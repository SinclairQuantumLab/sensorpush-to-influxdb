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
        response_json = requests.post(
            f"{BASE_URL}/devices/sensors",
            headers=self._headers(),
            json={},
            timeout=10,
        )
        response_json.raise_for_status()
        return response_json.json()

    def get_samples(
        self,
        limit: int | None = None,
        sensors: list[str] | None = None,
        start_time: str | None = None,
        stop_time: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if limit is not None:
            payload["limit"] = limit
        if sensors is not None:
            payload["sensors"] = sensors
        if start_time is not None:
            payload["startTime"] = start_time
        if stop_time is not None:
            payload["stopTime"] = stop_time

        response_json = requests.post(
            f"{BASE_URL}/samples",
            headers=self._headers(),
            json=payload,
            timeout=15,
        )
        response_json.raise_for_status()
        samples = response_json.json()

        # print(f"[DEBUG] get_samples sensors={sensors} start_time={start_time}")
        # print(f"[DEBUG] get_samples payload={payload}")
        # print(f"[DEBUG] get_samples response={response_json}")

        return samples


if __name__ == "__main__":
    import json
    from getpass import getpass
    from pprint import pprint

    print("-" * 60)
    print("SensorPush connection test")
    email = input("SensorPush email (if blank, sinclairquantumlab@gmail.com by default): ").strip()
    if email == "":
        email = "sinclairquantumlab@gmail.com"
    password = getpass("SensorPush password: (if blank, use default)").strip()
    if password == "":
        password = "rubidium87"

    client = SensorPushClient(email, password)

    print("\nStep 1: Authenticating...")
    client.authenticate()
    print(" [OK] Authentication succeeded.")

    input("Press Enter to continue...")

    print("\nStep 2: Fetching sensor list...")
    sensors = client.get_sensors()
    print(f" [OK] Found {len(sensors)} sensor(s).")
    pprint(sensors)
    print()

    input("Press Enter to continue...")

    print("\nStep 3: Fetching latest sample...")
    samples = client.get_samples(limit=1)
    print(" [OK] Sample fetch succeeded.")
    pprint(samples)
    print()
    
    example_sensor_id = list(samples["sensors"].keys())[0]
    example_sample = samples["sensors"][example_sensor_id]
    example_record = example_sample[0]
    example_time = example_record["observed"]
    print(f"Example observed time in each record: {example_time} (type: {type(example_time)})")

    print("-" * 60)
    print("RESULT: SensorPush connection test PASSED.")

