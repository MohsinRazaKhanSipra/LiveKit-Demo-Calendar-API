import os
import sys
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.nexhealth_tool import _get_api_details


load_dotenv(dotenv_path='.env') 


SUBDOMAIN = os.getenv('NEXHEALTH_SUBDOMAIN')
LOCATION_ID = os.getenv('NEXHEALTH_TEST_LOCATION_ID')


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
        print(params)
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







def create_appointment_func(patient_id: int, provider_id: int, start_time: str, operatory_id: int = None) -> str:
    """
    Creates a new appointment for a patient.
    
    :param patient_id: The ID of the patient.
    :param provider_id: The ID of the provider for the appointment.
    :param start_time: The start time of the appointment (e.g., "YYYY-MM-DDTHH:MM:SSTZ").
    :param operatory_id: (Optional) The ID of the operatory/room for the appointment.
    :return: A success or error message.
    """
    try:
     
        NEXHEALTH_BASE_URL, HEADERS, SUBDOMAIN = _get_api_details()

     
        params = {
            "subdomain": SUBDOMAIN,
            "location_id": LOCATION_ID
        }

        
        payload = {
            "appt": {
                "patient_id": patient_id,
                "provider_id": provider_id,
                "start_time": start_time,
                "operatory_id": operatory_id,
            }
        }
        
  
        endpoint = f"{NEXHEALTH_BASE_URL}/appointments"
        
    
        response = requests.post(
            endpoint, 
            headers=HEADERS, 
            params=params, 
            json=payload 
        )
        
        response.raise_for_status() 
        
    
        data = response.json()
        new_appt_id = data.get("data", {}).get("id", "N/A")

        return f"\nSuccessfully created new appointment (ID: {new_appt_id}) for Patient ID {patient_id}."

    except requests.exceptions.HTTPError as e:

        error_details = e.response.text if e.response is not None else "No response body."
        return f"\nHTTP Error creating appointment: {e}\nDetails: {error_details}"
    except Exception as e:
        return f"\nError creating appointment: {e}"




new_appointment_result = create_appointment_func(
    patient_id=413326833,
    provider_id=413326781,
    start_time="2025-10-08T13:06:10+0000",
    operatory_id=199997
)
print(new_appointment_result)



# results=view_patient_func("John Doe", "1980-01-01")
# results=view_patient_func("Jane Smith")
# results=view_patient_func("Abbi Fett")    
# results=view_patient_func("achaias Tyrell", "1983-01-31")
# print(results)



