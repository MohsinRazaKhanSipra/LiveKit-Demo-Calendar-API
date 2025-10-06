import os
import requests
import time
from typing import List
from pydantic import BaseModel, Field


token_cache = {
    "token": None,
    "expires_at": 0
}




class GetAvailableSlotsInput(BaseModel):
    """Input model for checking available appointment slots."""
    start_date: str = Field(..., description="The starting date to check for slots, in YYYY-MM-DD format.")
    days: int = Field(..., description="The number of days from the start date to check for availability.")
    location_ids: List[int] = Field(..., description="A list of location IDs to check.")
    provider_ids: List[int] = Field(..., description="A list of provider IDs to check.")


def authenticate_and_get_token():
    """
    Fetches a new bearer token if the current one is invalid or expired.
    Caches the token to reuse it for subsequent requests.
    """
    # Check if a valid, non-expired token exists
    if token_cache["token"] and token_cache["expires_at"] > time.time():
        return token_cache["token"]

    # If not, fetch a new token
    NEXHEALTH_BASE_URL = os.getenv('NEXHEALTH_BASE_URL')
    NEXHEALTH_API_KEY = os.getenv('NEXHEALTH_API_KEY')

    if not NEXHEALTH_BASE_URL or not NEXHEALTH_API_KEY:
        raise EnvironmentError("Missing NexHealth base URL or API key.")

    auth_url = f"{NEXHEALTH_BASE_URL.rstrip('/')}/authenticates"
    auth_headers = {
        "accept": "application/vnd.Nexhealth+json;version=2",
        "Authorization": NEXHEALTH_API_KEY 
    }
    
    try:
        response = requests.post(auth_url, headers=auth_headers)
        response.raise_for_status()
        data = response.json()
        
        bearer_token = data.get("data", {}).get("token")
        if not bearer_token:
            raise ValueError("Failed to retrieve bearer token from NexHealth.")

        # new token and set its expiration time (1 hour from now)
        token_cache["token"] = bearer_token
        token_cache["expires_at"] = time.time() + 3600  # 1 hour
        
        return bearer_token
    except requests.exceptions.RequestException as e:
        # Clear variables on failure
        token_cache["token"] = None
        token_cache["expires_at"] = 0
        raise ConnectionError(f"Could not authenticate with NexHealth: {e}")


def _get_api_details():
    """Fetches bearer token and other necessary details for API calls."""
    NEXHEALTH_BASE_URL = os.getenv('NEXHEALTH_BASE_URL')
    NEXHEALTH_SUBDOMAIN = os.getenv('NEXHEALTH_SUBDOMAIN')

    if not NEXHEALTH_BASE_URL or not NEXHEALTH_SUBDOMAIN:
        raise EnvironmentError("Missing NexHealth URL or Subdomain in .env file.")

    bearer_token = authenticate_and_get_token()
    
    headers = {
        "accept": "application/vnd.Nexhealth+json;version=2",
        "Authorization": f"Bearer {bearer_token}" # Use the bearer token for API calls
    }
    return NEXHEALTH_BASE_URL, headers, NEXHEALTH_SUBDOMAIN



def get_locations_func():
    """Fetches all locations from the NexHealth API and formats them for display."""
    try:
        NEXHEALTH_BASE_URL, HEADERS, _ = _get_api_details()
        response = requests.get(f"{NEXHEALTH_BASE_URL}/locations", headers=HEADERS)
        response.raise_for_status()
        data = response.json().get("data", [])

        if not data:
            return "No locations found."

        formatted_locations = []
        for institution in data:
            for loc in institution.get("locations", []):
                address = f"{loc.get('street_address', '')}, {loc.get('city', '')}"
                formatted_locations.append(
                    f"ID: {loc.get('id')}, Name: {loc.get('name')}, Address: {address}"
                )
        return "\n".join(formatted_locations)
    except Exception as e:
        return f"Error fetching locations: {e}"

def get_providers_func():
    """Fetches providers for the static subdomain defined in the .env file."""
    try:
        NEXHEALTH_BASE_URL, HEADERS, SUBDOMAIN = _get_api_details()
        params = {"subdomain": SUBDOMAIN, "inactive": "false"}
        
        response = requests.get(f"{NEXHEALTH_BASE_URL}/providers", headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json().get("data", [])

        if not data:
            return "No providers found for this location."

        formatted_providers = [
            f"ID: {p.get('id')}, Name: {p.get('name')}, Specialty: {p.get('nexhealth_specialty')}"
            for p in data
        ]
        return "\n".join(formatted_providers)
    except Exception as e:
        return f"Error fetching providers: {e}"

def get_available_slots_func(input_data: GetAvailableSlotsInput):
    """Fetches available appointment slots based on multiple criteria."""
    try:
        NEXHEALTH_BASE_URL, HEADERS, SUBDOMAIN = _get_api_details()
        params = {
            "subdomain": SUBDOMAIN,
            "start_date": input_data.start_date,
            "days": input_data.days,
            "lids[]": input_data.location_ids,
            "pids[]": input_data.provider_ids,
            "overlapping_operatory_slots": "false"
        }
        
        response = requests.get(f"{NEXHEALTH_BASE_URL}/appointment_slots", headers=HEADERS, params=params)
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
                time_slots = ", ".join([slot['time'] for slot in slots])
                results.append(f"For provider {pid} at location {lid}, available slots are: {time_slots}.")
            else:
                next_date = item.get('next_available_date')
                results.append(f"For provider {pid} at location {lid}, no slots available. Next available is {next_date}.")

        return "\n".join(results)
    except Exception as e:
        return f"Error fetching available slots: {e}"