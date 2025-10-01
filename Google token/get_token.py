from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_access_token():
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secret_2.json',  # Path to your client_secret.json
        SCOPES
    )
    creds = flow.run_local_server(port=8000)
    print("Access token:", creds.token)
    return creds.token

if __name__ == "__main__":
    access_token = get_access_token()



# from google_auth_oauthlib.flow import InstalledAppFlow

# SCOPES = ['https://www.googleapis.com/auth/calendar']

# def get_refresh_token():
#     flow = InstalledAppFlow.from_client_secrets_file(
#         'client_secret_2.json',  # Path to your downloaded client_secret.json
#         SCOPES
#     )
#     creds = flow.run_local_server(port=8000)
#     print("Refresh token:", creds.refresh_token)
#     return creds.refresh_token

# if __name__ == "__main__":
#     get_refresh_token()