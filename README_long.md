# SensorPush → InfluxDB Uploader

A small Python polling script that reads data from SensorPush Cloud and prepares/uploads it to InfluxDB.

It is designed for long-running use under a process supervisor. The script polls SensorPush on a fixed interval, converts units, builds `influxdb_records` as plain dicts, skips samples that were already seen, and raises after a configurable exception threshold so a supervisor can handle restart logic. The current `main.py` polls with `limit=1`, deduplicates using each sensor's `observed` timestamp, and retries once after re-authentication for common request failures. fileciteturn9file0L15-L17 fileciteturn9file0L45-L58 fileciteturn9file0L71-L85 fileciteturn9file0L140-L147

## Project files

- `main.py` — main polling loop
- `sensorpush_client.py` — SensorPush API client and authentication flow
- `supervisor_helper.py` — logging helpers for supervisor-friendly stdout/stderr output

## What it does

- Authenticates to SensorPush Cloud and fetches the latest samples. fileciteturn9file0L7-L12
- Converts SensorPush values into preferred units such as `degC` and `hPa`. fileciteturn9file0L33-L39 fileciteturn9file0L87-L113
- Stores outgoing points as dict-based `influxdb_records` rather than InfluxDB `Point` objects. fileciteturn9file0L63-L65 fileciteturn9file0L77-L85
- Avoids re-uploading the same sample by remembering the most recent `observed` timestamp per sensor. fileciteturn9file0L45-L46 fileciteturn9file0L71-L75 fileciteturn9file0L133-L135
- Retries once after re-authentication for common request-layer failures such as timeouts, connection errors, and HTTP errors. fileciteturn9file0L52-L59

## Quick start

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install requests influxdb-client
```

### 3. Configure credentials and connection settings

Edit `main.py` and set:

- `SP_EMAIL`
- `SP_PASSWORD`
- `INFLUXDB_URL`
- `INFLUXDB_TOKEN`
- `INFLUXDB_ORG`
- `INFLUXDB_BUCKET`

These settings are defined near the top of the script. fileciteturn9file0L7-L12 fileciteturn9file0L19-L29

### 4. Run the script

```bash
python main.py
```

The script starts an infinite polling loop and sleeps for `INTERVAL` seconds between iterations. fileciteturn9file0L15-L17 fileciteturn9file0L147-L147

## Enabling real InfluxDB writes

The current `main.py` has the actual write call commented out for debugging. fileciteturn9file0L130-L131

Uncomment the write line when you are ready to send records to InfluxDB:

```python
INFLUXDB_WRITE_API.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=influxdb_records)
```

Until then, the script still builds `influxdb_records` and updates the in-memory per-sensor timestamp cache, which is useful for testing the dedup logic without writing to the database. fileciteturn9file0L63-L65 fileciteturn9file0L118-L137

## Running under supervisor

This project is meant to play nicely with an external supervisor.

- The script keeps polling forever in a `while True` loop. fileciteturn9file0L48-L49
- It counts exceptions and raises once the configured threshold is reached so the supervisor can restart it. fileciteturn9file0L140-L145
- Logging is separated into stdout/stderr using helper functions from `supervisor_helper.py`. fileciteturn9file0L1-L1 fileciteturn9file0L55-L56 fileciteturn9file0L142-L142

## Notes

- SensorPush is polled with `limit=1`, so the script only asks for the latest sample from each sensor on each pass. fileciteturn9file0L53-L53
- Deduplication state is kept in memory, so restarting the process resets that cache. fileciteturn9file0L45-L46
- More detailed behavior and implementation notes live in the source comments.

## Security

At the moment, credentials are configured directly in the script. Moving them to environment variables or a separate local config file is strongly recommended before broader deployment. The code works; the secrets-in-source habit is the gremlin waiting in the ceiling.
