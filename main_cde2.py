# Python Code for Raspberry Pie Zero W with Grove-Hat

# CO2,Temperature and Humidity Sensor

#############
# Libraries #
#############
from scd30_i2c import SCD30
import time
import datetime
import csv
import sqlite3
import requests
from grove.gpio import GPIO
from grove.grove_4_digit_display import Grove4DigitDisplay
import chainable_rgb_direct
import threading
import logging

#########################
# Variable introduction #
#########################

# Location
location_ids = [0, 1, 2, 3, 4, 5]
location_edit_mode = False

# Last DB safe is ready set
db_connection = False

# Global variables for CO2, temperature, and humidity
co2 = 0
temperature = 0
humidity = 0

# introduce first set of display options
display_options = ["co2", "temperature", "humidity"]
display_option_index = 0
display_option = display_options[display_option_index]

# global variables for interaction between functions
button_use = False
window_open = False

# Configure logging
log_file = '/home/pi/python/error.log'
logging.basicConfig(filename=log_file, level=logging.ERROR)

##########################
# Create Local Databases #
##########################

# Create a connection to the SQLite database and a cursor to execute SQL commands
db_conn = sqlite3.connect('/home/pi/python/cde2_data.db')
cursor = db_conn.cursor()
# Create the temperature_humidity_entries table if it doesn't exist
cursor.execute('''CREATE TABLE IF NOT EXISTS co2_temperature_humidity_entries
                  (timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                   measurement_time STRING,
                   co2 REAL,
                   temperature REAL,
                   humidity REAL,
                   window_open BOOL,
                   location_id REAL,
                   db_deliver_status BOOL)''')
db_conn.commit()
db_conn.close()

# Create a connection to the Temporary SQLite database and a temporary cursor to execute SQL commands
db_conn_temp = sqlite3.connect('/home/pi/python/cde2_data_temp.db')
cursor_temp = db_conn_temp.cursor()
# Create the temporary temperature_humidity_entries table if it doesn't exist
cursor_temp.execute('''CREATE TABLE IF NOT EXISTS co2_temperature_humidity_entries
                  (timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                   measurement_time STRING,
                   co2 REAL,
                   temperature REAL,
                   humidity REAL,
                   window_open BOOL,
                   location_id REAL,
                   db_deliver_status BOOL)''')

db_conn_temp.commit()
db_conn_temp.close()


########################
# Function Definitions #
########################

# 4-Digit Display Module
# Define a function to show the display based on the display option selected
def show_display():
    global display_option, co2, temperature, humidity, button_use
    while True:
        # Blink the display for CO2, Temperature, and Humidity options
        if display_option in ["co2", "temperature", "humidity"]:
            if button_use:
                for _ in range(1):
                    if display_option == 'co2':
                        display.show('CO2 ')
                    elif display_option == "temperature":
                        display.show('C   ')
                    elif display_option == "humidity":
                        display.show('HU  ')
                    time.sleep(0.5)
                    display.clear()
                    time.sleep(0.5)
                    button_use = False

            # Show the current display option on the 4-digit display
            if display_option == "co2":
                display.show(int(round(co2, 0)))
                # print(f"CO2: {co2:.2f}ppm")
            elif display_option == "temperature":
                display.show(int(round(temperature, 0)))
                # print(f"Temperature: {temperature:.2f}'C")
            elif display_option == "humidity":
                display.show(int(round(humidity, 0)))
                # print(f"Humidity: {humidity:.2f}%")
                # Add a sleep between updates
                time.sleep(0.5)
            else:
                display.clear()

        if "LOC" in display_option:
            display.show(display_option)
            print(display_option)

        # Add a sleep between updates
        time.sleep(0.25)

