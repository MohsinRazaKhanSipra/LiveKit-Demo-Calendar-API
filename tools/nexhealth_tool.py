import os
from dotenv import load_dotenv
import requests
import time
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime, timedelta


#load enviroment
load_dotenv()



class GetAvailableSlotsInput(BaseModel):
    """Input model for checking available appointment slots."""
    start_date: Optional[str] = Field(
        default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d"),
        description="The starting date to check for slots, in YYYY-MM-DD format."
    )
    days: Optional[int] = Field(7, description="The number of days from the start date to check for availability.")
    location_ids: Optional[List[int]] = Field(None, description="A list of location IDs to check.")
    provider_ids: Optional[List[int]] = Field(None, description="A list of provider IDs to check.")



class NexHealthClient:
    """
    Class-based client to manage NexHealth authentication and API calls.
    Use NexHealthClient().get_headers() to retrieve a valid Authorization header.
    """
    global NEXHEALTH_API_KEY, NEXHEALTH_BASE_URL, SUBDOMAIN
    #config:
    NEXHEALTH_API_KEY =os.getenv('NEXHEALTH_API_KEY')
    NEXHEALTH_BASE_URL=os.getenv('NEXHEALTH_BASE_URL')
    SUBDOMAIN=os.getenv('NEXHEALTH_SUBDOMAIN')

    def __init__(self):
   
    
        self._token: Optional[str] = None
        self._expires_at: float = 0.0
        self.authenticate()

        if not NEXHEALTH_BASE_URL or not NEXHEALTH_API_KEY:
           
            raise EnvironmentError("Missing NexHealth base URL or API key.")

    def _is_token_valid(self) -> bool:
        return bool(self._token) and (self._expires_at > time.time())

    def authenticate(self) -> None:
        """
        Authenticate against NexHealth and populate internal token cache.
        Raises ConnectionError on network/auth failure.
        """
        auth_url = f"{NEXHEALTH_BASE_URL}/authenticates"
        auth_headers = {
            "accept": "application/vnd.Nexhealth+json;version=2",
            "Authorization": NEXHEALTH_API_KEY
        }

        try:
            resp = requests.post(auth_url, headers=auth_headers)
            resp.raise_for_status()
            data = resp.json()
            bearer_token = data.get("data", {}).get("token")
            if not bearer_token:
                self._token = None
                self._expires_at = 0
                raise ValueError("Failed to retrieve bearer token from NexHealth.")
            self._token = bearer_token
            self._expires_at = time.time() + 3600 # 1 hour expiry 
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

       
        self.authenticate()
        return {
            "accept": "application/vnd.Nexhealth+json;version=2",
            "Authorization": f"Bearer {self._token}"
        }

    def get_locations(self) -> Union[str, List[dict]]:
        """Fetches all locations from the NexHealth API and formats them for display.

        Args:
            None
        """
        try:
            headers = self.get_headers()
            response = requests.get(f"{NEXHEALTH_BASE_URL}/locations", headers=headers)
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
        """Fetches providers for the configured subdomain and returns a formatted list.

        Args:
            None
        """
        try:
            headers = self.get_headers()
            params = {"subdomain": SUBDOMAIN, "inactive": "false", "include[]": "appointment_types"}

            response = requests.get(f"{NEXHEALTH_BASE_URL}/providers", headers=headers, params=params)
            response.raise_for_status()
            data = response.json().get("data", [])

            if not data:
                return "No providers found for this location."

            formatted_providers = [
                {
                    "id": p.get('id'),
                    "name": p.get('name'),
                    "specialty": p.get('nexhealth_specialty'),
                    "appointment_types": [x['name'] for x in p['availabilities'][0]['appointment_types']]
                }
                for p in data
            ]
            print(formatted_providers[0])
            return formatted_providers
        except Exception as e:
            return f"Error fetching providers: {e}"

    def get_available_slots(self, input_data: GetAvailableSlotsInput) -> Union[str, List[dict]]:
        """Fetches available appointment slots based on multiple criteria.

        Args:
            input_data (GetAvailableSlotsInput): Model containing:
                - start_date (str, optional): YYYY-MM-DD start date to search from.
                - days (int, optional): Number of days from start_date to include.
                - location_ids (List[int], optional): Specific location IDs to filter.
                - provider_ids (List[int], optional): Specific provider IDs to filter.
        """
        try:
            headers = self.get_headers()

            
        
            if input_data.location_ids is not None:
                location_ids = input_data.location_ids
            else:
                raw_locations = self.get_locations()
                location_ids = [
                loc['id']
                for loc in (raw_locations if isinstance(raw_locations, list) else [])
                if isinstance(loc, dict) and 'id' in loc
                ]

            if input_data.provider_ids is not None:
                provider_ids = input_data.provider_ids
            else:
                raw_providers = self.get_providers()
                provider_ids = [
                prov['id']
                for prov in (raw_providers if isinstance(raw_providers, list) else [])
                if isinstance(prov, dict) and 'id' in prov
                ]
            start_date = input_data.start_date if input_data.start_date is not None else time.strftime("%Y-%m-%d")
            days = input_data.days if input_data.days is not None else 7

            params = {
                "subdomain": SUBDOMAIN,
                "start_date": start_date,
                "days": days,
                "lids[]": location_ids,
                "pids[]": provider_ids
            }

            response = requests.get(f"{NEXHEALTH_BASE_URL}/appointment_slots", headers=headers, params=params)
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
        


    def search_patients(self, name: str, phone_number: str, date_of_birth: str, location_id: int) -> Union[str, List[dict]]:
        """Searches the patient by dob first then using the filter like name and mobile we get patients

        Args:
            name (str): Full patient name to match (case-insensitive).
            phone_number (str): Phone number to verify against patient record.
            date_of_birth (str): Patient DOB in YYYY-MM-DD format.
            location_id (int): Location ID to restrict the search to.
        """
        try:
            headers = self.get_headers()
            

            params = {
                "subdomain": SUBDOMAIN,
                "date_of_birth": date_of_birth, 
                "location_id": location_id
            }


            endpoint = f"{NEXHEALTH_BASE_URL}/patients"

            response = requests.get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            data = response.json().get("data", {})
            patients = data.get("patients", [])

            
            if patients: 
                result_patient=[]
                for patient in patients:
                    if patient.get('name').lower() == name.lower():
                        if patient['bio']['phone_number'] == phone_number:
                            result_patient.append({
                                'id': patient['id'],
                                'name': patient['name'],
                                'phone': patient['bio']['phone_number'],
                                'status': 'verified patient'
                            })
                            
                        else:
                            result_patient.append({
                                'id': patient['id'],
                                'name': patient['name'],
                                'phone': patient['bio'].get('phone_number'),
                                'status': 'number not verified'
                            })

                if result_patient:
                    return result_patient
                else:
                    return "no patient found"

            
            return "no patient found"

        
        except Exception as e:
            return f"Error fetching patient information: {e}"
        



        
    def view_appointment(self, appointment_id: Optional[int] = None, location_id: int = None, days: Optional[int]=10) -> Union[str, dict, List[dict]]:
        """Retrieve appointments for a time window or a single appointment by ID.

        Args:
            appointment_id (Optional[int]): If provided, return only this appointment ID.
            location_id (int): Location ID to filter appointments (can be None).
            days (Optional[int]): Number of days from now to include in the range (default 10).
        """
       
        if appointment_id is not None and not isinstance(appointment_id, int):
            return "appointment_id must be an integer"

        now = datetime.utcnow()
        start = now.strftime("%Y-%m-%dT%H:%M:%S+0000")
        end_dt = now + timedelta(days=days)
        end = end_dt.strftime("%Y-%m-%dT%H:%M:%S+0000")
        print(end)

        params = {"subdomain": SUBDOMAIN, "start": start, "end": end, "location_id": location_id}
        url = f"{NEXHEALTH_BASE_URL}/appointments"

        try:
            headers = self.get_headers()
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            payload = resp.json()
            data = payload.get("data", [])


            if appointment_id is not None:
                for appt in data:
                    if appt.get("id") == appointment_id:
                        result_single_appt={
                                'id': appt['id'],
                                'start_time': appt['start_time'],
                                'end_time': appt['end_time'],
                                'appointment_type_id': appt['appointment_type_id']
                            }
                        return result_single_appt
                return f"No appointment found with id {appointment_id} in the requested range."

            result=[]
            for appt in data:
                result.append({
                    'id': appt['id'],
                    'start_time': appt['start_time'],
                    'end_time': appt['end_time'],
                    'appointment_type_id': appt['appointment_type_id']
                })
            return result

        except requests.exceptions.RequestException as e:
            return f"Error fetching appointments: {e}"
        except Exception as e:
            return f"Unexpected error fetching appointments: {e}"
        



    def create_patient(
        self,
        provider_id: int,
        first_name: str,
        last_name: str,
        email: str,
        phone_number: str,
        date_of_birth: str,
        location_id: int
    ) -> Dict[str, Any]:
        """
        Creates a new patient in the NexHealth system.
        Returns simplified patient details or raises an error.
        """
        try:
            headers = self.get_headers()
            headers["content-type"] = "application/json"
            
            payload = {
                "provider": {"provider_id": provider_id},
                "patient": {
                    "bio": {
                        "phone_number": phone_number,
                        "date_of_birth": date_of_birth
                    },
                    "email": email,
                    "last_name": last_name,
                    "first_name": first_name
                }
            }
            
            url = f"{NEXHEALTH_BASE_URL}/patients?subdomain={SUBDOMAIN}&location_id={location_id}"
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json().get("data", {}).get("user", {})
            
            return {
                "id": data.get("id"),
                "email": data.get("email"),
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "name": data.get("name"),
                "phone_number": data.get("bio", {}).get("phone_number"),
                "date_of_birth": data.get("bio", {}).get("date_of_birth"),
                "created_at": data.get("created_at"),
                "location_ids": data.get("location_ids", [])
            }
        
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Error creating patient: {e}")
        



