
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli, RunContext # Import RunContext here
from livekit.agents.llm import function_tool, LLM
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import deepgram, openai, silero, elevenlabs # 👈 Add elevenlabs
from datetime import datetime
from tools.google_calendar_api import (
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

logger = logging.getLogger("google-calendar-voice-agent")
logger.setLevel(logging.INFO)

load_dotenv(dotenv_path='.env')



class GoogleCalendarAgent(Agent):
    def __init__(self, refresh_token: str) -> None:
        super().__init__(
            instructions="""
                You are a helpful Google Calendar voice assistant. You can create, list, update, or delete events.
                Always respond clearly and avoid unpronounceable characters.
                Current time: {current_time} in Asia/Karachi.
                If the user needs to authenticate, inform them to run the OAuth flow separately.
                Use natural language for dates (e.g., 'tomorrow at 3 PM') and convert to ISO8601 when needed.
            """.format(current_time=datetime.now().strftime("%I:%M %p, %b %d, %Y")),
            stt=deepgram.STT(),
            llm=openai.LLM(model="gpt-4o"),
            tts=elevenlabs.TTS(
                    voice_id="ODq5zmih8GrVes37Dizd",
                    model="eleven_multilingual_v2"
            ),
            vad=silero.VAD.load()
        )
        self.refresh_token = refresh_token
        # self.timezone = 'Asia/Karachi'  # pakistan timezone
        self.timezone = 'America/Chicago' # america central timezone


    @function_tool
    async def create_event(self, context: RunContext, input: CreateEventInput):
        """Create a calendar event. Also check for conflicts. if there is a conflict, suggest a new time."""
        logger.info(f"Creating event: {input}")
        result = create_event_func(input, self.refresh_token, self.timezone)
        return None, result   

    @function_tool
    async def list_events(self, context: RunContext, input: ListEventsInput):
        """List calendar events within a specified time range. or show event of today."""
        logger.info(f"Listing events: {input}")
        result = list_events_func(input, self.refresh_token)
        return None, result

    @function_tool
    async def update_event(self, context: RunContext, input: UpdateEventInput):
        """Update a calendar event by event ID or title or selection from a list of events or date with confirmation"""
        logger.info(f"Updating event: {input}")
        result = update_event_func(input, self.refresh_token, self.timezone)
        return None, result

    @function_tool
    async def delete_event(self, context: RunContext, input: DeleteEventInput):
        """Delete a calendar event by event ID or title or selection from a list of events or date all with confirmation"""
        logger.info(f"Deleting event: {input}")
        result = delete_event_func(input, self.refresh_token)
        return None, result
    
    async def on_enter(self):
        if not self.refresh_token:
            await self.session.say("Please authenticate with Google Calendar first.")
            return
        await self.session.say("Hello! I'm your Google Calendar assistant. You can say things like 'create a meeting tomorrow at 3 PM' or 'list my events this week'.")


    
async def entrypoint(ctx: JobContext):
    refresh_token = get_access_token()
    if not refresh_token:
        logger.error("No refresh token found. Please run get_refresh_token_playwright.py to authenticate.")
        return

    session = AgentSession()
    await session.start(
        agent=GoogleCalendarAgent(refresh_token=refresh_token),
        room=ctx.room
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
