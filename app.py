
from dataclasses import asdict
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
import json
import asyncio
import livekit.agents as agents
from livekit.agents import JobContext, WorkerOptions, cli, RunContext, metrics, AutoSubscribe
from livekit.agents.llm import function_tool, LLM
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import deepgram, openai, silero, elevenlabs 
from datetime import datetime
from typing import List, Optional
from tools.google_calendar_tool import (
    CreateEventInput,
    ListEventsInput,
    UpdateEventInput,
    DeleteEventInput,
    create_event_func,
    list_events_func,
    update_event_func,
    delete_event_func,
    get_access_token,
)

from tools.get_weather_tool import get_weather_by_city

from tools.nexhealth_tool import (
    NexHealthClient, 
    GetAvailableSlotsInput, CallerInfo
)


logger = logging.getLogger("google-calendar-voice-agent")
logger.setLevel(logging.INFO)

load_dotenv(dotenv_path='.env')



class NexHealthAgent(Agent):
    def __init__(self, refresh_token: str) -> None:
        super().__init__(
            instructions="""
                You are a helpful voice assistant for managing Google Calendar, checking weather, and booking appointments with NexHealth.
                
                For NexHealth, you can find locations, list providers, and check for available appointment slots.
                The workflow is:
                1. User asks for locations. You call 'get_nexhealth_locations'.
                2. User asks for providers. You call 'get_nexhealth_providers'.
                3. User asks for available slots. They may or may not provide a location, provider, or date. You call 'check_available_slots' with whatever information the user gives you; all parameters are optional.
                
                Gather caller details progressively: name, date of birth (in YYYY-MM-DD format), phone number, intent, appointment type, and category. Whenever the user shares information related to these fields, automatically call 'update_caller_info' to update the stored info without asking for confirmation. Ask one piece at a time only if needed to gather missing details. Use this stored info to filter providers and slots automatically.
                
                If userdata has caller_name then call user by their name.
                Also tell current weather of a specified city. 
                You can create, list, update, or delete events on google calendar.
                Always respond clearly and avoid unpronounceable characters.
                Current time: {current_time} in America/Chicago.
                If the user needs to authenticate, inform them to run the OAuth flow separately.
                Use natural language for dates (e.g., 'tomorrow at 3 PM') and convert to ISO8601 when needed.
            """.format(current_time=datetime.now().strftime("%I:%M %p, %b %d, %Y")),
            stt=deepgram.STT(),
            llm=openai.LLM(model="gpt-4o"),
            tts=openai.TTS(),
            # tts=elevenlabs.TTS(
            #         voice_id="ODq5zmih8GrVes37Dizd",
            #         model="eleven_multilingual_v2"
            # ),
            vad=silero.VAD.load()
        )
        self.refresh_token = refresh_token
        # self.timezone = 'Asia/Karachi'  # pakistan timezone
        self.timezone = 'America/Chicago' # america central timezone
        self.nexhealth_client = NexHealthClient()
  

    
    @function_tool
    async def get_nexhealth_locations(self, context: RunContext[CallerInfo]):
        """Get a list of all available NexHealth clinic locations."""
        logger.info("Getting NexHealth locations")

        formatted_locations = self.nexhealth_client.get_locations()
        return None, formatted_locations
    

    @function_tool
    async def get_nexhealth_providers(self, context: RunContext[CallerInfo]):
        """Get a list of available providers."""
        logger.info("Getting NexHealth providers")
        result = self.nexhealth_client.get_providers()
        return None, result
    

    @function_tool
    async def check_available_slots(
        self,
        context: RunContext[CallerInfo],
        start_date: Optional[str] = None,
        days: Optional[int] = None,
        location_ids: Optional[List[int]] = None,
        provider_ids: Optional[List[int]] = None,
    ):
        """
        Check for available appointment slots. All parameters are optional.
        If no parameters are provided, it will search for all available slots.
        """
        logger.info(f"Checking slots for LIDs {location_ids} and PIDs {provider_ids}")
        input_data = GetAvailableSlotsInput(
            start_date=start_date,
            days=days,
            location_ids=location_ids,
            provider_ids=provider_ids,
        )
        result = self.nexhealth_client.get_available_slots(input_data)
        return None, result
    
    @function_tool
    async def update_caller_info(
        self,
        context: RunContext[CallerInfo],
        caller_name: Optional[str] = None,
        caller_dob: Optional[str] = None,  
        caller_phone: Optional[str] = None,
        callers_intent: Optional[str] = None,
        appt_type: Optional[str] = None,
        appt_category: Optional[str] = None,
    ):
        """
        Update caller information in the userdata. Provide only the fields to update; others will remain unchanged.
        Date of birth should be in YYYY-MM-DD format.
        """
        userdata = context.userdata
        updates = {}

        if caller_name is not None:
            userdata.caller_name = caller_name
            updates["name"] = caller_name

        if caller_dob is not None:
            try:
                parsed_dob = datetime.strptime(caller_dob, "%Y-%m-%d").date()
                userdata.caller_dob = parsed_dob
                updates["dob"] = caller_dob
            except ValueError:
                return "Invalid date format for DOB. Use YYYY-MM-DD.", None

        if caller_phone is not None:
            userdata.caller_phone = caller_phone
            updates["phone"] = caller_phone

        if callers_intent is not None:
            userdata.callers_intent = callers_intent
            updates["intent"] = callers_intent

        if appt_type is not None:
            userdata.appt_type = appt_type
            updates["appt_type"] = appt_type

        if appt_category is not None:
            userdata.appt_category = appt_category
            updates["appt_category"] = appt_category

        update_summary = ", ".join([f"{k}: {v}" for k, v in updates.items()]) if updates else "No updates"
        return None, f"Successfully updated: {update_summary}"


    @function_tool
    async def create_event(self, context: RunContext[CallerInfo], input: CreateEventInput):
        """Create a calendar event. Also check for conflicts. if there is a conflict, suggest a new time."""
        logger.info(f"Creating event: {input}")
        result = create_event_func(input, self.refresh_token, self.timezone)
        return None, result   

    @function_tool
    async def list_events(self, context: RunContext[CallerInfo], input: ListEventsInput):
        """List calendar events within a specified time range. or show event of today."""
        logger.info(f"Listing events: {input}")
        result = list_events_func(input, self.refresh_token)
        return None, result

    @function_tool
    async def update_event(self, context: RunContext[CallerInfo], input: UpdateEventInput):
        """Update a calendar event by event ID or title or selection from a list of events or date with confirmation"""
        logger.info(f"Updating event: {input}")
        result = update_event_func(input, self.refresh_token, self.timezone)
        return None, result

    @function_tool
    async def delete_event(self, context: RunContext[CallerInfo], input: DeleteEventInput):
        """Delete a calendar event by event ID or title or selection from a list of events or date all with confirmation"""
        logger.info(f"Deleting event: {input}")
        result = delete_event_func(input, self.refresh_token)
        return None, result
    
    @function_tool
    async def weather_tool(self, context: RunContext[CallerInfo], city_name: str) -> dict:
        """
        Get current weather information for a given city.
        """
        api_key = os.getenv("OPENWEATHERMAP_API_KEY")
        if not api_key:
            return {"error": "Missing OpenWeatherMap API key in environment variables."}

        result=get_weather_by_city(city_name, api_key)
        return None, result 
    
    async def on_enter(self):
        await self.session.say(
            "Hello! I can manage your Google Calendar, check the weather, or help you find and book NexHealth appointments. How can I help?"
        )
    
