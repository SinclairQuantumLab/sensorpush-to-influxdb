# SensorPush-to-InfluxDB Relay

A small Python script that polls SensorPush sensors and uploads new samples to InfluxDB.

It is designed to:

- poll more frequently than the SensorPush measurement interval
- skip duplicate samples using each sensor's `observed` timestamp
- run under `supervisor` with stdout/stderr-friendly logging

## Requirements

- Developed with Python-3.14
- A SensorPush account
- An InfluxDB server url and token

## How to use

### First-time setup

1. Open `main.py` and set your SensorPush and InfluxDB configuration values.
2. Install all the packages main.py and imported scripts require.

### How to run

In terminal `cd` to the app's folder and run the `main.py`. Some examples:

```bash
uv run main.py
```

```bash
activate .venv/bin/activate
python main.py
```

## Notes

- The script polls SensorPush continuously at the configured interval.
- It only prepares/uploads samples whose `observed` timestamp is newer than the last seen value for that sensor.
- If too many exceptions occur, the script raises and lets `supervisor` handle restart/recovery.
- Detailed implementation notes are kept in the code comments.

## Developer's Notes

- Sensor Push Gateway Cloud API: https://www.sensorpush.com/gateway-cloud-api?srsltid=AfmBOopm_qc8vBGBzhOWyyigeyQWjgD0QLlwBF4gnVuUD-_SpZXuGT-M
- Try `pysensorpush` package next time: https://github.com/homeassistant-projects/pysensorpush