client=NexHealthClient()
# result=client.search_patients("Achaias Tyrell","4692696088","1983-01-31", 331668)
# print("------------ Test 1 -----------")
# print('("Achaias Tyrell","4692696088","1983-01-31", 331668)')
# print(result)
# print("\n\n")

# #Appointment related question prompts
#         #name
#         #dob
#         #telephone



# print("------------ Test 2 -----------")
# print('("ACHAIAS Tyrell","4692696088","1983-01-31", 331668)')
# result=client.search_patients("ACHAIAS Tyrell","4692696088","1983-01-31", 331668)
# print(result)
# print("\n\n")

# print("------------ Test 3 -----------")
# print('("Achaias Tyrell","3692696088","1983-01-31", 331668)')
# result=client.search_patients("Achaias Tyrell","3692696088","1983-01-31", 331668)
# print(result)
# print("\n\n")


# print("------------ Test 4 -----------")
# print('("Achaias Tyrell","4692696088","2000-01-30", 331668)')
# result=client.search_patients("Achaias Tyrell","4692696088","2000-01-30", 331668)
# print(result)
# print("\n\n")



# print("------------ Test 5 -----------")
# print('("Achaias Tyrell","4692696088","2000-01-30", 331668)')
# result=client.search_patients("Mohsin Tyrell","4692696088","1983-01-31", 331668)
# print(result)
# print("\n\n")






# print("------------ get_available_slots() -----------")
# input_data=GetAvailableSlotsInput(
#             # start_date="2025-10-16",
#             # days=1,
#             # location_ids=[331668],
#             # provider_ids=[413326781]
#         )
# result=client.get_available_slots(input_data)
# print(result)
# print("\n\n")

# print(client.view_appointment(1036290875))

# print(client.view_appointment(1029645607, location_id=331668))

# print(client.view_appointment(location_id=331668))



print("------------- create_patient() --------------")
result=client.create_patient(
    provider_id=413326781,
    first_name="First3343Name",
    last_name="Last324Name",
    email="example@exadmple1.com",
    phone_number="3292696088",
    date_of_birth="1990-01-01",
    location_id=331668
)
print(result)

# print(client.view_appointment(location_id=331668, days=30))