import os
import requests
from typing import List
from pydantic import BaseModel, Field




# Pydantic Models for Tool Inputs 
class GetProvidersInput(BaseModel):
    """Input model for getting providers, requires a subdomain."""
    subdomain: str = Field(..., description="The subdomain of the institution, obtained from the locations tool.")

class GetAvailableSlotsInput(BaseModel):
    """Input model for checking available appointment slots."""
    subdomain: str = Field(..., description="The subdomain of the institution.")
    start_date: str = Field(..., description="The starting date to check for slots, in YYYY-MM-DD format.")
    days: int = Field(..., description="The number of days from the start date to check for availability.")
    location_ids: List[int] = Field(..., description="A list of location IDs to check.")
    provider_ids: List[int] = Field(..., description="A list of provider IDs to check.")

def get_env_variables():
    """Fetches and validates necessary environment variables."""
    NEXHEALTH_BASE_URL = os.getenv('NEXHEALTH_BASE_URL')
    NEXHEALTH_API_KEY = os.getenv('NEXHEALTH_API_KEY')

    if not NEXHEALTH_BASE_URL or not NEXHEALTH_API_KEY:
        raise EnvironmentError("Missing NexHealth environment variables.")

    HEADERS = {
        "accept": "application/vnd.Nexhealth+json;version=2",
        "Authorization": NEXHEALTH_API_KEY
    }
    return NEXHEALTH_BASE_URL, HEADERS





#tools functions
def get_locations_func():
    """Fetches all locations from the NexHealth API and formats them for display."""
    try:
        NEXHEALTH_BASE_URL, HEADERS= get_env_variables()
        response = requests.get(f"{NEXHEALTH_BASE_URL}/locations", headers=HEADERS)
        response.raise_for_status()
        data = response.json().get("data", [])
   

        if not data:
            return "No locations found.", None

        subdomain = data[0].get("subdomain")

        formatted_locations = []
        for institution in data:
            for loc in institution.get("locations", []):
                address = f"{loc.get('street_address', '')}, {loc.get('city', '')}"
                formatted_locations.append(
                    f"ID: {loc.get('id')}, Name: {loc.get('name')}, City: {loc.get('city')}, Address: {address}"
                )

        return "\n".join(formatted_locations), subdomain
    except requests.exceptions.RequestException as e:
        return f"Error fetching locations: {e}", None

def get_providers_func(input_data: GetProvidersInput):
    """Fetches providers for a given subdomain."""
    params = {"subdomain": input_data.subdomain, "inactive": "false"}
    NEXHEALTH_BASE_URL, HEADERS= get_env_variables()
    try:
        response = requests.get(f"{NEXHEALTH_BASE_URL}/providers", headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json().get("data", [])

        if not data:
            return "No providers found for this location."

        formatted_providers = []
        for p in data:
            formatted_providers.append(
                f"ID: {p.get('id')}, Name: {p.get('name')}, NPI No.: {p.get('npi')}, Specialty: {p.get('nexhealth_specialty')}"
            )

        return "\n".join(formatted_providers)
    except requests.exceptions.RequestException as e:
        return f"Error fetching providers: {e}"

def get_available_slots_func(input_data: GetAvailableSlotsInput):
    """Fetches available appointment slots based on multiple criteria."""
    params = {
        "subdomain": input_data.subdomain,
        "start_date": input_data.start_date,
        "days": input_data.days,
        "lids[]": input_data.location_ids,
        "pids[]": input_data.provider_ids,
        "overlapping_operatory_slots": "false"
    }
    NEXHEALTH_BASE_URL, HEADERS= get_env_variables()
    try:
        response = requests.get(f"{NEXHEALTH_BASE_URL}/appointment_slots", headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json().get("data", [])

        if not data:
            return "Could not retrieve availability information."

        results = []
        for item in data:
            pid = item.get('pid')
            lid = item.get('lid')
            slots = item.get('slots', [])
            if slots:
            
                time_slots = ", ".join(
                    f"{slot['time']} - {slot['end_time']}" for slot in slots
                )
                results.append(f"For provider {pid} at location {lid}, available slots are: {time_slots}.")
            else:
                next_date = item.get('next_available_date')
                results.append(f"For provider {pid} at location {lid}, no slots are available. The next available date is {next_date}.")

        return "\n".join(results) if results else "No available slots found for the selected criteria."
    except requests.exceptions.RequestException as e:
        return f"Error fetching available slots: {e}"