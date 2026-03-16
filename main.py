"""
Poll SensorPush sensors and upload new samples to InfluxDB.

This script runs continuously, polls SensorPush at a fixed interval,
asks InfluxDB for the latest uploaded sample time for each sensor, and
raises after a configured number of total exceptions so supervisor can
handle process-level recovery.
"""

from supervisor_helper import *
import requests
from sensorpush_client import SensorPushClient
import time
from datetime import datetime, timezone

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
# <<< SensorPush API connection <<<

# >>> loop configuration >>>
INTERVAL_s = 60
EX_THRESHOLD = 3
print(f"Polling interval = {INTERVAL_s} s, exception threshold = {EX_THRESHOLD}.")
print()
# <<< loop configuration <<<

# check the input value
# 1 query per minute is the maximum allowed for SensorPush API
# https://www.sensorpush.com/gateway-cloud-api
if INTERVAL_s < 60: raise ValueError("The loop interval (INTERVAL_s) should be at least 60 s.")

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
INFLUXDB_QUERY_API = INFLUXDB_CLIENT.query_api()
print(f"InfluxDB client initialized for org='{INFLUXDB_ORG}', bucket='{INFLUXDB_BUCKET}'.")
print()
# <<< InfluxDB configuration <<<


# >>> functions for unit conversion >>>
def f_to_c(temp_f):
    """Convert temperature from degF to degC."""
    return (temp_f - 32.0) * 5.0 / 9.0

def inhg_to_hpa(pressure_inhg):
    """Convert pressure from inHg to hPa."""
    return pressure_inhg * 33.8638866667
# <<< functions for unit conversion <<<

# >>> helper functions >>>
do_debug = False
def print_debug(*args, **kwargs):
    """Print debug messages only when do_debug is enabled."""
    if do_debug is False: return
    print("[DEBUG] ", *args, **kwargs)

