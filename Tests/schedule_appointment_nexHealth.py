from datetime import datetime
import os
import sys
import requests
from dotenv import load_dotenv
import requests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.nexhealth_tool import _get_api_details


load_dotenv(dotenv_path='.env') 


SUBDOMAIN = os.getenv('NEXHEALTH_SUBDOMAIN')
LOCATION_ID = os.getenv('NEXHEALTH_TEST_LOCATION_ID')



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

        if response.status_code == 201:
            data = response.json()
            appt = data.get("data", {}).get("appt", {})
            provider_name = appt.get("provider_name", "N/A")
            appt_time = appt.get("start_time", "N/A")
            operatory = appt.get("operatory_id", "N/A")
            note = appt.get("note", "")

            return (
                f"\nAppointment Created Successfully!\n"
                f"Appointment ID: {appt.get('id', 'N/A')}\n"
                f"Patient ID: ({appt.get('patient_id', 'N/A')})\n"
                f"Provider: {provider_name} (ID: {appt.get('provider_id', 'N/A')})\n"
                f"Start Time: {appt_time}\n"
                f"Operatory ID: {operatory}\n"
                f"Note: {note if note else 'No notes.'}"
            )
        elif response.status_code == 400:

            error_info = response.json()
            error_msg = error_info.get("error")[0]
           
            if "slot" in error_msg.lower() or "availability" in error_msg.lower():
                slot_msg = "\nNo slot available at the requested time. Please choose a different time."
            else:
                slot_msg = ""
           
            return (f"\nBad Request: The server could not process your request.\n"
                    f"{slot_msg}\n"
                    f"Details: {error_msg}")
        
        elif response.status_code == 401:
            return (
            "\nUnauthorized: Your API credentials are invalid or missing.\n"
            "Please verify your authentication details."
            )
        elif response.status_code == 403:
            return (
            "\nForbidden: You do not have permission to create this appointment.\n"
            "Contact your administrator if you believe this is an error."
            )
        elif response.status_code == 404:
            return (
            "\nNot Found: The requested resource could not be found.\n"
            "Please check the patient, provider, or operatory IDs."
            )
        elif response.status_code == 500:
            return (
            "\nInternal Server Error: Something went wrong on the server.\n"
            "Please try again later or contact support if the issue persists."
            )
        else:
            return (
            f"\nUnexpected Error: Error creating appointment.\n")
    except Exception as e:
        return f"\nError creating appointment. exception: {e}"



def cancel_appointment_func(appointment_id: int) -> str:
    """
    Cancels an appointment via a PATCH request.
    If the appointment is already cancelled, it returns a success message
    and avoids throwing an error that stops the reschedule process.
    """
    try:
        NEXHEALTH_BASE_URL, HEADERS, SUBDOMAIN = _get_api_details()
        endpoint = f"{NEXHEALTH_BASE_URL}/appointments/{appointment_id}"
        params = {"subdomain": SUBDOMAIN}
        payload = {"appt": {"cancelled": True}}

        response = requests.patch(endpoint, headers=HEADERS, params=params, json=payload)
        
        if response.status_code == 200:
            data = response.json().get("data", {}).get("appt", {})
         
            is_cancelled = data.get('cancelled')
            
            status = "Cancelled" if is_cancelled else "Not Cancelled"
            
            
            
            return (
                f"\nAppointment {status} Successfully!\n"
                f"Appointment ID: {data.get('id', 'N/A')}"
            )

        elif response.status_code == 400:
   
            error_info = response.json()
            error_list = error_info.get("error", [])
            already_cancelled_msg = "Cannot update appointment because it is not synced with the PMS and/or a live client"
            
            if already_cancelled_msg in error_list and not error_info.get("code", True):
                 
                 return f"\nAppointment ID {appointment_id} is **already cancelled** or cannot be updated, but proceeding with new appointment creation for reschedule."
            
            error_msg = error_list[0] if error_list else f"Error: {response.text}"
            return f"\nError: Bad Request received for appointment {appointment_id}. Details: {error_msg}"

        else:
      
            return f"\nError: Received status code {response.status_code} while updating appointment {appointment_id}. Details: {response.text}"

    except Exception as e:
        return f"\nAn exception occurred while updating appointment ID {appointment_id}: {e}"
    
    
    
def reschedule_appointment_func(appointment_id: int, patient_id: int, provider_id: int, new_start_time: str, operatory_id: int = None) -> str:
    """
    Reschedules an appointment by cancelling the old one and creating a new one.
    It will proceed to create a new appointment even if the cancellation
    response indicates the original appointment was already cancelled.

    :param appointment_id: The ID of the original appointment to cancel.
    :param patient_id: The ID of the patient.
    :param provider_id: The ID of the provider for the new appointment.
    :param new_start_time: The new start time for the rescheduled appointment (e.g., "YYYY-MM-DDTHH:MM:SSTZ").
    :param operatory_id: (Optional) The ID of the operatory for the new appointment.
    :return: A string summarizing the results of both cancellation and creation.
    """
 
    cancel_result = cancel_appointment_func(appointment_id)
    
 
    if "Error:" in cancel_result and "**already cancelled**" not in cancel_result:
        error_message = (
            f"Failed to cancel the original appointment (ID: {appointment_id}). "
            f"Reschedule process stopped.\n"
            f"Reason: {cancel_result}"
        )
        return error_message

  
    print(f"Original appointment cancellation attempt complete. Result:\n{cancel_result.strip()}")
    print("\nAttempting to create the new appointment...")
    

    new_appointment_result = create_appointment_func(
        patient_id=patient_id,
        provider_id=provider_id,
        start_time=new_start_time,
        operatory_id=operatory_id
    )

 
    final_summary = (
        f"Reschedule Summary \n"
        f"Original Appointment (ID: {appointment_id}) Cancellation:\n{cancel_result.strip()}\n"
        f"-----------------------------\n"
        f"New Appointment Creation:\n{new_appointment_result.strip()}"
    )
    
    return final_summary


# new appointment
#-----------------
# new_appointment_result = create_appointment_func(
#     patient_id=413326833,
#     provider_id=413326781,
#     start_time="2025-10-24T15:06:10+0000",
#     operatory_id=199997
# )
# print(new_appointment_result)


# cancelling an appointment
#-----------------
# print(cancel_appointment_func(1036299820))


# Rescheduling an appointment
#-----------------
reschedule_outcome = reschedule_appointment_func(
    appointment_id=10362796433,
    patient_id=413326833,
    provider_id=413326781,
    new_start_time="2025-10-24T15:06:10+0000", 
    operatory_id=199997
)
print(reschedule_outcome)



# results=view_patient_func("John Doe", "1980-01-01")
# results=view_patient_func("Jane Smith")
# results=view_patient_func("Abbi Fett")    
# results=view_patient_func("achaias Tyrell", "1983-01-31")
# print(results)



