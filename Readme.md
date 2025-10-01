# Google Calendar Voice Assistant

This repository contains a Python-based voice assistant that interacts with the Google Calendar API to perform CRUD (Create, Read, Update, Delete) operations on calendar events. Built using the `google-api-python-client` library for calendar integration and the LiveKit framework for real-time voice interactions, the assistant supports natural language commands like "create a meeting tomorrow at 3 PM" or "list my events this week."

## Features

- **Voice Interaction**: Uses Deepgram for speech-to-text, OpenAI's `gpt-4o` for natural language processing, and OpenAI's TTS for voice responses.
- **Calendar Operations**:
  - **Create Events**: Schedule events with title, start/end times, description, location, and attendees (including Google Meet links for online meetings).
  - **Read Events**: List events within a specified time range.
  - **Update Events**: Modify events by ID, title + time, or event number.
  - **Delete Events**: Remove events with flexible identification.
- **OAuth 2.0 Authentication**: Securely accesses Google Calendar using a refresh token.
- **Natural Language Support**: Converts user-friendly date inputs (e.g., "tomorrow at 3 PM") to ISO8601 format.
- **Error Handling**: Robust logging and user-friendly error messages.

## Prerequisites

- **Python 3.8+**
- Google Cloud Project with Google Calendar API enabled
- OAuth 2.0 credentials (client ID, client secret, refresh token)
- LiveKit server for voice interactions
- Required Python packages:
  - `google-api-python-client`
  - `google-auth-oauthlib`
  - `google-auth-httplib2`
  - `python-dotenv`
  - `livekit-agents`
  - `livekit-plugins-deepgram`
  - `livekit-plugins-openai`
  - `livekit-plugins-silero`
  - `pydantic`

## Setup

### 1. Install Dependencies
Clone the repository and install the required packages:

```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
pip install -r requirements.txt
```

Or manually install the packages:

```bash
pip install google-api-python-client google-auth-oauthlib google-auth-httplib2 python-dotenv livekit-agents livekit-plugins-deepgram livekit-plugins-openai livekit-plugins-silero pydantic
```

### 2. Configure Google Cloud Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project or select an existing one.
3. Enable the **Google Calendar API** under APIs & Services > Library.
4. Create OAuth 2.0 credentials:
   - Go to APIs & Services > Credentials > Create Credentials > OAuth client ID.
   - Choose **Desktop application** and name it (e.g., "Calendar Voice Assistant").
   - Add `http://localhost:8080/` to **Authorized redirect URIs** (ensure the trailing slash is included).
   - Download the `client_secret.json` file and place it in the project directory.
5. Configure the OAuth consent screen with the scope `https://www.googleapis.com/auth/calendar.events` and `https://www.googleapis.com/auth/calendar.readonly`.

### 3. Obtain a Refresh Token
Run the `get_refresh_token.py` script to authenticate and obtain a refresh token:

```bash
python get_refresh_token.py
```

**Script** (`get_refresh_token.py`):
```python
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.readonly'
]

def get_refresh_token():
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secret.json',
        SCOPES
    )
    creds = flow.run_local_server(port=8080)
    print("Access token:", creds.token)
    print("Refresh token:", creds.refresh_token)
    print("Client ID:", creds.client_id)
    print("Client Secret:", creds.client_secret)
    return creds.refresh_token

if __name__ == "__main__":
    get_refresh_token()
```

- Place `client_secret.json` in the project directory.
- Run the script, sign in with your Google account (e.g., `example@gmail.com`), and approve access.
- Copy the `refresh_token`, `client_id`, and `client_secret` to your `.env` file.

### 4. Set Up Environment Variables
Create a `.env` file in the project directory with the following:

```
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REFRESH_TOKEN=your_refresh_token_here
```

Example:
```
GOOGLE_CLIENT_ID=1234567890-abc123def456.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-abc123def456ghi789
GOOGLE_REFRESH_TOKEN=1//04abc123def456ghi789jkl012mn345op678
```