async def entrypoint(ctx: JobContext):
    # refresh_token = get_access_token()
    refresh_token=None
    # if not refresh_token:
    #     logger.error("No refresh token found. Please run google oauth flow to authenticate.")
    #     return

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    transcript_path = log_dir / "transcript.json"
    metrics_path = log_dir / "metrics.json"

 
    transcript_path.write_text("[]")
    metrics_path.write_text("{}")

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    

    session = AgentSession[CallerInfo](userdata=CallerInfo())
    await session.start(
        agent=NexHealthAgent(refresh_token=refresh_token),
        room=ctx.room
    )

 
    session.on("conversation_item_added")
    async def log_transcription(event: agents.ConversationItemAddedEvent, path: Path):
        item = event.item
        if hasattr(item, "text") and item.text:
            role = item.role
            text = item.text
            with open(path, "r") as f:
                transcript = json.load(f)
            transcript.append({"role": role, "text": text})
            with open(path, "w") as f:
                json.dump(transcript, f, indent=2)
            # logger.info(f"Logged transcription: {role} - {text}")

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: agents.MetricsCollectedEvent):
        usage_collector.collect(ev.metrics)
        with open(metrics_path, "w") as f:
            json.dump(asdict(usage_collector.get_summary()), f, indent=2)
        # logger.info(f"Logged metrics: {ev.metrics}")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
