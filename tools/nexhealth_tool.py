from datetime import datetime
import os
import requests
import time
from typing import List, Optional, Union
from pydantic import BaseModel, Field


class GetAvailableSlotsInput(BaseModel):
    """Input model for checking available appointment slots."""
    start_date: Optional[str] = Field(..., description="The starting date to check for slots, in YYYY-MM-DD format.")
    days: Optional[int] = Field(..., description="The number of days from the start date to check for availability.")
    location_ids: Optional[List[int]] = Field(..., description="A list of location IDs to check.")
    provider_ids: Optional[List[int]] = Field(..., description="A list of provider IDs to check.")


class NexHealthClient:
    """
    Class-based client to manage NexHealth authentication and API calls.
    Use NexHealthClient().get_headers() to retrieve a valid Authorization header.
    """
    #config:
    # NH=os.getenv('NEXHEALTH_API_KEY')
    # NEXHEALTH_BASE_URL=os.getenv('NEXHEALTH_BASE_URL')
    # SUBDOMAIN=os.getenv('NEXHEALTH_SUBDOMAIN')

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None,
                 subdomain: Optional[str] = None, token_ttl: int = 3600, session: Optional[requests.Session] = None):
        self.base_url = (base_url or os.getenv('NEXHEALTH_BASE_URL') or "").rstrip('/')
        self.api_key = api_key or os.getenv('NEXHEALTH_API_KEY')
        self.subdomain = subdomain or os.getenv('NEXHEALTH_SUBDOMAIN')
        self.token_ttl = token_ttl
        self.session = session or requests.Session()

        # token cache
        self._token: Optional[str] = None
        self._expires_at: float = 0.0

        if not self.base_url or not self.api_key:
            # allow lazily raising when attempting to authenticate, but initialize guard here
            raise EnvironmentError("Missing NexHealth base URL or API key.")

    def _is_token_valid(self) -> bool:
        return bool(self._token) and (self._expires_at > time.time())

    def authenticate(self) -> None:
        """
        Authenticate against NexHealth and populate internal token cache.
        Raises ConnectionError on network/auth failure.
        """
        auth_url = f"{self.base_url}/authenticates"
        auth_headers = {
            "accept": "application/vnd.Nexhealth+json;version=2",
            "Authorization": self.api_key
        }

        try:
            resp = self.session.post(auth_url, headers=auth_headers)
            resp.raise_for_status()
            data = resp.json()
            bearer_token = data.get("data", {}).get("token")
            if not bearer_token:
                # clear any stale token
                self._token = None
                self._expires_at = 0
                raise ValueError("Failed to retrieve bearer token from NexHealth.")
            self._token = bearer_token
            self._expires_at = time.time() + int(self.token_ttl)
        except requests.exceptions.RequestException as e:
            self._token = None
            self._expires_at = 0
            raise ConnectionError(f"Could not authenticate with NexHealth: {e}")

    def get_headers(self) -> dict:
        """
        Returns headers with a valid Bearer token, authenticating if necessary.
        """
        if self._is_token_valid():
            return {
                "accept": "application/vnd.Nexhealth+json;version=2",
                "Authorization": f"Bearer {self._token}"
            }

        # authenticate and return headers
        self.authenticate()
        return {
            "accept": "application/vnd.Nexhealth+json;version=2",
            "Authorization": f"Bearer {self._token}"
        }

    def get_locations(self) -> Union[str, List[dict]]:
        """Fetches all locations from the NexHealth API and formats them for display."""
        try:
            headers = self.get_headers()
            response = requests.get(f"{self.base_url}/locations", headers=headers)
            response.raise_for_status()
            data = response.json().get("data", [])

            if not data:
                return "No locations found."

            formatted_locations = []
            for institution in data:
                for loc in institution.get("locations", []):
                    address = f"{loc.get('street_address', '')}, {loc.get('city', '')}"
                    formatted_locations.append({
                        "id": loc.get('id'),
                        "name": loc.get('name'),
                        "address": address
                    })

            return formatted_locations
        except Exception as e:
            return f"Error fetching locations: {e}"

    def get_providers(self) -> Union[str, List[dict]]:
        """Fetches providers for the configured subdomain."""
        try:
            headers = self.get_headers()
            params = {"subdomain": self.subdomain, "inactive": "false"}

            response = self.session.get(f"{self.base_url}/providers", headers=headers, params=params)
            response.raise_for_status()
            data = response.json().get("data", [])

            if not data:
                return "No providers found for this location."

            formatted_providers = [
                {
                    "id": p.get('id'),
                    "name": p.get('name'),
                    "specialty": p.get('nexhealth_specialty')
                }
                for p in data
            ]
            return formatted_providers
        except Exception as e:
            return f"Error fetching providers: {e}"

    def get_available_slots(self, input_data: GetAvailableSlotsInput) -> Union[str, List[dict]]:
        """Fetches available appointment slots based on multiple criteria."""
        try:
            headers = self.get_headers()

            # Resolve fallback location/provider lists by calling the corresponding methods
            raw_locations = self.get_locations()
            raw_providers = self.get_providers()

            location_ids = input_data.location_ids if input_data.location_ids is not None else [
                loc['id'] for loc in (raw_locations if isinstance(raw_locations, list) else []) if isinstance(loc, dict)
            ]
            provider_ids = input_data.provider_ids if input_data.provider_ids is not None else [
                prov['id'] for prov in (raw_providers if isinstance(raw_providers, list) else []) if isinstance(prov, dict)
            ]
            start_date = input_data.start_date if input_data.start_date is not None else time.strftime("%Y-%m-%d")
            days = input_data.days if input_data.days is not None else 7

            params = {
                "subdomain": self.subdomain,
                "start_date": start_date,
                "days": days,
                "lids[]": location_ids,
                "pids[]": provider_ids
            }

            response = self.session.get(f"{self.base_url}/appointment_slots", headers=headers, params=params)
            response.raise_for_status()
            data = response.json().get("data", [])

            if not data:
                return "Could not retrieve availability information for the selected criteria."

            results = []
            for item in data:
                pid = item.get('pid')
                lid = item.get('lid')
                slots = item.get('slots', [])
                if slots:
                    results.append({
                        "provider_id": pid,
                        "location_id": lid,
                        "available_slots": [
                            {
                                "start_time": slot.get('time'),
                                "end_time": slot.get('end_time')
                            }
                            for slot in slots
                        ]
                    })
                    
                else:
                    next_date = item.get('next_available_date')
                    results.append({
                        "message": f"For provider {pid} at location {lid}, no slots available. Next available is {next_date}."
                    })

            return results
        except Exception as e:
            return f"Error fetching available slots: {e}"


