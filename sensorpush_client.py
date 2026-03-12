"""
Minimal SensorPush API client.

Supports authentication, sensor list retrieval, and sample queries.
This file can also be run directly for a quick connection test.
"""

from typing import Any
import requests

BASE_URL = "https://api.sensorpush.com/api/v1"


class SensorPushClient:
    """Minimal client for SensorPush Cloud API."""

    def __init__(self, email: str, password: str) -> None:
        self._email: str = email
        self._password: str = password
        self._access_token: str | None = None

    # read-only properties
    @property
    def email(self) -> str: """Sensor Push account email address"""; return self._email

    def authenticate(self) -> None:
        auth_res = requests.post(
            f"{BASE_URL}/oauth/authorize",
            json={"email": self._email, "password": self._password},
            timeout=10,
        )
        auth_res.raise_for_status()
        authorization_token: str = auth_res.json()["authorization"]

        access_res = requests.post(
            f"{BASE_URL}/oauth/accesstoken",
            json={"authorization": authorization_token},
            timeout=10,
        )
        access_res.raise_for_status()
        self._access_token = access_res.json()["accesstoken"]

    def _headers(self) -> dict[str, str]:
        if not self._access_token:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        return {
            "accept": "application/json",
            "Authorization": self._access_token,
            "Content-Type": "application/json",
        }

    def get_sensors(self) -> dict[str, Any]:
        res = requests.post(
            f"{BASE_URL}/devices/sensors",
            headers=self._headers(),
            json={},
            timeout=10,
        )
        res.raise_for_status()
        return res.json()

    def get_samples(
        self,
        limit: int = 1,
        sensors: list[str] | None = None,
        start_time: str | None = None,
        stop_time: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"limit": limit}
        if sensors is not None:
            payload["sensors"] = sensors
        if start_time is not None:
            payload["startTime"] = start_time
        if stop_time is not None:
            payload["stopTime"] = stop_time

        res = requests.post(
            f"{BASE_URL}/samples",
            headers=self._headers(),
            json=payload,
            timeout=15,
        )
        res.raise_for_status()
        return res.json()


if __name__ == "__main__":
    import json
    from getpass import getpass

    print("-" * 60)
    print("SensorPush connection test")

    email = input("SensorPush email: ").strip()
    password = getpass("SensorPush password: ").strip()

    try:
        client = SensorPushClient(email, password)

        print("\nStep 1: Authenticating...")
        client.authenticate()
        print("   [OK] Authentication succeeded.")

        print("\nStep 2: Fetching sensor list...")
        sensors = client.get_sensors()
        print(f"   [OK] Found {len(sensors)} sensor(s).")

        for sensor_id, info in sensors.items():
            print(f"      - Name: {info.get('name')}, ID: {sensor_id}")

        print("\nStep 3: Fetching latest sample...")
        samples = client.get_samples(limit=1)
        print("   [OK] Sample fetch succeeded.")
        print(json.dumps(samples, indent=2))

        print("-" * 60)
        print("RESULT: SensorPush connection test PASSED.")

    except requests.exceptions.HTTPError as e:
        print(f"   [FAIL] HTTP Error: {e.response.status_code}")
        print(e.response.text)

    except Exception as e:
        print(f"   [FAIL] {e}")