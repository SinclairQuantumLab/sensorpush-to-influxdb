"""
Query the last measured time for each SensorPush sensor from InfluxDB and print it.

This is intentionally a simple sequential test script.
"""

import influxdb_client
from datetime import datetime

# >>> InfluxDB configuration >>>
INFLUXDB_URL = "http://synology-nas:8086"
INFLUXDB_TOKEN = "xixuoRzjm51D2WQh5uHnqjd0H28NJuaKpiHAmmSzEUlqgUhxRl0A01Na6-a_gX6BENlP3xx8FEoGP-qMx0Xrow=="
INFLUXDB_ORG = "sinclairgroup"
INFLUXDB_BUCKET = "imaq"

INFLUXDB_CLIENT = influxdb_client.InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
INFLUXDB_QUERY_API = INFLUXDB_CLIENT.query_api()
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
        print(datetime.fromisoformat("2026-03-14T05:18:53.000Z") == measured_time)
        

if not found:
    print("No SensorPush data found in InfluxDB.")