# Button Module
# Define a function to handle button presses
def handle_button_press():
    global display_option_index, display_option, display_options, button_use, window_open, location_edit_mode
    pressed_time = None
    delay_time = 0.25  # set the delay time to 0.25 second

    # Add debounce delay to handle rapid button presses
    debounce_delay = 0.1

    while True:
        try:
            # add debounce delay
            time.sleep(debounce_delay)
            # Read the button state (0 or 1)
            button_state = button.read()

            # If the button is pressed (LOW state) and we haven't started measuring
            # the pressed time yet, record the start time
            if button_state == 1 and pressed_time is None:
                pressed_time = time.monotonic()

            # If the button is released (HIGH state) and we have already started measuring
            # the pressed time, determine if it was a short or long press
            if button_state == 0 and pressed_time is not None:
                released_time = time.monotonic()
                pressed_duration = released_time - pressed_time
                # button_use = 1
                if pressed_duration >= 2.0 and pressed_duration < 5.0:
                    #print("Button pressed for {:.2f} seconds, more than 2 seconds!".format(pressed_duration))
                    # Handle long press
                    # global window_open
                    if window_open == True:
                        window_open = False
                    else:
                        window_open = True
                    # time.sleep(1.1)
                    time.sleep(delay_time)
                    pressed_time = None
                    # button_use = 0
                elif pressed_duration >= 5.0:
                    #print("Button pressed for {:.2f} seconds, more than 5 seconds!".format(pressed_duration))
                    # entered location edit mode
                    if location_edit_mode == True:
                        write_location_id(location_id)
                        display_option = display_option_temp
                        #print(display_option)
                        location_edit_mode = False
                    else:
                        location_edit_mode = True
                        display_option_temp = display_option
                        display_option = "LOC" + str(location_id)
                        #print(display_option)
                    pressed_time = None


                else:
                    #print("Button pressed for {:.2f} seconds, less than 2 seconds.".format(pressed_duration))
                    if display_option in ["co2", "temperature", "humidity"]:
                        # Cycle through display options on short press
                        display_option_index = (display_option_index + 1) % len(display_options)
                        display_option = display_options[display_option_index]
                        time.sleep(delay_time)
                        button_use = True
                    elif display_option in ["LOC0", "LOC1", "LOC2", "LOC3", "LOC4", "LOC5"]:
                        cycle_location()
                        display_option = "LOC" + str(location_id)
                    else:
                        logging.error("Error in Short Button Press")

                time.sleep(delay_time)
                pressed_time = None

            # Wait for 0.1 seconds before checking again
            time.sleep(0.1)

        except KeyboardInterrupt:
            break
        except IOError:
            logging.error("Error: Button")

