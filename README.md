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
- `uv`
- A SensorPush Cloud account
- A SensorPush Gateway configured for cloud access
- An InfluxDB server URL, organization, bucket, and token
- Access to the private `imaq_config` repository used by this app

This repository intentionally does not include the private configuration files
it depends on. The app reads SensorPush and InfluxDB credentials from
`imaq_config/auth.toml`.

## Installation & setup

1. `git clone` this repo.
2. `git clone` the private `imaq_config` repo into this repo's `imaq_config`
   folder.
3. Run `uv sync`.
4. (Optional) To manage the main app with `supervisor`, adjust
   `sensorpush-to-influxdb.conf` for your environment and move it into the
   `supervisor` `conf.d` folder.

The local folder name should be `imaq_config`, and `imaq_config/auth.toml`
should exist before running the scripts.

If the private config repo is named differently on GitHub, clone it locally as
`imaq_config`, for example:

```bash
git clone <private-config-repo-url> imaq_config
```

On Linux, no special `uv` handling is needed beyond the normal `uv sync`.

> On Windows, if `uv` fails with cache, hardlink, or managed-Python errors,
> run:
>
> ```powershell
> powershell -ExecutionPolicy Bypass -File .\repair_uv.ps1
> ```
>
> This recreates `.venv` using a project-local `uv` cache and a project-local
> managed Python install.

## How to run

### Main app

With `uv`:

```bash
uv run main.py
```

or with a virtual environment:

```bash
python main.py
```

The measurement period **`INTERVAL_s` is strongly recommended to be >= 60** because [SensorPush's policy on API call frequency](https://www.sensorpush.com/gateway-cloud-api): 1 call/min.

### Batch relay by specified time range

Use `relay_by_range.py` if data within a specific time range needs to be
(re-)relayed, for example after a power outage or network problem.

Set the time range in `relay_by_range.py` like this:

```python
# >>> app config >>>
START_TIME = "2026-03-13T15:00:00.000Z"
STOP_TIME = "2026-03-13T20:10:00.000Z"
```

Then run:

```bash
uv run relay_by_range.py
```

## Notes

- The main app reads `imaq_config/auth.toml` at startup, so it should be run
  from the project root.
- It only prepares/uploads samples whose `observed` timestamp is newer than the
  earliest last-seen value across the sensors already stored in InfluxDB.
- `main.py` currently raises an error if `INTERVAL_s` is set below `60`.
- If too many exceptions occur, the script raises and lets `supervisor` handle
  restart/recovery.
- SensorPush Gateway Cloud API:
  <https://www.sensorpush.com/gateway-cloud-api>
