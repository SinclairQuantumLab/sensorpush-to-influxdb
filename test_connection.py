"""
SensorPush API connection test script.
This script performs a 2-step authentication flow (authorize -> accesstoken)
to verify if sensors and samples can be retrieved.

Usage:
    python test_connection.py
"""

import requests
import json
import sys

# --- Configuration ---
SP_EMAIL = "sinclairquantumlab@gmail.com"
SP_PASSWORD = "rubidium87"
BASE_URL = "https://api.sensorpush.com/api/v1"
# ---------------------

print("-" * 60)
print("Step 1: Authenticating with SensorPush Cloud...")

# 1) Login: get temporary authorization token
auth_res = requests.post(
    f"{BASE_URL}/oauth/authorize",
    headers={
        "accept": "application/json",
        "Content-Type": "application/json",
    },
    json={
        "email": SP_EMAIL,
        "password": SP_PASSWORD,
    },
    timeout=10,
)
auth_res.raise_for_status()

auth_data = auth_res.json()
authorization_token = auth_data["authorization"]

print("   [OK] Authentication successful.")
print(f"   authorization token:\n{authorization_token}")

print("\nStep 2: Exchanging authorization token for access token...")

# 2) Exchange authorization token for access token
access_res = requests.post(
    f"{BASE_URL}/oauth/accesstoken",
    headers={
        "accept": "application/json",
        "Content-Type": "application/json",
    },
    json={
        "authorization": authorization_token
    },
    timeout=10,
)
access_res.raise_for_status()

access_data = access_res.json()
access_token = access_data["accesstoken"]

print("   [OK] Access token acquired.")
print(f"   access token:\n{access_token}")

print("\nStep 3: Fetching sensor list...")

# 3) Use access token to get sensor list
headers = {
    "accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": access_token,
}

sensors_res = requests.post(
    f"{BASE_URL}/devices/sensors",
    headers=headers,
    json={},
    timeout=10,
)
sensors_res.raise_for_status()

sensors_dict = sensors_res.json()

if not sensors_dict:
    print("   [!] No sensors found in this account.")
else:
    print(f"   [OK] Found {len(sensors_dict)} sensor(s):")
    for sensor_id, info in sensors_dict.items():
        print(f"        - Name: {info.get('name')}, ID: {sensor_id}")

print("\nStep 4: Fetching latest sample(s)...")

# 4) Fetch latest samples
samples_res = requests.post(
    f"{BASE_URL}/samples",
    headers=headers,
    json={"limit": 1},
    timeout=15,
)
samples_res.raise_for_status()

samples_data = samples_res.json()

print("   [OK] Sample data retrieved successfully.")
print("\n--- Latest Sample Preview ---")
print(json.dumps(samples_data, indent=4))

print("-" * 60)
print("RESULT: SensorPush connection test PASSED.")
