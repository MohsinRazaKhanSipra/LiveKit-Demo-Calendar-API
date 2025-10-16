
from dataclasses import asdict, dataclass, field
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
from livekit.plugins import deepgram, openai, silero, elevenlabs, google

from datetime import date, datetime
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
    GetAvailableSlotsInput
)

from livekit.api import LiveKitAPI, DeleteRoomRequest
from livekit.api.sip_service import TransferSIPParticipantRequest

#Loading enviroment variables
load_dotenv(dotenv_path='.env')

#Logging
logger = logging.getLogger("google-calendar-voice-agent")
logger.setLevel(logging.DEBUG)

#Custom userdata
@dataclass
class CallerInfo():
    ctx: JobContext
    caller_name: str="" 
    caller_dob: date = field(default_factory=date.today)
    caller_phone: str="" 
    callers_intent: str="" 
    appt_type: str=""
    appt_category: str=""
    
RunContext_T = RunContext[CallerInfo]

#Base Class
class BaseAgent(Agent):
    
    api_url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    async def _transfer_call_function(
        self, 
        context: RunContext_T, 
        participant_identity: str,
        transfer_to: str
    ) -> str:
        """
        This function transfers an ongoing SIP call to another phone number using the LiveKit SIP API.
        It handles the transfer by creating a TransferSIPParticipantRequest and executing it asynchronously.
        The function assumes valid LiveKit API credentials are set in environment variables.
        Upon success, it logs the transfer and says a goodbye message to the session.
        If credentials are missing or the transfer fails, it returns an error message.

        Args:
            context: The RunContext providing access to the session userdata and room details.
            participant_identity: The unique identity string of the SIP participant to transfer, as required by LiveKit docs (typically obtained from room participants).
            transfer_to: The destination phone number in E.164 format, e.g., 'tel:+14155550100'.

        Returns:
            A confirmation string like "Call successfully transferred to {transfer_to}." or an error message.
        """
        room_name = context.userdata.ctx.room.name

        if not all([self.api_url, self.api_key, self.api_secret]):
            return "LiveKit API credentials not configured."

        async with LiveKitAPI(
            url=self.api_url, 
            api_key=self.api_key, 
            api_secret=self.api_secret
        ) as livekit_api:
            transfer_request = TransferSIPParticipantRequest(
                participant_identity=participant_identity,
                room_name=room_name,
                transfer_to=transfer_to,
                play_dialtone=False
            )
            logger.debug(f"Transfer request: {transfer_request}")

            await livekit_api.sip.transfer_sip_participant(transfer_request)
            logger.info(f"Successfully transferred participant {participant_identity}")

        await self.session.say("Transferring your call now. Goodbye!")
        return f"Call successfully transferred to {transfer_to}."



    async def _end_call_function(
        self, 
        context: RunContext_T,
    ) -> str:
        """
        Ends (hangs up) the ongoing SIP call by deleting the entire room.
        This is the correct way to end a SIP call in the latest LiveKit SDK, as
        HangupSIPParticipantRequest is no longer supported.
        
        Args:
            context: The RunContext providing access to the session userdata and room details.
            
        Returns:
            A confirmation string like "Call successfully ended." or an error message.
        """
        room_name = context.userdata.ctx.room.name

        if not all([self.api_url, self.api_key, self.api_secret]):
            return "LiveKit API credentials not configured."

        async with LiveKitAPI(
            url=self.api_url, 
            api_key=self.api_key, 
            api_secret=self.api_secret
        ) as livekit_api:
            await self.session.say("Thank you for calling. Goodbye!")
            await asyncio.sleep(1) # Small delay to ensure the message is delivered.
            

            delete_room_request = DeleteRoomRequest(room=room_name)
            logger.debug(f"Delete room request: {delete_room_request}")
            
            await livekit_api.room.delete_room(delete_room_request)
            logger.info(f"Successfully deleted room {room_name}")

        return "Call successfully ended."
    

