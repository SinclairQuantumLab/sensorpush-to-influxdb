"""
Poll SensorPush sensors and upload new samples to InfluxDB.

This script runs continuously, polls SensorPush at a fixed interval,
skips already-seen samples using per-sensor observed timestamps, and
raises after a configured number of total exceptions so supervisor can
handle process-level recovery.
"""

from supervisor_helper import *
import requests
from sensorpush_client import SensorPushClient
import json
import time

print()
print("----- SensorPush -> InfluxDB uploader -----")
print()

# >>> SensorPush API connection >>>
SP_EMAIL = "sinclairquantumlab@gmail.com"
SP_PASSWORD = "rubidium87"

print("Authenticating to SensorPush...", end=" ")
client = SensorPushClient(SP_EMAIL, SP_PASSWORD)
client.authenticate()
print("Done.")
print()
# << SensorPush API connection <<<

# >>> loop configuration >>>
INTERVAL_s = 10
EX_THRESHOLD = 3
print(f"Polling interval = {INTERVAL_s} s, exception threshold = {EX_THRESHOLD}.")
print()
# <<< loop configuration <<<

# >>> InfluxDB configuration >>>
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
# Connection Settings
INFLUXDB_URL = "http://synology-nas:8086"
INFLUXDB_TOKEN = "xixuoRzjm51D2WQh5uHnqjd0H28NJuaKpiHAmmSzEUlqgUhxRl0A01Na6-a_gX6BENlP3xx8FEoGP-qMx0Xrow=="  # sinclairgroup_influxdb's admin token
INFLUXDB_ORG = "sinclairgroup"     # The Organization name you set during initial setup
INFLUXDB_BUCKET = "imaq"    # main bucket for IMAQ lab
# Initialize the InfluxDB Client and the Write API
INFLUXDB_CLIENT = influxdb_client.InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
INFLUXDB_WRITE_API = INFLUXDB_CLIENT.write_api(write_options=SYNCHRONOUS)
print(f"InfluxDB client initialized for org='{INFLUXDB_ORG}', bucket='{INFLUXDB_BUCKET}'.")
print()
# <<< InfluxDB configuration <<<


# >>> functions for unit conversion >>> 

def f_to_c(temp_f):
    return (temp_f - 32.0) * 5.0 / 9.0

def inhg_to_hpa(pressure_inhg):
    return pressure_inhg * 33.8638866667

# <<< functions for unit conversion <<<


# Main loop for querying SensorPush samples and uploading to InfluxDB
ex_count = 0
last_uploaded_observed_by_sensor = {}

print("Entering main polling loop...")
print()

il = 0 # iteration loop counter
while True:
    try:
        # log_info(f"Iteration {il}:", end=" ")
        msg_il = f"Iteration {il}: "

        # >>>>> querying samples and parsing them for InfluxDB >>>>>
        # log_info("Polling SensorPush for latest samples...")

        try:
            # Fetch sensor list and sample data on every iteration
            sensors_info = client.get_sensors() 
            samples_data = client.get_samples(limit=1) # limit= # of last samples to retrieve, default is 1
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as ex:
            log_error(msg_il)
            log_error(f"SensorPush query failed: {type(ex).__name__}: {ex}")
            log_warn("Re-establishing SensorPush connection and retrying once...")
            client.authenticate()
            log_warn("SensorPush re-authentication succeeded.")
            # Retry fetching after re-authentication
            sensors_info = client.get_sensors() 
            samples_data = client.get_samples(limit=1) #
            log_warn("Retry succeeded.")
            
        sensors_block = samples_data.get("sensors", {})

        influxdb_records = []
        new_observed_by_sensor = {}

        for sensor_id, sample_list in sensors_block.items():
            if not isinstance(sample_list, list):
                continue
            
            # Retrieve the sensor name from the freshly queried sensors_info
            # it will raise KeyError if the sensor_id is not found from the queried sensor list
            try:
                sensor_name = sensors_info[sensor_id].get("name", "<unnamed>")
            except KeyError as ex:
                raise KeyError(f"Sensor ID {sensor_id} not found in queried sensor list.") from ex

            for sample in sample_list:
                observed = sample["observed"]
                last_uploaded_observed = last_uploaded_observed_by_sensor.get(sensor_id)

                if last_uploaded_observed is not None and observed <= last_uploaded_observed:
                    continue

                influxdb_record = {
                    "measurement": "SensorPush",
                    "tags": {
                        "sensor_id": sensor_id,
                        "sensor_name": sensor_name,
                        "gateway": str(sample.get("gateways", "")),
                    },
                    "fields": {},
                    "time": observed,
                }

                temperature_f = sample.get("temperature")
                if temperature_f is not None:
                    influxdb_record["fields"]["Temperature[degC]"] = f_to_c(float(temperature_f))

                humidity = sample.get("humidity")
                if humidity is not None:
                    influxdb_record["fields"]["Humidity[%]"] = float(humidity)

                dewpoint_f = sample.get("dewpoint")
                if dewpoint_f is not None:
                    influxdb_record["fields"]["DewPoint[degC]"] = f_to_c(float(dewpoint_f))

                barometric_pressure_inhg = sample.get("barometric_pressure")
                if barometric_pressure_inhg is not None:
                    influxdb_record["fields"]["BarometricPressure[hPa]"] = inhg_to_hpa(float(barometric_pressure_inhg))

                vpd = sample.get("vpd")
                if vpd is not None:
                    influxdb_record["fields"]["VPD[kPa]"] = float(vpd)

                altitude = sample.get("altitude")
                if altitude is not None:
                    influxdb_record["fields"]["Altitude[m]"] = float(altitude)

                altimeter_pressure_inhg = sample.get("altimeter_pressure")
                if altimeter_pressure_inhg is not None:
                    influxdb_record["fields"]["AltimeterPressure[hPa]"] = inhg_to_hpa(float(altimeter_pressure_inhg))

                influxdb_records.append(influxdb_record)
                new_observed_by_sensor[sensor_id] = observed

        # if there is no records to upload:
        if not influxdb_records:
            log(msg_il + "No new SensorPush samples to upload.")
            time.sleep(INTERVAL_s)
            il += 1
            continue

        # <<<<< querying samples and parsing them for InfluxDB <<<<<

        # Upload to InfluxDB
        INFLUXDB_WRITE_API.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=influxdb_records)
        # log_warn("InfluxDB write is currently disabled for debugging.")
        log(msg_il + f"Uploaded {len(influxdb_records)} influxdb_record(s).")
        

        # Update the last uploaded observed timestamp for each sensor
        for sensor_id, observed in new_observed_by_sensor.items():
            last_uploaded_observed_by_sensor[sensor_id] = observed

    except Exception as ex:
        log_error(msg_il)
        ex_count += 1
        log_error(f"Error during measurement/upload ({ex_count}/{EX_THRESHOLD}): {type(ex).__name__}: {ex}")
        if ex_count >= EX_THRESHOLD:
            log_error("Exception threshold reached. Raising to supervisor.")
            raise

    # log_info(f"Sleeping for {INTERVAL} s.")
    time.sleep(INTERVAL_s)
    il += 1