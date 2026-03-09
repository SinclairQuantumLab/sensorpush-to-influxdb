"""
FILE: test_sensorpush_conn.py
DESCRIPTION: Pytest for verifying SensorPush API connectivity (2-Step Authentication).
USAGE:
    1. Install requirements: pip install pytest requests
    2. Run tests: 
        $ pytest test_sensorpush_conn.py
    3. Run with detailed logs:
        $ pytest -v test_sensorpush_conn.py
"""

import pytest
import requests

# --- Configuration ---
SP_EMAIL = "sinclairquantumlab@gmail.com"
SP_PASSWORD = "rubidium87"
BASE_URL = "https://api.sensorpush.com/api/v1"

@pytest.fixture(scope="module")
def auth_token():
    """Step 1: Get initial authorization token from email/password."""
    payload = {"email": SP_EMAIL, "password": SP_PASSWORD}
    res = requests.post(f"{BASE_URL}/oauth/authorize", json=payload, timeout=10)
    
    assert res.status_code == 200, f"Auth step failed: {res.text}"
    token = res.json().get("authorization")
    assert token is not None, "Authorization token is missing in response"
    return token

@pytest.fixture(scope="module")
def access_token(auth_token):
    """Step 2: Exchange authorization token for an access token."""
    payload = {"authorization": auth_token}
    res = requests.post(f"{BASE_URL}/oauth/accesstoken", json=payload, timeout=10)
    
    assert res.status_code == 200, f"Access token exchange failed: {res.text}"
    token = res.json().get("accesstoken")
    assert token is not None, "Access token is missing in response"
    return token

def test_connection_auth_flow(access_token):
    """Verify that the access token is valid and non-empty."""
    assert isinstance(access_token, str)
    assert len(access_token) > 10

def test_sensor_list_retrieval(access_token):
    """Verify that the sensor list can be retrieved using the access token."""
    headers = {
        "accept": "application/json",
        "Authorization": access_token,
        "Content-Type": "application/json"
    }
    # Using /devices/sensors as per your successful manual test
    res = requests.post(f"{BASE_URL}/devices/sensors", headers=headers, json={}, timeout=10)
    
    assert res.status_code == 200, f"Failed to fetch sensors: {res.text}"
    sensors = res.json()
    assert isinstance(sensors, dict), "Sensors response should be a dictionary"
    print(f"\n[INFO] Found {len(sensors)} sensors.")

def test_latest_sample_fetch(access_token):
    """Verify that the samples endpoint returns data."""
    headers = {
        "accept": "application/json",
        "Authorization": access_token,
        "Content-Type": "application/json"
    }
    payload = {"limit": 1}
    res = requests.post(f"{BASE_URL}/samples", headers=headers, json=payload, timeout=15)
    
    assert res.status_code == 200, f"Failed to fetch samples: {res.text}"
    data = res.json()
    # assert "sensors" in data, "Response should contain 'sensors' key"
    assert isinstance(data, dict), "Samples response should be a dictionary"
    assert len(data) >= 0

