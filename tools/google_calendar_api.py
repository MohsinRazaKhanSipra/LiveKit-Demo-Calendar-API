import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from google_auth_oauthlib.flow import InstalledAppFlow 
from typing import List, Optional
import json
import os

logger = logging.getLogger("google-calendar-api")
logger.setLevel(logging.INFO)

SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.readonly'
]


SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_access_token():
    flow = InstalledAppFlow.from_client_secrets_file(
        r'secrets\google_client_secret.json',  # Path to your client_secret.json
        SCOPES
    )
    creds = flow.run_local_server(port=8000)
    print("Access token:", creds.token)
    return creds.token




class CreateEventInput(BaseModel):
    title: str = Field(description="Event title")
    start_datetime: str = Field(description="ISO8601 start datetime")
    end_datetime: str = Field(description="ISO8601 end datetime")
    # FIX 1 (Previous Request): Allowed 'null' for attendees
    attendees: Optional[List[str]] = Field(default=[], description="List of attendee emails")
    description: Optional[str] = Field(default="", description="Event description")
    location: Optional[str] = Field(default="", description="Event location")

class ListEventsInput(BaseModel):
    start_datetime: str = Field(description="ISO8601 start datetime for range")
    end_datetime: str = Field(description="ISO8601 end datetime for range")
    # FIX 2 (New): Allowed 'null' for max_results
    max_results: Optional[int] = Field(default=10, description="Max events to return")

class UpdateEventInput(BaseModel):
# ... (unchanged)
    event_id: Optional[str] = Field(default=None, description="Event ID to update")
    title: Optional[str] = Field(default=None, description="Event title to match")
    start_datetime: Optional[str] = Field(default=None, description="Start datetime to match (ISO8601)")
    event_number: Optional[int] = Field(default=None, description="Event number from list")
    new_title: Optional[str] = Field(default=None, description="New title")
    new_start_datetime: Optional[str] = Field(default=None, description="New start ISO")
    new_end_datetime: Optional[str] = Field(default=None, description="New end ISO")
    new_description: Optional[str] = Field(default=None, description="New description")

class DeleteEventInput(BaseModel):
# ... (unchanged)
    event_id: Optional[str] = Field(default=None, description="Event ID to delete")
    title: Optional[str] = Field(default=None, description="Event title to match")
    start_datetime: Optional[str] = Field(default=None, description="Start datetime to match (ISO8601)")
    event_number: Optional[int] = Field(default=None, description="Event number from list")

def build_service_from_refresh_token(refresh_token):
    # ... (unchanged)
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        scopes=SCOPES
    )
    creds.refresh(Request())
    return build('calendar', 'v3', credentials=creds)

def create_event_func(input: CreateEventInput, refresh_token: str, timezone: str = 'Asia/Karachi') -> str:
    try:
        service = build_service_from_refresh_token(refresh_token)
        # Safely handle Optional[List[str]] being None
        attendees_list = input.attendees if input.attendees is not None else []
        event_body = {
            "summary": input.title,
            "start": {"dateTime": input.start_datetime, "timeZone": timezone},
            "end": {"dateTime": input.end_datetime, "timeZone": timezone},
            "attendees": [{"email": a} for a in attendees_list if "@" in a],
            "description": input.description,
            "location": input.location,
            "conferenceData": {"createRequest": {"requestId": f"meet-{datetime.now().timestamp()}"}} if input.location and input.location.lower() in ["google meet", "online meeting"] else None
        }
        created = service.events().insert(calendarId="primary", body=event_body, conferenceDataVersion=1).execute()
        description = f" Description: {input.description}" if input.description else ""
        return f"Your event is created: {created.get('summary')} at {created['start']['dateTime']}{description}"
    except Exception as e:
        logger.error(f"Error creating event: {str(e)}")
        return f"Error creating event: {str(e) if str(e) else 'Unknown error'}"