### 5. Configure LiveKit
- Set up a LiveKit server (see [LiveKit documentation](https://docs.livekit.io/)).
- Ensure you have API keys for LiveKit and the necessary credentials for Deepgram and OpenAI (if required by your setup).
- Update `.env` with any additional LiveKit or plugin-specific variables (e.g., `DEEPGRAM_API_KEY`, `OPENAI_API_KEY`).

### 6. Run the Application
Start the voice assistant:

```bash
python app_with_calendar_api.py
```

The assistant will connect to a LiveKit room and respond to voice commands for managing Google Calendar events.

## Usage

The assistant supports natural language voice commands, such as:
- "Create a meeting tomorrow at 3 PM"
- "List my events this week"
- "Update my meeting titled 'Team Sync' to 4 PM"
- "Delete the event called 'Lunch' tomorrow"

### Example API Functions (from `google_calendar_api.py`)

1. **Create an Event**:
   ```python
   from google_calendar_api import CreateEventInput, create_event_func
   input = CreateEventInput(
       title="Team Meeting",
       start_datetime="2025-10-03T15:00:00+05:00",
       end_datetime="2025-10-03T16:00:00+05:00",
       description="Weekly sync",
       attendees=["example@gmail.com"],
       location="Google Meet"
   )
   print(create_event_func(input, refresh_token="your_refresh_token"))
   ```

2. **List Events**:
   ```python
   from google_calendar_api import ListEventsInput, list_events_func
   input = ListEventsInput(
       start_datetime="2025-10-01T00:00:00Z",
       end_datetime="2025-10-31T23:59:59Z",
       max_results=10
   )
   print(list_events_func(input, refresh_token="your_refresh_token"))
   ```

3. **Update an Event**:
   ```python
   from google_calendar_api import UpdateEventInput, update_event_func
   input = UpdateEventInput(
       event_id="your_event_id_here",
       new_title="Updated Team Meeting",
       new_start_datetime="2025-10-03T16:00:00+05:00"
   )
   print(update_event_func(input, refresh_token="your_refresh_token"))
   ```

4. **Delete an Event**:
   ```python
   from google_calendar_api import DeleteEventInput, delete_event_func
   input = DeleteEventInput(event_id="your_event_id_here")
   print(delete_event_func(input, refresh_token="your_refresh_token"))
   ```

Replace `your_refresh_token` with the actual refresh token from `.env` and `your_event_id_here` with an event ID from `list_events_func`.

## Project Structure

```
your-repo-name/
├── app_with_calendar_api.py  # Voice assistant script
├── google_calendar_api.py    # Google Calendar API functions
├── get_refresh_token.py      # Script to generate refresh token
├── client_secret.json        # OAuth 2.0 client credentials (not tracked)
├── .env                      # Environment variables (not tracked)
├── requirements.txt          # Python dependencies
├── README.md                 # This file
```

## Troubleshooting

- **Error 400: redirect_uri_mismatch**:
  - Ensure `http://localhost:8080/` is listed in Authorized redirect URIs in Google Cloud Console.
  - Verify `get_refresh_token.py` uses `port=8080` in `run_local_server`.
  - Wait 5-10 minutes after updating URIs for changes to propagate.
  - If the error persists, check the browser's error URL for the exact `redirect_uri` and add it to the console.

- **Missing Environment Variables**:
  - Verify `.env` exists in the project root and contains `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REFRESH_TOKEN`.
  - Use `load_dotenv(dotenv_path='.env')` if the file is not detected.

- **Invalid Refresh Token**:
  - Regenerate using `get_refresh_token.py`.
  - Ensure the Google account (e.g., `example@gmail.com`) has access to the calendar.

- **LiveKit Issues**:
  - Confirm your LiveKit server is running and accessible.
  - Check API keys for LiveKit, Deepgram, and OpenAI.

- **API Errors**:
  - Ensure the Google Calendar API is enabled in your Google Cloud project.
  - Verify the calendar ID (`primary`) is accessible to the authenticated account.

## Contributing

Contributions are welcome! Please:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/your-feature`).
3. Commit changes (`git commit -m 'Add your feature'`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact

For issues or questions, contact [example@gmail.com] or open an issue on GitHub.