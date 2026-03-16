"""
Minimal SensorPush API client.

Supports:
- authentication
- sensor list retrieval
- sample queries

This file can also be run directly for a quick connection test.
"""

from typing import Any
import requests

BASE_URL = "https://api.sensorpush.com/api/v1"


class SensorPushClient:
    """
    Minimal client for SensorPush Cloud API.

    This client is intentionally small and only implements the subset of
    SensorPush endpoints used by this app.
    """

    def __init__(self, email: str, password: str) -> None:
        # account credentials for SensorPush Cloud authentication
        self._email: str = email
        self._password: str = password

        # access token obtained after authenticate()
        self._access_token: str | None = None

    # read-only properties
    @property
    def email(self) -> str: """Sensor Push account email address"""; return self._email

    def authenticate(self) -> None:
        """
        Authenticate with SensorPush Cloud.

        SensorPush authentication is a two-step process:
        1) exchange email/password for a temporary authorization token
        2) exchange that authorization token for an access token

        The access token is cached in this client instance and reused by
        subsequent API calls.
        """

        # Step 1: get a temporary authorization token from account credentials
        auth_res = requests.post(
            f"{BASE_URL}/oauth/authorize",
            json={"email": self._email, "password": self._password},
            timeout=10,
        )
        auth_res.raise_for_status()
        authorization_token: str = auth_res.json()["authorization"]

        # Step 2: exchange the temporary authorization token for an access token
        access_res = requests.post(
            f"{BASE_URL}/oauth/accesstoken",
            json={"authorization": authorization_token},
            timeout=10,
        )
        access_res.raise_for_status()
        self._access_token = access_res.json()["accesstoken"]

    def _headers(self) -> dict[str, str]:
        """
        Build authenticated request headers for SensorPush API calls.

        Raises:
            RuntimeError:
                If authenticate() has not been called yet.
        """

        if not self._access_token:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        return {
            "accept": "application/json",
            "Authorization": self._access_token,
            "Content-Type": "application/json",
        }

    def get_sensors(self, timeout: int = 10) -> dict[str, Any]:
        """
        Query sensor metadata from SensorPush.

        Args:
            timeout (int):
                Request timeout in seconds passed to `requests.post()` for the
                SensorPush `/devices/sensors` API call.

        Returns:
            dict[str, Any]:
                Dictionary keyed by sensor id. Each value is a dictionary of
                metadata for that sensor. Typical fields include whether the
                sensor is active, BLE address, battery voltage, calibration
                values, alert settings, device id, display name, RSSI, and
                device type.

                Example structure:
                    {
                        "<sensor_id>": {
                            "active": True,
                            "address": "14:9C:EF:B0:83:C6",
                            "battery_voltage": 3.01,
                            "deviceId": "16987116",
                            "id": "16987116.2874219303900926617",
                            "name": "Sinclair Lab Hallway",
                            "rssi": -73,
                            "type": "HTP.xw",
                            ...
                        },
                        ...
                    }

        Raises:
            requests.exceptions.HTTPError:
                If the SensorPush API returns an error response.
            requests.exceptions.Timeout:
                If the HTTP request exceeds the specified timeout.
        """

        response_json = requests.post(
            f"{BASE_URL}/devices/sensors",
            headers=self._headers(),
            json={},
            timeout=timeout,
        )
        response_json.raise_for_status()
        return response_json.json()

    def get_samples(
        self,
        limit: int | None = 10, # 10 by default (as of 2026/03/15) to explicitly state the default value for sensorpush API query
        sensors: list[str] | None = None,
        start_time: str | None = None,
        stop_time: str | None = None,
        timeout: int = 60,
    ) -> dict[str, Any]:
        """
        Query sample records from SensorPush.

        Args:
            limit (int | None):
                Maximum number of samples per sensor requested from SensorPush. If None,
                the "limit" field is omitted from the request payload.
            sensors (list[str] | None):
                Optional list of sensor ids to restrict the query to specific
                sensors. If None, the "sensors" field is omitted from the
                request payload.
            start_time (str | None):
                Optional lower time bound as an ISO8601 UTC timestamp string.
                Only samples after this time are requested. If None, the
                "startTime" field is omitted from the request payload.
            stop_time (str | None):
                Optional upper time bound as an ISO8601 UTC timestamp string.
                If None, the "stopTime" field is omitted from the request
                payload.
            timeout (int):
                Request timeout in seconds passed to `requests.post()` for the
                SensorPush `/samples` API call.

        Returns:
            dict[str, Any]:
                Parsed JSON response from the SensorPush `/samples` endpoint.

                The returned dictionary typically contains:
                    last_time (str):
                        Timestamp cursor returned by SensorPush, typically used
                        as a reference point for later sample queries.
                    sensors (dict[str, list[dict[str, Any]]]):
                        Mapping from sensor id to a list of sample records for
                        that sensor.
                    status (str):
                        API status string, typically "OK" for successful queries.
                    total_samples (int):
                        Total number of samples included in this response.
                    total_sensors (int):
                        Total number of sensors represented in this response.
                    truncated (bool):
                        Whether the response was truncated by SensorPush.

                Each sample record typically includes measured values and metadata
                such as:
                    - observed
                    - temperature
                    - humidity
                    - dewpoint
                    - vpd
                    - barometric_pressure
                    - altimeter_pressure
                    - altitude
                    - gateways

        Raises:
            requests.exceptions.HTTPError:
                If the SensorPush API returns an error response.
            requests.exceptions.Timeout:
                If the HTTP request exceeds the specified timeout.
        """

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
            timeout=timeout,
        )
        response_json.raise_for_status()
        samples = response_json.json()

        return samples


if __name__ == "__main__":
    import json
    from getpass import getpass
    from pprint import pprint

    # Simple step-by-step manual connection test for quick debugging.
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