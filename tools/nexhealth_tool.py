from datetime import datetime
import os
import requests
import time
from typing import List, Optional
from pydantic import BaseModel, Field


token_cache = {
    "token": None,
    "expires_at": 0
}




class GetAvailableSlotsInput(BaseModel):
    """Input model for checking available appointment slots."""
    start_date: Optional[str] = Field(..., description="The starting date to check for slots, in YYYY-MM-DD format.")
    days: Optional[int] = Field(..., description="The number of days from the start date to check for availability.")
    location_ids: Optional[List[int]] = Field(..., description="A list of location IDs to check.")
    provider_ids: Optional[List[int]] = Field(..., description="A list of provider IDs to check.")


def get_header():
    """
    Fetches a new bearer token if the current one is invalid or expired.
    Caches the token to reuse it for subsequent requests.
    """

    if token_cache["token"] and token_cache["expires_at"] > time.time():
        bearer_token = token_cache["token"]
        headers = {
            "accept": "application/vnd.Nexhealth+json;version=2",
            "Authorization": f"Bearer {bearer_token}" 
        }
        return headers
    


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
        headers = {
            "accept": "application/vnd.Nexhealth+json;version=2",
            "Authorization": f"Bearer {bearer_token}" # Use the bearer token for API calls
        }
        
        return headers
    except requests.exceptions.RequestException as e:
        # Clear variables on failure
        token_cache["token"] = None
        token_cache["expires_at"] = 0
        raise ConnectionError(f"Could not authenticate with NexHealth: {e}")




def get_locations_func():
    """Fetches all locations from the NexHealth API and formats them for display."""
    try:
        HEADERS= get_header()
        NEXHEALTH_BASE_URL = os.getenv('NEXHEALTH_BASE_URL')
        response = requests.get(f"{NEXHEALTH_BASE_URL}/locations", headers=HEADERS)
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

def get_providers_func():
    """Fetches providers for the static subdomain defined in the .env file."""
    try:
        HEADERS= get_header()
        SUBDOMAIN = os.getenv('NEXHEALTH_SUBDOMAIN')
        NEXHEALTH_BASE_URL = os.getenv('NEXHEALTH_BASE_URL')
        params = {"subdomain": SUBDOMAIN, "inactive": "false"}
        
        response = requests.get(f"{NEXHEALTH_BASE_URL}/providers", headers=HEADERS, params=params)
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

def get_available_slots_func(input_data: GetAvailableSlotsInput):
    """Fetches available appointment slots based on multiple criteria."""
    try:
        HEADERS = get_header()
        SUBDOMAIN = os.getenv('NEXHEALTH_SUBDOMAIN')
        NEXHEALTH_BASE_URL = os.getenv('NEXHEALTH_BASE_URL')
        

        location_ids = input_data.location_ids if input_data.location_ids is not None else [loc['id'] for loc in get_locations_func() if isinstance(loc, dict)]
        provider_ids = input_data.provider_ids if input_data.provider_ids is not None else [prov['id'] for prov in get_providers_func() if isinstance(prov, dict)]
        start_date = input_data.start_date if input_data.start_date is not None else time.strftime("%Y-%m-%d")
        days = input_data.days if input_data.days is not None else 7

        params = {
            "subdomain": SUBDOMAIN,
            "start_date": start_date,
            "days": days,
            "lids[]": location_ids,
            "pids[]": provider_ids
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
                results.append({
                    "provider_id": pid,
                    "location_id": lid,
                    "available_slots": [
                        {
                            "start_time": slot['time'],
                            "end_time": slot['end_time']
                        }
                        for slot in slots
                    ]
                })
                print(results)
            else:
                next_date = item.get('next_available_date')
                results.append(f"For provider {pid} at location {lid}, no slots available. Next available is {next_date}.")

        return results
    except Exception as e:
        return f"Error fetching available slots: {e}"
    