def parse_utc_timestamp(ts: str) -> datetime:
    """Parse a UTC timestamp string into a timezone-aware datetime."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)

def get_last_relayed_sample_datetimes() -> dict[str, datetime]:
    """
    Query InfluxDB for the latest relayed sample time of each sensor.

    Returns:
        dict[str, datetime]:
            Mapping from sensor_id to the latest sample timestamp
            already relayed to InfluxDB.
    """
    flux = f'''
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: 0)
  |> filter(fn: (r) => r["_measurement"] == "SensorPush")
  |> group(columns: ["sensor_id"])
  |> last(column: "_time")
  |> keep(columns: ["_time", "sensor_id"])
'''
    last_relayed_sample_datetimes = {}
    tables = INFLUXDB_QUERY_API.query(query=flux, org=INFLUXDB_ORG)
    for table in tables:
        for record in table.records:
            sensor_id = record.values.get("sensor_id")
            observed = record.get_time()
            if sensor_id is None or observed is None:
                continue
            last_relayed_sample_datetimes[sensor_id] = observed

    print_debug(f"last_relayed_sample_times count={len(last_relayed_sample_datetimes)}")
    for sensor_id, observed in last_relayed_sample_datetimes.items():
        print_debug(f"influx cursor sensor_id={sensor_id} observed={observed}")

    return last_relayed_sample_datetimes

def query_sensorpush() -> tuple[dict[str, any], dict[str, any]]:
    """
    Query SensorPush once for all sensors after a global start time.

    Logic:
    - Read the latest relayed sample time of each sensor from InfluxDB.
    - Set the SensorPush query start time to the earliest of those
      existing relayed timestamps.
    - Query SensorPush once from that start time.
    - Remove samples that were already relayed to InfluxDB.

    Assumptions:
    - All new sensors are connected to the gateway when deployed.
    - No data already stored in InfluxDB will be lost.
    - This app does not exclude particular sensors.
    """

    # get the measured time of the last sample relayed to InfluxDB for each sensor
    last_relayed_sample_datetimes = get_last_relayed_sample_datetimes()

    # get sensor information here because the querying sample data below
    # takes a while and the sensor info might change meanwhile
    sensors = client.get_sensors()

    # >>>>> query samples after the last one relayed to InfluxDB >>>>>

    # set sensorpush query start time to be the earliest last measured time
    # across the sensors that already exist in InfluxDB
    # if there is no prior relayed sample at all, query from Unix epoch
    observed_existing = [observed for sensor_id, observed in last_relayed_sample_datetimes.items() if observed is not None]
    query_start_datetime = min(observed_existing) if observed_existing else datetime(1970, 1, 1, tzinfo=timezone.utc)
    query_start_time_str = query_start_datetime.isoformat(timespec='milliseconds')

    # query samples from sensorpush
    samples = client.get_samples(
                start_time=query_start_time_str,
                limit=1000
            )
    
    # remove the samples previously relayed
    # also drop the records with no specified measured time (shouldn't happen though)
    for sensor_id, records in samples["sensors"].items():
        last_relayed_sample_datetime = last_relayed_sample_datetimes.get(sensor_id, None)
        if last_relayed_sample_datetime is None:
            continue

        records_filtered = []
        for record in records:
            measured_time_str = record.get("observed", None)
            if measured_time_str is None:
                continue
            measured_datetime = datetime.fromisoformat(measured_time_str)
            if measured_datetime <= last_relayed_sample_datetime:
                continue
            records_filtered += [record]
        samples["sensors"][sensor_id] = records_filtered

    # <<<<< query samples after the last one relayed to InfluxDB <<<<<

    return sensors, samples

def upload_new_samples(
    sensors: dict[str, any],
    samples: dict[str, any],
) -> int:
    """
    Convert queried SensorPush samples into InfluxDB records and upload them.

    Returns:
        int:
            Number of InfluxDB records prepared for upload.
    """

    influxdb_records = []

    print_debug(f"upload_new_samples sensor_count={len(samples['sensors'])}")

    # >>>>> prepare records to upload to InfluxDB >>>>>

    for sensor_id, records in samples["sensors"].items(): # iterate record over different sensors
        # Retrieve the sensor name from the freshly queried sensors
        # it will raise KeyError if the sensor_id is not found from the queried sensor list
        sensor_name = sensors[sensor_id].get("name", "")

        for record in records:
            measured_time = record["observed"]
            influxdb_record = {
                "measurement": "SensorPush",
                "tags": {
                    "sensor_id": sensor_id,
                    "sensor_name": sensor_name,
                    "gateway": str(record.get("gateways", "")),
                },
                "fields": {},
                "time": measured_time,
            }

            temperature_f = record.get("temperature")
            if temperature_f is not None:
                influxdb_record["fields"]["Temperature[degC]"] = f_to_c(float(temperature_f))

            humidity = record.get("humidity")
            if humidity is not None:
                influxdb_record["fields"]["Humidity[%]"] = float(humidity)

            dewpoint_f = record.get("dewpoint")
            if dewpoint_f is not None:
                influxdb_record["fields"]["DewPoint[degC]"] = f_to_c(float(dewpoint_f))

            barometric_pressure_inhg = record.get("barometric_pressure")
            if barometric_pressure_inhg is not None:
                influxdb_record["fields"]["BarometricPressure[hPa]"] = inhg_to_hpa(float(barometric_pressure_inhg))

            vpd = record.get("vpd")
            if vpd is not None:
                influxdb_record["fields"]["VPD[kPa]"] = float(vpd)

            altitude = record.get("altitude")
            if altitude is not None:
                influxdb_record["fields"]["Altitude[m]"] = float(altitude)

            altimeter_pressure_inhg = record.get("altimeter_pressure")
            if altimeter_pressure_inhg is not None:
                influxdb_record["fields"]["AltimeterPressure[hPa]"] = inhg_to_hpa(float(altimeter_pressure_inhg))

            influxdb_records += [influxdb_record]
            print_debug(f"appended influxdb_record sensor_id={sensor_id} time={measured_time} field_count={len(influxdb_record['fields'])}")

    print_debug(f"total influxdb_records prepared={len(influxdb_records)}")

    # <<<<< prepare records to upload to InfluxDB <<<<<
    
    # >>>>> upload to InfluxDB >>>>>

    if not influxdb_records:
        print_debug("no records to write to InfluxDB")
        return 0
    for record in influxdb_records:
        print_debug(f"write_record sensor_id={record['tags']['sensor_id']} time={record['time']} sensor_name={repr(record['tags']['sensor_name'])}")

    INFLUXDB_WRITE_API.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=influxdb_records)
    print_debug(f"INFLUXDB_WRITE_API.write completed for {len(influxdb_records)} record(s)")
    # log_warn("InfluxDB write is currently disabled for debugging.")

    # <<<<< upload to InfluxDB <<<<<

    return len(influxdb_records)
# <<< helper functions <<<

# Main loop for querying SensorPush samples and uploading to InfluxDB
ex_count = 0

print("Entering main polling loop...")
print()

il = 0  # iteration loop counter
while True:
    try:
        # log_info(f"Iteration {il}:", end=" ")
        msg_il = f"Iteration {il}: "

        # >>>>> querying samples >>>>>
        # log_info("Polling SensorPush for latest samples...")
        try:
            print_debug(f"starting query_samples() for iteration {il}")

            # fetch sensor list and sample data on every iteration
            sensors, samples_per_sensor = query_sensorpush()

            print_debug(f"finished query_samples() for iteration {il}")

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as ex:
            # re-connect to SensorPush and retry once
            # intended for expired session rather than usual exception handling purpose
            log_error(msg_il)
            log_error(f"SensorPush query failed: {type(ex).__name__}: {ex}")
            log_warn("Re-establishing SensorPush connection and retrying once...")
            client.authenticate()
            log_warn("SensorPush re-authentication succeeded.")

            print_debug(f"retrying query_samples() for iteration {il}")

            # retry fetching after re-authentication
            sensors, samples_per_sensor = query_sensorpush()

            print_debug(f"retry query_samples() succeeded for iteration {il}")
        # <<<<< querying samples <<<<<


        # >>>>> uploading samples to InfluxDB >>>>>

        uploaded_count = upload_new_samples(sensors, samples_per_sensor)

        # if there is no records to upload:
        if uploaded_count == 0:
            log(msg_il + "No new SensorPush samples to upload.")
        else:
            log(msg_il + f"Uploaded {uploaded_count} influxdb_record(s).")

        # <<<<< uploading samples to InfluxDB <<<<<

    except Exception as ex:
        log_error(msg_il)
        ex_count += 1
        log_error(f"Error during measurement/upload ({ex_count}/{EX_THRESHOLD}): {type(ex).__name__}: {ex}")
        # raise # for debug
        if ex_count >= EX_THRESHOLD:
            log_error("Exception threshold reached. Raising to supervisor.")
            raise

    # log_info(f"Sleeping for {INTERVAL} s.")
    time.sleep(INTERVAL_s)
    il += 1