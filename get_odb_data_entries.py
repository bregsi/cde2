## Quick Example How to Get Data from Oracle DB via URL-query
#Libraries
import json
import urllib.request
import csv
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import datetime

# Reads a CSV file and returns a list of the URLs in the first column.
def read_urls_from_csv():
    with open('/home/pi/python/urls.csv') as f:
        reader = csv.reader(f)
        urls = [row[0] for row in reader]
    return urls
# Get items from Oracle Database in JSON
def get_data_from_oracle_db(url, location_id, batch_size=100, max_entries=None, offset=0):
    try:
        measurement_times = []
        co2_values = []
        #offset = 0
        total_entries = 0

        while True:
            # Append the query parameters 'location_id', 'limit', and 'offset' to the URL
            url_with_query = f"{url}?location_id={location_id}&limit={batch_size}&offset={offset}"

            # Make a GET request to retrieve the data
            response = urllib.request.urlopen(url_with_query)

            if response.status == 200:
                data = json.load(response)

                if 'items' in data:
                    for record in data['items']:
                        measurement_time_str = record['measurement_time']
                        measurement_time = datetime.datetime.strptime(measurement_time_str, "%Y-%m-%d %H:%M:%S")
                        co2 = record['co2_value']
                        if co2 is not None:
                            co2 = int(record['co2_value'])
                            if co2 > 1000:
                                continue  # Skip the measurement if CO2 value exceeds 1000
                        else:
                            co2 = record['co2_value']

                        measurement_times.append(measurement_time)
                        co2_values.append(co2)
                        total_entries += 1

                        if max_entries is not None and total_entries >= max_entries:
                            return measurement_times, co2_values

                    if not data['hasMore']:
                        break  # Exit the loop if there are no more records

                    offset += batch_size  # Increment the offset for the next page

                else:
                    print("No 'items' key found in the response JSON")
                    break

            else:
                print(f"Error retrieving data from Oracle database. Status code: {response.status}")
                print("Response content:", response.read())
                break

        return measurement_times, co2_values

    except Exception as e:
        print("Error while trying to retrieve data from Oracle database: ", e)

    return [], []
# plot a quick graph
def plot_graph(measurement_times, co2_values):
    plt.scatter(measurement_times, co2_values, s=5)  # Plot points instead of lines
    plt.xlabel("Measurement Time")
    plt.ylabel("CO2 Values")
    plt.title("CO2 Values over Time - Outdoors")

    # Format x-axis tick labels
    plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.xticks(rotation=45)

    plt.tight_layout()  # Adjust spacing to prevent overlapping labels
    plt.savefig("/home/pi/python/co2_plot.png")  # Save the plot as a PNG file
    print("Plot saved as co2_plot.png")


location_id = 1
urls = read_urls_from_csv()

if not urls:
    print("No URLs found in the CSV file.")
else:
    url = urls[0]  # Assuming the first URL from the CSV is used
    print(url)
    measurement_times, co2_values = get_data_from_oracle_db(url, location_id, batch_size=250, max_entries=250, offset=36000)
    plot_graph(measurement_times, co2_values)
