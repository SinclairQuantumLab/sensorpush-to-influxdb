"""
Query the last measured time for each SensorPush sensor from InfluxDB and print it.

This is intentionally a simple sequential test script.
"""

import influxdb_client
from datetime import datetime

# >>> load IMAQ config >>>
import tomllib
with open("imaq_config/auth.toml", "rb") as f:
    AUTH = tomllib.load(f)
# <<< load IMAQ config <<<

# >>> InfluxDB configuration >>>
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
# Initialize the InfluxDB Client and the Write API
INFLUXDB_CLIENT = influxdb_client.InfluxDBClient(**AUTH["influxdb"])
INFLUXDB_WRITE_API = INFLUXDB_CLIENT.write_api(write_options=SYNCHRONOUS)
INFLUXDB_QUERY_API = INFLUXDB_CLIENT.query_api()
INFLUXDB_ORG = AUTH["influxdb"]["org"]; INFLUXDB_BUCKET = AUTH["influxdb"]["bucket"]
print(f"InfluxDB client initialized for org='{INFLUXDB_ORG}', bucket='{INFLUXDB_BUCKET}'.")
print()
# <<< InfluxDB configuration <<<

flux = f'''
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: 0)
  |> filter(fn: (r) => r["_measurement"] == "SensorPush")
  |> group(columns: ["sensor_id"])
  |> last(column: "_time")
  |> keep(columns: ["sensor_id", "_time"])
'''

tables = INFLUXDB_QUERY_API.query(query=flux, org=INFLUXDB_ORG)

print()
print("----- Last measured time in InfluxDB for each SensorPush sensor -----")
print()

found = False

for table in tables:
    for record in table.records:
        sensor_id = record.values.get("sensor_id", None)
        measured_time = record.get_time()

        if sensor_id is None or measured_time is None:
            continue

        found = True
        print(f"sensor_id={sensor_id}  last_measured_time={measured_time} ({type(measured_time)})")
        

if not found:
    print("No SensorPush data found in InfluxDB.")