def list_events_func(input: ListEventsInput, refresh_token: str) -> str:
    try:
        service = build_service_from_refresh_token(refresh_token)
        # Safely get max_results, defaulting to 10 if None is received
        max_results = input.max_results if input.max_results is not None else 10
        events = service.events().list(
            calendarId='primary',
            timeMin=input.start_datetime,
            timeMax=input.end_datetime,
            maxResults=max_results, # Use the safe value
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        items = events.get('items', [])
        # ... (rest of function unchanged)
        if not items:
            return "No events found."
        result = []
        for idx, e in enumerate(items, 1):
            start = e['start'].get('dateTime', e['start'].get('date'))
            try:
                dt = datetime.fromisoformat(start.replace("Z", ""))
                natural_time = dt.strftime("%I:%M %p, %b %d").lstrip("0").lower()
            except:
                natural_time = start
            result.append({"id": e['id'], "summary": e.get('summary', 'No title'), "start": natural_time})
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error listing events: {str(e)}")
        return f"Error listing events: {str(e) if str(e) else 'Unknown error'}"


def update_event_func(input: UpdateEventInput, refresh_token: str, timezone: str = 'Asia/Karachi') -> str:
    try:
        service = build_service_from_refresh_token(refresh_token)
        if input.event_number and not input.event_id:
            events = service.events().list(
                calendarId='primary',
                timeMin=(datetime.now() - timedelta(days=30)).isoformat() + 'Z',
                timeMax=(datetime.now() + timedelta(days=30)).isoformat() + 'Z',
                maxResults=10,
                singleEvents=True,
                orderBy='startTime'
            ).execute().get('items', [])
            if input.event_number < 1 or input.event_number > len(events):
                return f"Invalid event number: {input.event_number}. Choose between 1 and {len(events)}."
            input.event_id = events[input.event_number - 1]['id']
        if not input.event_id and input.title and input.start_datetime:
            events = service.events().list(
                calendarId='primary',
                timeMin=input.start_datetime,
                timeMax=input.start_datetime,
                q=input.title,
                singleEvents=True,
                maxResults=1
            ).execute().get('items', [])
            if not events:
                return "No event found with that title and time."
            input.event_id = events[0]['id']
        if not input.event_id:
            return "Event ID, event number, or title with time required."
        event = service.events().get(calendarId='primary', eventId=input.event_id).execute()
        if input.new_title:
            event['summary'] = input.new_title
        if input.new_start_datetime:
            event['start'] = {"dateTime": input.new_start_datetime, "timeZone": timezone}
        if input.new_end_datetime:
            event['end'] = {"dateTime": input.new_end_datetime, "timeZone": timezone}
        if input.new_description:
            event['description'] = input.new_description
        updated = service.events().update(calendarId='primary', eventId=input.event_id, body=event).execute()
        return f"Updated event: {updated.get('summary')} at {updated['start']['dateTime']}"
    except Exception as e:
        logger.error(f"Error updating event: {str(e)}")
        return f"Error updating event: {str(e) if str(e) else 'Unknown error'}"

def delete_event_func(input: DeleteEventInput, refresh_token: str) -> str:
    try:
        service = build_service_from_refresh_token(refresh_token)
        event_id = input.event_id
        if not event_id and input.title and input.start_datetime:
            try:
                start_dt = datetime.fromisoformat(input.start_datetime.replace("Z", ""))
                end_dt = start_dt + timedelta(days=1)
            except ValueError as ve:
                return f"Invalid date/time format: {str(ve)}. Please use format like 'Sep 23, 2025 at 6:00 PM'."
            events = service.events().list(
                calendarId='primary',
                timeMin=start_dt.isoformat() + 'Z',
                timeMax=end_dt.isoformat() + 'Z',
                q=input.title,
                singleEvents=True,
                maxResults=2
            ).execute().get('items', [])
            if not events:
                return f"No event found with title '{input.title}' at that time."
            if len(events) > 1:
                return f"Multiple events found with title '{input.title}' at that time. Please use event number or list events to select."
            event_id = events[0]['id']
        if not event_id and input.event_number:
            events = service.events().list(
                calendarId='primary',
                timeMin=(datetime.now() - timedelta(days=30)).isoformat() + 'Z',
                timeMax=(datetime.now() + timedelta(days=30)).isoformat() + 'Z',
                maxResults=10,
                singleEvents=True,
                orderBy='startTime'
            ).execute().get('items', [])
            if input.event_number < 1 or input.event_number > len(events):
                return f"Invalid event number: {input.event_number}. Choose between 1 and {len(events)}."
            event_id = events[input.event_number - 1]['id']
        if not event_id:
            return "Please provide event title with date/time or list events to select."
        try:
            service.events().delete(calendarId='primary', eventId=event_id).execute()
        except Exception as e:
            return f"Error deleting event: {str(e) if str(e) else 'Unknown error'}"
        events = service.events().list(
            calendarId='primary',
            timeMin=(datetime.now() - timedelta(days=30)).isoformat() + 'Z',
            timeMax=(datetime.now() + timedelta(days=30)).isoformat() + 'Z',
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute().get('items', [])
        if any(e['id'] == event_id for e in events):
            return f"Failed to delete event. Please try again or check your calendar connection."
        return "Event deleted successfully"
    except Exception as e:
        logger.error(f"Error deleting event: {str(e)}")
        return f"Error deleting event: {str(e) if str(e) else 'Unknown error'}"