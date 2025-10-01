# Updated google_calendar_voice_agent.py (importing from google_calendar_api.py)
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli, RunContext # Import RunContext here
from livekit.agents.llm import function_tool, LLM
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import deepgram, openai, silero
from datetime import datetime
from google_calendar_api import (
    CreateEventInput,
    ListEventsInput,
    UpdateEventInput,
    DeleteEventInput,
    create_event_func,
    list_events_func,
    update_event_func,
    delete_event_func,
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
            tts=openai.TTS(),
            vad=silero.VAD.load()
        )
        self.refresh_token = refresh_token
        self.timezone = 'Asia/Karachi'

    @function_tool
    async def create_event(self, context: RunContext, input: CreateEventInput):
        logger.info(f"Creating event: {input}")
        result = create_event_func(input, self.refresh_token, self.timezone)
        return None, result

    @function_tool
    async def list_events(self, context: RunContext, input: ListEventsInput):
        logger.info(f"Listing events: {input}")
        result = list_events_func(input, self.refresh_token)
        return None, result

    @function_tool
    async def update_event(self, context: RunContext, input: UpdateEventInput):
        logger.info(f"Updating event: {input}")
        result = update_event_func(input, self.refresh_token, self.timezone)
        return None, result

    @function_tool
    async def delete_event(self, context: RunContext, input: DeleteEventInput):
        logger.info(f"Deleting event: {input}")
        result = delete_event_func(input, self.refresh_token)
        return None, result
    
    async def on_enter(self):
        # FIX 1: Use self.session.say() instead of self.session.generate_reply()
        if not self.refresh_token:
            await self.session.say("Please authenticate with Google Calendar first.")
            return
        await self.session.say("Hello! I'm your Google Calendar assistant. You can say things like 'create a meeting tomorrow at 3 PM' or 'list my events this week'.")


    
async def entrypoint(ctx: JobContext):
    refresh_token = os.getenv('GOOGLE_REFRESH_TOKEN')
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
