# SensorPush-to-InfluxDB Relay

A small Python app that relays SensorPush Cloud samples to InfluxDB.

It is designed to:

- poll SensorPush at a fixed interval
- avoid re-relaying samples already stored in InfluxDB
- store SensorPush measurements in InfluxDB with a simple, consistent schema
- run under `supervisor` with stdout/stderr-friendly logging
- support backfilling a specified time range with a separate script

## Requirements

- Python 3.14
- A SensorPush Cloud account
- A SensorPush Gateway configured for cloud access
- An InfluxDB server URL, organization, bucket, and token
- The local helper modules used by this repo:
  - `sensorpush_client.py`
  - `supervisor_helper.py`

## Installation & setup

1. `git clone` this repo and run `uv sync`.
2. `git clone` `imaq-config` repo in this repo's `imaq-config` folder.
3. (Optional) To manage the main app with `supervisor`, set `sensorpush-to-influxdb.conf` `supervisor` configuration file accordingly and move it to teh `supervisor`'s `conf.d` folder.

## How to run

### Main app

With `uv`:

```bash
uv run main.py
```

or with a virtual environment:

```bash
source .venv/bin/activate
python main.py
```

### Batch relay by specified time range

Use `relay_by_range.py` if data within a specifit range of time needs to be (re-)relayed (e.g., for SensorPush samples saved in the sensor that are not relayed to InfluxDB due to power outtages or network error).

Set the time range in `relay_by_range.py` like this:

```python
# >>> app config >>>
START_TIME = "2026-03-13T15:00:00.000Z"
STOP_TIME = "2026-03-13T20:10:00.000Z"
```

## Developer's Notes

- [Sensor Push Gateway Cloud API](https://www.sensorpush.com/gateway-cloud-api?srsltid=AfmBOopm_qc8vBGBzhOWyyigeyQWjgD0QLlwBF4gnVuUD-_SpZXuGT-M)

- It only prepares/uploads samples whose `observed` timestamp is newer than the earilest last seen value across the sensors.

- If too many exceptions occur, the script raises and lets `supervisor` handle restart/recovery.

- Detailed implementation notes are kept in the code comments.

- It might be worth taking a look into [`pysensorpush`](https://github.com/homeassistant-projects/pysensorpush) package.
