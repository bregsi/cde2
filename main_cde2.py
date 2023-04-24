#Python Code for Raspberry Pie Zero W with Grove-Hat
#CO2,Temperature and Humidity Sensor
###########
#Libraries#
###########
from scd30_i2c import SCD30
import time
import csv
import sqlite3
import sys
from grove.gpio import GPIO
from grove.grove_4_digit_display import Grove4DigitDisplay
import chainable_rgb_direct
import threading

#######################
#Variable introduction#
#######################

#Location
location_ids = [0, 1, 2, 3, 4, 5]
location_edit_mode = False

#Last DB safe is ready set %TODO% set it to false, on startup, set it to false
db_connection = True

# Global variables for CO2, terature, and humidity
co2 = 0
temperature = 0
humidity = 0

# introduce display options
display_options = ["co2", "temperature", "humidity"]
display_option_index = 0
display_option = display_options[display_option_index]


# global variables for interaction between functions
button_use = False
window_open = False

######################
#Function Definitions#
######################

# Define a function to show the display based on the display option selected
def show_display():
    global display_option, co2, temperature, humidity, button_use
    while True:
        # Blink the display for CO2, Temperature, and Humidity options
        if display_option in ["co2", "temperature", "humidity"]:
            if button_use == True:
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
                print(f"CO2: {co2:.2f}ppm")
            elif display_option == "temperature":
                display.show(int(round(temperature, 0)))
                print(f"Temperature: {temperature:.2f}'C")
            elif display_option == "humidity":
                display.show(int(round(humidity, 0)))
                print(f"Humidity: {humidity:.2f}%")
            elif "LOC" in display_option:
                display.show(display_option)
                print(display_option)

            # Add a sleep between updates
            time.sleep(1)
        else:
            display.clear()
            # Add a sleep between updates
            time.sleep(0.5)



#Define a function to handle button presses
def handle_button_press():
    global display_option_index, display_option, display_options, button_use, window_open
    pressed_time = None
    delay_time = 0.25  # set the delay time to 0.25 second

    # Add debounce delay to handle rapid button presses
    debounce_delay = 0.1

    while True:
        try:
            #add debounce delay
            time.sleep(debounce_delay)
            # Read the button state (0 or 1)
            button_state = button.read()

            # If the button is pressed (LOW state) and we haven't started measuring
            # the pressed time yet, record the start time
            if button_state == 1 and pressed_time is None:
                pressed_time = time.monotonic()
                #button_use = 1
            #if button_state == 0 and pressed_time is None:
            #    none
            #if button_state == 1 and pressed_time is not None:
            #    none
            # If the button is released (HIGH state) and we have already started measuring
            # the pressed time, determine if it was a short or long press
            if button_state == 0 and pressed_time is not None:
                released_time = time.monotonic()
                pressed_duration = released_time - pressed_time
                #button_use = 1
                if pressed_duration >= 2.0 and pressed_duration < 5.0:
                    print("Button pressed for {:.2f} seconds, more than 2 seconds!".format(pressed_duration))
                    # Handle long press
                    #global window_open
                    if window_open == True:
                        window_open = False
                    else:
                        window_open = True
                    #time.sleep(1.1)
                    time.sleep(delay_time)
                    pressed_time = None
                    #button_use = 0
                elif pressed_duration >=5.0:
                    #entered location edit mode
                    if location_edit_mode == True:
                        write_location_id(location_id)
                        display_option="co2"
                        location_edit_mode = False
                    else:
                        location_edit_mode = True
                        display_option= "LOC" + str(location_id)


                else:
                    print("Button pressed for {:.2f} seconds, less than 2 seconds.".format(pressed_duration))
                    if display_option in ["co2", "temperature", "humidity"]:
                        # Cycle through display options on short press
                        display_option_index = (display_option_index + 1) % len(display_options)
                        display_option = display_options[display_option_index]
                        time.sleep(delay_time)
                        button_use = True
                    elif display_option in ["LOC0", "LOC1", "LOC2", "LOC3", "LOC4", "LOC5"]:
                        cycle_location()
                        display_option = "LOC" + str(location_id)



                time.sleep(delay_time)
                pressed_time = None

            # Wait for 0.1 seconds before checking again
            time.sleep(0.1)

        except KeyboardInterrupt:
            break
        except IOError:
            print("Error: Button")


