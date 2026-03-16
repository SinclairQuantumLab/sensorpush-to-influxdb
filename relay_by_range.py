"""
Relay all SensorPush samples observed within a specified time range to InfluxDB.

This script:
- authenticates to SensorPush Cloud
- queries all samples from all sensors within the given time range
- queries InfluxDB for already-relayed SensorPush timestamps in that same time range
- uploads only the samples not already present in InfluxDB

Notes:
- The time range should be given as ISO8601 UTC timestamp strings.
- This is intended as a backfill / relay script, not a continuous polling loop.
"""

from supervisor_helper import *
import requests
from sensorpush_client import SensorPushClient
from datetime import datetime, timezone

print()
print("----- SensorPush -> InfluxDB ranged relay -----")
print()

# >>> app config >>>
START_TIME = "2026-03-13T15:00:00.000Z"
STOP_TIME = "2026-03-13T20:10:00.000Z"
SAMPLES_LIMIT = 10000

print(f"Requested time range:")
print(f"  start = {START_TIME}")
print(f"  stop  = {STOP_TIME}")
print()
# <<< app config <<<

# >>> load IMAQ config >>>
import tomllib
with open("imaq_config/auth.toml", "rb") as f:
    AUTH = tomllib.load(f)
# <<< load IMAQ config <<<

# >>> SensorPush API connection >>>
print("Authenticating to SensorPush...", end=" ")
client = SensorPushClient(**AUTH["sensorpush"])
client.authenticate()
print("Done.")
print()
# <<< SensorPush API connection <<<

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

def get_existing_relayed_sample_times(start_time: str, stop_time: str) -> dict[str, set[str]]:
    """
    Query InfluxDB for already-relayed SensorPush sample timestamps in the given time range.

    Returns:
        dict[str, set[str]]:
            Mapping from sensor_id to a set of observed timestamp strings already present
            in InfluxDB for that sensor within the requested time range.
    """
    flux = f'''
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: time(v: "{start_time}"), stop: time(v: "{stop_time}"))
  |> filter(fn: (r) => r["_measurement"] == "SensorPush")
  |> keep(columns: ["_time", "sensor_id"])
  |> group(columns: ["sensor_id", "_time"])
  |> first(column: "_time")
'''
    existing_relayed_sample_times = {}
    tables = INFLUXDB_QUERY_API.query(query=flux, org=INFLUXDB_ORG)

    for table in tables:
        for record in table.records:
            sensor_id = record.values.get("sensor_id", None)
            observed = record.get_time()
            if sensor_id is None or observed is None:
                continue

            observed_str = observed.isoformat().replace("+00:00", "Z")
            if sensor_id not in existing_relayed_sample_times:
                existing_relayed_sample_times[sensor_id] = set()
            existing_relayed_sample_times[sensor_id].add(observed_str)

    print_debug(f"existing relayed sensor count={len(existing_relayed_sample_times)}")
    return existing_relayed_sample_times

def query_sensorpush_in_range(start_time: str, stop_time: str) -> tuple[dict[str, any], dict[str, any]]:
    """
    Query SensorPush once for all sensors within the given time range.

    Returns:
        tuple[dict[str, any], dict[str, any]]:
            sensors metadata dictionary, and samples response dictionary.
    """

    # get sensor information first
    sensors = client.get_sensors()

    # query all samples from sensorpush in the specified time range
    samples = client.get_samples(
                start_time=start_time,
                stop_time=stop_time,
                limit=SAMPLES_LIMIT,
                timeout=60,
            )

    print_debug(f"queried sensors count={len(sensors)}")
    print_debug(f"sample response total_sensors={samples.get('total_sensors')}")
    print_debug(f"sample response total_samples={samples.get('total_samples')}")
    print_debug(f"sample response truncated={samples.get('truncated')}")

    return sensors, samples

def upload_new_samples_in_range(
    sensors: dict[str, any],
    samples: dict[str, any],
    existing_relayed_sample_times: dict[str, set[str]],
) -> int:
    """
    Convert queried SensorPush samples into InfluxDB records and upload only new ones.

    Returns:
        int:
            Number of InfluxDB records uploaded.
    """

    influxdb_records = []

    print_debug(f"upload_new_samples_in_range sensor_count={len(samples['sensors'])}")

    # >>>>> prepare records to upload to InfluxDB >>>>>

    for sensor_id, records in samples["sensors"].items(): # iterate records over different sensors
        # Retrieve the sensor name from the freshly queried sensors
        # it will raise KeyError if the sensor_id is not found from the queried sensor list
        sensor_name = sensors[sensor_id].get("name", "")

        already_relayed_times = existing_relayed_sample_times.get(sensor_id, set())

        for record in records:
            measured_time = record.get("observed", None)
            if measured_time is None:
                continue

            # skip samples already relayed to InfluxDB
            if measured_time in already_relayed_times:
                continue

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

    INFLUXDB_WRITE_API.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=influxdb_records)
    print_debug(f"INFLUXDB_WRITE_API.write completed for {len(influxdb_records)} record(s)")

    # <<<<< upload to InfluxDB <<<<<

    return len(influxdb_records)
# <<< helper functions <<<


# Main execution
try:
    print("Querying existing relayed timestamps from InfluxDB...")
    existing_relayed_sample_times = get_existing_relayed_sample_times(START_TIME, STOP_TIME)
    print("Done.")
    print()

    print("Querying SensorPush samples in the requested time range...")
    sensors, samples = query_sensorpush_in_range(START_TIME, STOP_TIME)
    print("Done.")
    print()

    uploaded_count = upload_new_samples_in_range(sensors, samples, existing_relayed_sample_times)

    if uploaded_count == 0:
        log("No new SensorPush samples to upload in the requested time range.")
    else:
        log(f"Uploaded {uploaded_count} influxdb_record(s) in the requested time range.")

except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as ex:
    log_error(f"SensorPush query failed: {type(ex).__name__}: {ex}")
    raise

except Exception as ex:
    log_error(f"Error during ranged relay: {type(ex).__name__}: {ex}")
    raise