class NexHealthAgent(BaseAgent):
    def __init__(self, refresh_token: str) -> None:
        super().__init__(
            instructions="""
                You are a helpful voice assistant for managing Google Calendar, checking weather, and booking appointments with NexHealth.
                Gather caller details progressively: name, date of birth (in YYYY-MM-DD format), phone number, intent, appointment type, and category. Whenever the user shares information related to these fields, automatically call 'update_caller_info' to update the stored info without asking for confirmation. Ask one piece at a time only if needed to gather missing details. Use this stored info to filter providers and slots automatically.

                For NexHealth, you can find locations, list providers, and check for available appointment slots.
                The workflow is:
                1. User asks for locations. You call 'get_nexhealth_locations'.
                2. User asks for providers. You call 'get_nexhealth_providers'.
                3. User asks for available slots. They may or may not provide a location, provider, or date. You call 'check_available_slots' with whatever information the user gives you; all parameters are optional.
                4. User ask for schedule appointment then schedule the appointment by getting patient_id, provider_id, start_time, operatory_id from previous responses and call 'schedule_appointment'. or You call 'check_available_slots' with whatever information you require.
                
  
                
                If userdata has caller_name then call user by their name.
                Also tell current weather of a specified city. 
                You can create, list, update, or delete events on google calendar.
                Always respond clearly and avoid unpronounceable characters.
                Current time: {current_time} in America/Chicago.
                If the user needs to authenticate, inform them to run the OAuth flow separately.
                Use natural language for dates (e.g., 'tomorrow at 3 PM') and convert to ISO8601 when needed.
                You can also transfer the call to another number using 'transfer_call function' or end the call using 'end_call function'
            """.format(current_time=datetime.now().strftime("%I:%M %p, %b %d, %Y")),
            stt=deepgram.STT(),
            llm="google/gemini-2.5-flash-lite",#openai.LLM(model="gpt-4o"),
            tts=deepgram.TTS(model="aura-helios-en"),#openai.TTS(),
            # tts=elevenlabs.TTS(),
            vad=silero.VAD.load()
        )
        self.refresh_token = refresh_token
        # self.timezone = 'Asia/Karachi'  # pakistan timezone
        self.timezone = 'America/Chicago' # america central timezone
        self.nexhealth_client = NexHealthClient()


    @function_tool
    async def transfer_call(
        self, 
        context: RunContext_T, 
        participant_identity: str,
        transfer_to: str
    ) -> str:
        """
        Details:
            Transfer an ongoing SIP call for the given participant to another phone number
            using the LiveKit SIP API helper implemented in _transfer_call_function.
            This triggers an immediate transfer; the session will play a short message
            before the transfer.

        Args:
            context: RunContext_T - run context that provides access to session and userdata.
            participant_identity: str - identity of the SIP participant to transfer (as required by LiveKit).
            transfer_to: str - destination phone number in E.164 form, e.g., 'tel:+14155550100'.

        Returns:
            str: Confirmation message on success or an error message on failure.
        """
        return await self._transfer_call_function(context, participant_identity, transfer_to)


    @function_tool
    async def end_call(
        self, 
        context: RunContext_T,
        participant_identity: str
    ) -> str:
        """
        Details:
            End (hang up) the current SIP call by deleting the room via LiveKit API.
            Uses the helper _end_call_function which speaks a goodbye message before
            removing the room.

        Args:
            context: RunContext_T - run context that provides access to session and userdata.
            participant_identity: str - identity of the SIP participant being hung up (for logging/tracking).

        Returns:
            str: Confirmation message on success or an error message on failure.
        """
        return await self._end_call_function(context, participant_identity)
    
    @function_tool
    async def get_nexhealth_locations(self, context: RunContext_T):
        """
        Details:
            Retrieve the list of available NexHealth clinic locations from NexHealthClient.
            The returned value is suitable for speaking or further filtering by the agent.

        Args:
            context: RunContext_T - run context (unused here but included for consistency).

        Returns:
            tuple: (None, formatted_locations) where formatted_locations is the list/dict returned by NexHealthClient.get_locations().
        """
        logger.info("Getting NexHealth locations")

        formatted_locations = self.nexhealth_client.get_locations()
        return None, formatted_locations
    

    @function_tool
    async def get_nexhealth_providers(self, context: RunContext_T):
        """
        Details:
            Retrieve a list of providers available in NexHealth. Useful to enumerate providers
            for a given location or for the user to pick a provider when scheduling.

        Args:
            context: RunContext_T - run context (unused here but included for consistency).

        Returns:
            tuple: (None, result) where result is the provider list/dict returned by NexHealthClient.get_providers().
        """
        logger.info("Getting NexHealth providers")
        result = self.nexhealth_client.get_providers()
        return None, result
    

    @function_tool
    async def check_available_slots(
        self,
        context: RunContext_T,
        start_date: Optional[str] = None,
        days: Optional[int] = None,
        location_ids: Optional[List[int]] = None,
        provider_ids: Optional[List[int]] = None,
    ):
        """
        Details:
            Check for available appointment slots using NexHealthClient. All parameters are optional;
            if none are provided, a broad search is performed. Returns structured availability
            information that can be used to present options or schedule.

        Args:
            context: RunContext_T - run context (unused here but included for consistency).
            start_date: Optional[str] - ISO date (YYYY-MM-DD) or natural language converted to ISO by caller.
            days: Optional[int] - number of days from start_date to include in search.
            location_ids: Optional[List[int]] - list of location IDs to limit the search.
            provider_ids: Optional[List[int]] - list of provider IDs to limit the search.

        Returns:
            tuple: (None, result) where result contains available slots returned by NexHealthClient.get_available_slots().
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
    async def schedule_appointment(
        self,
        context: RunContext_T,
        patient_id: int,
        provider_id: int,
        start_time: str,
        operatory_id: int,
    ):
        """
        Details:
            Schedule an appointment with NexHealth using the provided identifiers and start time.
            This function currently demonstrates the scheduling stub and should be connected to
            the real scheduling API (NexHealthClient) for production use.

        Args:
            context: RunContext_T - run context (unused here but included for consistency).
            patient_id: int - NexHealth patient identifier.
            provider_id: int - NexHealth provider identifier.
            start_time: str - ISO8601 datetime string for the appointment start.
            operatory_id: int - operatory / room identifier for the appointment.

        Returns:
            tuple: (None, str) - human-readable confirmation or status message.
        """
        print("Scheduling appointment is completed")
        print(f"Patient ID: {patient_id}, Provider ID: {provider_id}, Start Time: {start_time}, Operatory ID: {operatory_id}")
        return None, "Scheduling appointment is completed"

    @function_tool
    async def update_caller_info(
        self,
        context: RunContext_T,
        caller_name: Optional[str] = None,
        caller_dob: Optional[str] = None,
        caller_phone: Optional[str] = None,
        callers_intent: Optional[str] = None,
        appt_type: Optional[str] = None,
        appt_category: Optional[str] = None,
    ):
        """
        Details:
            Update fields in the conversation userdata for the current caller. Only provided
            fields are updated; unspecified fields remain unchanged. Date of birth must be
            supplied in YYYY-MM-DD format to be parsed into a date.

        Args:
            context: RunContext_T - run context containing userdata to update.
            caller_name: Optional[str] - full name of the caller.
            caller_dob: Optional[str] - date of birth in 'YYYY-MM-DD' format.
            caller_phone: Optional[str] - phone number string.
            callers_intent: Optional[str] - short description of caller's intent.
            appt_type: Optional[str] - appointment type (e.g., new patient, follow-up).
            appt_category: Optional[str] - appointment category or reason.

        Returns:
            tuple:
                - If successful: (None, str) where str summarizes what was updated.
                - On invalid DOB format: (str_error_message, None).
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
    async def create_event(self, context: RunContext_T, input: CreateEventInput):
        """
        Details:
            Create a Google Calendar event using provided CreateEventInput. The helper
            create_event_func will check for conflicts and may suggest alternate times.

        Args:
            context: RunContext_T - run context (unused here but included for consistency).
            input: CreateEventInput - structured event creation data (title, start, end, attendees, etc.).

        Returns:
            tuple: (None, result) where result is the output from create_event_func (created event details or conflict suggestions).
        """
        logger.info(f"Creating event: {input}")
        result = create_event_func(input, self.refresh_token, self.timezone)
        return None, result   

    @function_tool
    async def list_events(self, context: RunContext_T, input: ListEventsInput):
        """
        Details:
            List calendar events for a specified time range or show events for today when requested.

        Args:
            context: RunContext_T - run context (unused here but included for consistency).
            input: ListEventsInput - parameters to filter the event listing (time range, calendar id, etc.).

        Returns:
            tuple: (None, result) where result contains the list of events from list_events_func.
        """
        logger.info(f"Listing events: {input}")
        result = list_events_func(input, self.refresh_token)
        return None, result

    @function_tool
    async def update_event(self, context: RunContext_T, input: UpdateEventInput):
        """
        Details:
            Update an existing calendar event identified by ID or title. The helper will
            perform necessary lookups and confirmations if multiple matches exist.

        Args:
            context: RunContext_T - run context (unused here but included for consistency).
            input: UpdateEventInput - structured data indicating which event to update and the updates to apply.

        Returns:
            tuple: (None, result) where result is the updated event details or a status message from update_event_func.
        """
        logger.info(f"Updating event: {input}")
        result = update_event_func(input, self.refresh_token, self.timezone)
        return None, result

    @function_tool
    async def delete_event(self, context: RunContext_T, input: DeleteEventInput):
        """
        Details:
            Delete a calendar event by event ID or other selectors. The helper handles confirmation flows.

        Args:
            context: RunContext_T - run context (unused here but included for consistency).
            input: DeleteEventInput - structured input indicating which event(s) to delete.

        Returns:
            tuple: (None, result) where result is the deletion result/status returned by delete_event_func.
        """
        logger.info(f"Deleting event: {input}")
        result = delete_event_func(input, self.refresh_token)
        return None, result
    
    @function_tool
    async def weather_tool(self, context: RunContext_T, city_name: str) -> dict:
        """
        Details:
            Fetch current weather for the provided city using OpenWeatherMap. Requires
            OPENWEATHERMAP_API_KEY to be set in environment variables.

        Args:
            context: RunContext_T - run context (unused here but included for consistency).
            city_name: str - human-readable city name (e.g., 'Chicago').

        Returns:
            tuple: (None, dict) where dict contains weather information returned by get_weather_by_city.
                    If API key is missing, returns a dict with an 'error' key.
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
    transcript_path = log_dir/"transcripts"
    metrics_path = log_dir / "metrics.json"
    metrics_path.write_text("{}")

    userdata = CallerInfo(ctx=ctx)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)


    session = AgentSession[CallerInfo](userdata=userdata)
    await session.start(
        agent=NexHealthAgent(refresh_token=refresh_token),
        room=ctx.room
    )

    async def write_transcript():
        current_date = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{transcript_path}/transcript_{ctx.room.name}_{current_date}.json"
        
        with open(filename, 'w') as f:
            json.dump(session.history.to_dict(), f, indent=2)
            
        print(f"Transcript for {ctx.room.name} saved to {filename}")

    ctx.add_shutdown_callback(write_transcript)


    @session.on("conversation_item_added")
    def on_conversation_item_added(ev):
        item = ev.item
        logger.info(f"Conversation item: role={item.role}, content={item.content}, interrupted={item.interrupted}")
        
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: agents.MetricsCollectedEvent):
        usage_collector.collect(ev.metrics)
        with open(metrics_path, "w") as f:
            json.dump(asdict(usage_collector.get_summary()), f, indent=2)
        # logger.info(f"Logged metrics: {ev.metrics}")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
