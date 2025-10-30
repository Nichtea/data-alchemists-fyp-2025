# import os
# import requests
# from datetime import datetime, timedelta
# from dotenv import load_dotenv, set_key

# load_dotenv()
# ENV_PATH = os.path.join(os.path.dirname(__file__), "../../.env")

# ONEMAP_EMAIL = os.getenv("ONEMAP_EMAIL")
# ONEMAP_PASSWORD = os.getenv("ONEMAP_PASSWORD")

# def refresh_onemap_token():
#     """Fetch a new OneMap access token and update .env"""
#     url = "https://www.onemap.gov.sg/api/auth/post/getToken"
#     payload = {"email": ONEMAP_EMAIL, "password": ONEMAP_PASSWORD}

#     try:
#         response = requests.post(url, json=payload)
#         response.raise_for_status()
#         data = response.json()
#         access_token = data.get("access_token")
#         expiry = data.get("expiry_timestamp")

#         if access_token:
#             set_key(ENV_PATH, "ONEMAP_API_KEY", access_token)
#             set_key(ENV_PATH, "ONEMAP_EXPIRY", expiry)
#             print(f"Token refreshed successfully. Expires at: {expiry}")
#             return access_token
#         else:
#             print("Failed to get access token:", data)
#     except Exception as e:
#         print(f"Error refreshing token: {e}")

# def is_token_expiring():
#     """Check if token is expiring within 2 days"""
#     expiry_str = os.getenv("ONEMAP_EXPIRY")
#     if not expiry_str:
#         return True
#     try:
#         expiry = datetime.fromisoformat(expiry_str)
#         return expiry - datetime.now() < timedelta(days=2)
#     except Exception:
#         return True

# def get_valid_token():
#     """Return a valid token (refresh if needed)"""
#     load_dotenv() 
#     if is_token_expiring():
#         refresh_onemap_token()
#     return os.getenv("ONEMAP_API_KEY")