# SCD30 Sensor Module
# Define a function to save the measurement
def save_measurement():
    global co2, temperature, humidity, db_conn, cursor, location_id
    # Establish a connection to the SQLite database and a cursor to execute SQL commands
    db_conn = sqlite3.connect('/home/pi/python/cde2_data.db')
    cursor = db_conn.cursor()
    counter = 1
    while True:
        start_time = time.time()
        if scd30.get_data_ready():
            m = scd30.read_measurement()
            measurement_time = datetime.datetime.now()
            mst = measurement_time.strftime("%Y-%m-%d %H:%M:%S")
            if m is not None:
                co2 = round(m[0], 2)
                temperature = round(m[1], 2)
                humidity = round(m[2], 2)
                #print(f"CO2: {co2:.2f}ppm, temp: {temperature:.2f}'C, rh: {humidity:.2f}%")                
                # Insert measurement data into database
                try:
                    cursor.execute(
                        "INSERT INTO co2_temperature_humidity_entries (measurement_time, co2,temperature, humidity,window_open,location_id,db_deliver_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (mst, co2, temperature, humidity, window_open, location_id, False))
                    db_conn.commit()
                    #print("Saved all Measurements to local database")
                except Exception as e:
                    logging.error(str(e))
                    #print("Error saving data to local database: ", e)

                # Start thread to transmit every 5th measurement data to oracle database
                if counter % 5 == 0:
                    oracle_db_thread = threading.Thread(target=transmission_to_oracle_db, args=(
                    measurement_time, co2, temperature, humidity, window_open, location_id))
                    oracle_db_thread.start()
                    counter = 0
                counter += 1

        # Check the time how long measurement took (transmission to oracle takes a long time)
        end_time = time.time()
        time_taken = end_time - start_time
        #print("Mess-Zeit:")
        #print(time_taken)
        # Pause for at least x seconds
        if time_taken < 2.0:
            time.sleep(2.0 - time_taken)

# DB Transfer Module
# Define a function which sends the measurements to the oracle db
def transmission_to_oracle_db(measurement_time, co2, temperature, humidity, window_open, location_id):
    global urls, db_connection
    mst = measurement_time.strftime("%Y-%m-%d %H:%M:%S")

    # Establish a connection to the Temporary SQLite database and a temporary cursor to execute SQL commands
    db_conn_temp = sqlite3.connect('/home/pi/python/cde2_data_temp.db')
    cursor_temp = db_conn_temp.cursor()

    try:
        payloads = {
            "measurement_time": mst,
            "location_id": location_id,
            "window_open": int(window_open),
            "co2_value": co2,
            "co2_unit": "ppm",
            "temperature_value": temperature,
            "temperature_unit": "°C",
            "humidity_value": humidity,
            "humidity_unit": "%"
                }
        #print(payloads)
        response = requests.post(urls[0], json=payloads)
        if response.status_code == 200:
            # Print the status code of the request made to the Oracle database
            #print(f"CO2, Temperature and Humidity sent to Oracle database. Status code: {response.status_code}")
            db_connection = True
        else:
            # Print the status code of the request made to the Oracle database
            #print(f"CTH to Oracle database Error. Status code: {response.status_code}")
            db_connection = False
            cursor_temp.execute(
                "INSERT INTO co2_temperature_humidity_entries (measurement_time, co2, temperature, humidity,window_open,location_id,db_deliver_status) VALUES (?, ?, ?, ?, ?, ?,?)",
                (mst, co2, temperature, humidity, window_open, location_id, False))
            db_conn_temp.commit()
            #print("Dataset locally temporarily saved")
    except Exception as e:
        #print("Error while trying to send the Dataset: ", e)
        logging.error(str(e))
        db_connection = False
        try:
            cursor_temp.execute(
                "INSERT INTO co2_temperature_humidity_entries (measurement_time, co2, temperature, humidity,window_open,location_id,db_deliver_status) VALUES (?, ?, ?, ?, ?, ?,?)",
                (mst, co2, temperature, humidity, window_open, location_id, False))
            db_conn_temp.commit()
            #print("CTH locally saved (to temp db).")
        except Exception as e:
            #print("Error while trying to save the Dataset locally (to temp db): ", e)
            logging.error(str(e))



# DB Transfer Retry Module
# Define a function that retries submitting measurement data
def transmission_to_oracle_db_retry():
    global urls
    while True:
        start_time = time.time()
        # Create a connection to the Temporary SQLite database and a temporary cursor to execute SQL commands
        db_conn_temp = sqlite3.connect('/home/pi/python/cde2_data_temp.db')
        cursor_temp = db_conn_temp.cursor()



        #check if table is empty
        cursor_temp.execute("SELECT COUNT(*) FROM co2_temperature_humidity_entries")
        result=cursor_temp.fetchone()
        if result[0] == 0:
            result[0] = 0
            #print('No measurements temporarily saved')
        else:
            #print(f'The temp table has {result[0]} measurement(s) saved.')

            # Fetch all unsent data from temperature_data, humidity_data, and light_data tables
            cursor_temp.execute("SELECT * FROM co2_temperature_humidity_entries WHERE db_deliver_status = FALSE")
            cth_data = cursor_temp.fetchall()

            # Upload co2 data to the Oracle database
            for entry in cth_data:
                payloads = {
                    "measurement_time": entry[1],
                    "location_id": entry[6],
                    "window_open": int(entry[5]),
                    "co2_value": entry[2],
                    "co2_unit": "ppm",
                    "temperature_value": entry[3],
                    "temperature_unit": "°C",
                    "humidity_value": entry[4],
                    "humidity_unit": "%"
                }
                #print("Retry: Payload")
                #print(payloads)
                try:
                    response = requests.post(urls[0], json=payloads)
                    response.raise_for_status()
                    if response.status_code == 200:
                        # Print the status code of the request made to the Oracle database
                        #print(f"RETRY: CO2, Temperature and Humidity sent to Oracle database. Status code: {response.status_code}")
                        # db_connection = True
                        cursor_temp.execute(
                            "UPDATE co2_temperature_humidity_entries SET db_deliver_status = TRUE WHERE measurement_time = ?",
                            (entry[1],))
                        db_conn_temp.commit()
                    else:
                        #print(f"RETRY Fail: CO2, Temperature and Humidity not sent to Oracle database. Status code: {response.status_code}")
                        logging.error(str(response.satus_code))
                except requests.exceptions.RequestException as e:
                    #print(f"Retry: Failed to retry upload dataset to ODB {entry[0]}: {e}")
                    logging.error(str(e))

            # delete all entries which have sucessfully been sent to ODB
            cursor_temp.execute("DELETE FROM co2_temperature_humidity_entries WHERE db_deliver_status = TRUE")
            db_conn_temp.commit()
            #print(f"Retry:Uploaded entry {entry[0]} to Oracle database.")


        # Close SQLite Connection
        db_conn_temp.close()

        stop_time = time.time()
        time_passed = stop_time - start_time
        #print("DB Retry Code: elapsed time since start")
        #print(time_passed)
        if time_passed < 120:
            time.sleep(120 - time_passed)

# LED Module
# Define a function that handles LED signaling
def status_led():
    #setuo global variables
    global db_connection, co2, window_open
    #Start Loop for the RGB LED
    while True:
        try:
            #condition if Oracle DB Transmission failed
            if not db_connection:
                rgbled.setOneLED(0, 0, 10, 0)
                time.sleep(0.25)
                #Window Condition while ODB connection is not available
                if window_open:
                    rgbled.setOneLED(42, 66, 0, 0)
                if co2 > 1400:
                    time.sleep(0.25)
                    rgbled.setOneLED(42, 0, 0, 0)
            #condition is co2 value is higher then 1400ppm
            elif co2 > 1400:
                rgbled.setOneLED(42, 0, 0, 0)
                if window_open:
                    time.sleep(0.25)
                    rgbled.setOneLED(42, 66, 0, 0)
            elif window_open:
                rgbled.setOneLED(42, 66, 0, 0)
                time.sleep(0.25)
                rgbled.setOneLED(0, 0, 0, 0)
            else:
                rgbled.setOneLED(0, 0, 0, 0)
            time.sleep(0.25)
        except KeyboardInterrupt:
            break
        except IOError:
            e="Error: RGB LED"
            logging.error(str(e))


# Define a function that writes the location to a file
def write_location_id(location_id):
    with open('/home/pi/python/location_id.csv', mode='w', newline='') as location_id_file:
        writer = csv.writer(location_id_file)
        writer.writerow([location_id])


# Define a function that reads the location from a file
def read_location_id():
    with open('/home/pi/python/location_id.csv', mode='r') as location_id_file:
        reader = csv.reader(location_id_file)
        for row in reader:
            return int(row[0])


# Reads a CSV file and returns a list of the URLs in the first column.
def read_urls_from_csv():
    with open('/home/pi/python/urls.csv') as f:
        reader = csv.reader(f)
        urls = [row[0] for row in reader]
    return urls


# Define a function to cycle through location IDs when the button is pressed
def cycle_location():
    global location_id, location_ids
    location_id = (location_id + 1) % len(location_ids)
    #print(f"Location ID: {location_ids[location_id]}")


###########################################
# Initialization of sensors and actuators #
###########################################

# Initializing 4-digit Display
# Connect Display to Socket D5
pin_display = 5
display = Grove4DigitDisplay(pin_display, pin_display + 1)
display.set_colon(False)

# Initializing co2, temp & humidity sensor
# Connect to the I2C socket
scd30 = SCD30()
scd30.set_measurement_interval(2)
scd30.start_periodic_measurement()

# Initializing Chainable RGB LED
# connect Chainable RGB LED to RPISER(UART) Socket
# Number of Leds
num_led = 1
rgbled = chainable_rgb_direct.rgb_led(num_led)

# Connect the Grove Button to PWM socket
button_pin = 12
button = GPIO(button_pin, GPIO.IN)

########
# MAIN #
########
# Read the saved location ID from the CSV file
try:
    location_id = read_location_id()
except IOError:
    #print("Location ID not yet set")
    write_location_id(0)

# Read the connection info to the oracle DB from file
urls = read_urls_from_csv()

# Start Threading #

# Start the display thread
display_thread = threading.Thread(target=show_display)
display_thread.start()

# Start the button press handling thread
button_thread = threading.Thread(target=handle_button_press)
button_thread.start()

# Start the measurement thread
measurement_thread = threading.Thread(target=save_measurement)
measurement_thread.start()

# Start the RGB LED Thread
rgbled_thread = threading.Thread(target=status_led)
rgbled_thread.start()

# Start the retry for the transmission to Oracle DB
oracle_db_retry_thread = threading.Thread(target=transmission_to_oracle_db_retry)
oracle_db_retry_thread.start()
