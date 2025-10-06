import os
import sys
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.nexhealth_tool import _get_api_details


load_dotenv(dotenv_path='.env') 


SUBDOMAIN = 'onera-health-demo-practice'
LOCATION_ID = 331668


import requests

def get_patient_details_func(patient_id: int):
    """
    Fetches detailed patient information by ID, including last visited appointment, 
    provider, and upcoming appointments if available.
    """
    try:
        NEXHEALTH_BASE_URL, HEADERS, SUBDOMAIN = _get_api_details()

        params = {
            "subdomain": SUBDOMAIN,
            "include[]": ["last_visited_appointment", "provider", "upcoming_appts"]
        }

        endpoint = f"{NEXHEALTH_BASE_URL}/patients/{patient_id}"
        response = requests.get(endpoint, headers=HEADERS, params=params)
        response.raise_for_status()

        data = response.json().get("data", {})
        patient_data = data if isinstance(data, dict) else {}

        if not patient_data:
            return f"\nNo detailed information found for Patient ID {patient_id}."

        name = patient_data.get('name', 'N/A')

        upcoming_appts = patient_data.get('upcoming_appts', [])
        if upcoming_appts:
            appt_details = []
            for a in upcoming_appts:
                appt_str = f"ID: {a.get('id', 'N/A')} on {a.get('start_time', '')[:10]} at {a.get('start_time', '')[11:16]}"
                provider_info = a.get('provider', {}).get('name')
                if provider_info:
                    appt_str += f" with {provider_info}"
                appt_details.append(appt_str)
            upcoming_str = "\nUpcoming Appointments:\n" + "\n".join(appt_details)
        else:
            upcoming_str = "\nNo upcoming appointments."

        last_visited = patient_data.get('last_visited_appointment')
        if last_visited:
            date = last_visited.get('start_time', '')[:10]
            provider_name = last_visited.get('provider_name', 'N/A')
            last_visited_str = f"\nLast visited on: {date} with provider: {provider_name}."
        else:
            last_visited_str = "\nNo record of a last visited appointment."

        provider = patient_data.get('provider')
        if provider:
            provider_str = f"\nPrimary Provider: {provider.get('name', 'N/A')} (ID: {provider.get('id', 'N/A')})."
        else:
            provider_str = "\nPrimary Provider: N/A."

        formatted_details = [
            f"Patient Name: {name} (ID: {patient_id})",
            provider_str,
            last_visited_str,
            upcoming_str
        ]

        return "\n".join(formatted_details)

    except Exception as e:
        return f"\nError fetching patient details for ID {patient_id}: {e}"



def view_patient_func(name: str, date_of_birth: str = None):
    """Fetches patient details by name, location ID, and optional date of birth."""
    try:
        NEXHEALTH_BASE_URL, HEADERS, SUBDOMAIN = _get_api_details()
        

        params = {
            "subdomain": SUBDOMAIN,
            "location_id": LOCATION_ID,
            "name": name,
            "new_patient": "false",
            "location_strict": "false",
            "sort": "name"
        }
        if date_of_birth:
            params["date_of_birth"] = date_of_birth

   
        endpoint = f"{NEXHEALTH_BASE_URL}/patients"
        
        response = requests.get(endpoint, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json().get("data", {})
        patients = data.get("patients", [])

        if not patients:
            return f"No patient found matching the criteria: Name '{name}'."

        
        formatted_patients = [
            get_patient_details_func(p.get('id'))
            for p in patients
        ]
        return "\n".join(formatted_patients)
    
    except Exception as e:
        return f"Error fetching patient information: {e}"




# results=view_patient_func("John Doe", "1980-01-01")
# results=view_patient_func("Jane Smith")
# results=view_patient_func("Abbi Fett")    
results=view_patient_func("Achaias Tyrell")
print(results)