# Define a function to save the measurement
def save_measurement():
    global co2, temperature, humidity, db_conn, cursor, location_id
    # Create a connection to the SQLite database and a cursor to execute SQL commands
    db_conn = sqlite3.connect('/home/pi/python/cde2_data.db')
    cursor = db_conn.cursor()

    # Create the temperature_humidity_entries table if it doesn't exist
    cursor.execute('''CREATE TABLE IF NOT EXISTS co2_temperature_humidity_entries
                      (timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                       co2 REAL,
                       temperature REAL,
                       humidity REAL,
                       window_open BOOL,
                       location_id REAL,
                       db_deliver_status BOOL)''')
    while True:
        if scd30.get_data_ready():
            m = scd30.read_measurement()
            if m is not None:
                co2 = m[0]
                temperature = m[1]
                humidity = m[2]
                print(f"CO2: {co2:.2f}ppm, temp: {temperature:.2f}'C, rh: {humidity:.2f}%")

                # Insert measurement data into database
                try:
                    cursor.execute(
                        "INSERT INTO co2_temperature_humidity_entries (co2,temperature, humidity,window_open,location_id,db_deliver_status) VALUES (?, ?, ?, ?, ?, ?)",
                        (m[0], m[1], m[2], window_open, location_id, False))
                    db_conn.commit()
                    print("Database data saved")
                except Exception as e:
                    print("Error saving data to local database: ", e)
            time.sleep(1.5)


#Define a function that handles LED signaling
def status_led():
    global db_connection, co2, window_open
    while True:
        try:
            if not db_connection:
                rgbled.setOneLED(42, 0, 0, 0)
                time.sleep(0.25)
                if window_open:
                    rgbled.setOneLED(42, 66, 0, 0)
            elif co2 > 1400:
                rgbled.setOneLED(0, 0, 10, 0)
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
            print("Error: RGB LED")

#Define a function that writes the location to a file
def write_location_id(location_id):
    with open('/home/pi/python/location_id.csv', mode='w', newline='') as location_id_file:
        writer = csv.writer(location_id_file)
        writer.writerow([location_id])

#Define a function that reads the location from a file
def read_location_id():
    with open('/home/pi/python/location_id.csv', mode='r') as location_id_file:
        reader = csv.reader(location_id_file)
        for row in reader:
            return int(row[0])

# Define a function to cycle through location IDs when the button is pressed
def cycle_location():
    global location_id
    location_id = (location_id + 1) % len(location_ids)
    print(f"Location ID: {location_ids[location_index]}")

###########################################
# Initialization of sensors and actuators #
###########################################

# Initializing 4-digit Display
#Connect Display to Socket D5
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
#Number of Leds
num_led = 1
rgbled = chainable_rgb_direct.rgb_led(num_led)

# Connect the Grove Button to PWM socket
button_pin = 12
button = GPIO(button_pin, GPIO.IN)


######
#MAIN#
######
# Read the saved location ID from the CSV file
try:
    location_id = read_location_id()
except IOError:
    print("Location ID not yet set")
    write_location_id(0)
    
###################
# Start Threading #
###################

# Start the display thread
display_thread = threading.Thread(target=show_display)
display_thread.start()

# Start the button press handling thread
button_thread = threading.Thread(target=handle_button_press)
button_thread.start()

#Start the measurement thread
measurement_thread = threading.Thread(target=save_measurement)
measurement_thread.start()

#Start the RGB LED Thread
rgbled_thread = threading.Thread(target=status_led)
rgbled_thread.start()
