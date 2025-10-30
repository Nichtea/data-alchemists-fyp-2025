import os
import requests
import datetime as dt
from typing import Optional
from supabase import create_client, Client

# ---- Config (Render ENV) ----
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_KEY"]  # server-side only
ONEMAP_EMAIL = os.environ["ONEMAP_EMAIL"]
ONEMAP_PASSWORD = os.environ["ONEMAP_PASSWORD"]


REFRESH_EARLY_SEC = 6 * 3600  # refresh if <6 h left

# ---- Init Supabase client ----
sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def _utcnow():
    return dt.datetime.now(dt.timezone.utc)

def _parse_expiry(exp_raw: Optional[object]) -> Optional[dt.datetime]:
    """Normalize various expiry representations to a timezone-aware datetime in UTC.

    Accepts:
    - None -> returns None
    - datetime -> ensures tz-aware (assumes UTC if naive)
    - numeric (int/float) or numeric string -> epoch seconds
    - ISO string (with or without trailing Z)
    On parse failure returns None.
    """
    if exp_raw is None:
        return None
    # already a datetime
    if isinstance(exp_raw, dt.datetime):
        if exp_raw.tzinfo is None:
            return exp_raw.replace(tzinfo=dt.timezone.utc)
        return exp_raw.astimezone(dt.timezone.utc)

    try:
        # numeric types
        if isinstance(exp_raw, (int, float)):
            return dt.datetime.fromtimestamp(int(exp_raw), tz=dt.timezone.utc)
        s = str(exp_raw).strip()
        if s.isdigit():
            return dt.datetime.fromtimestamp(int(s), tz=dt.timezone.utc)
        # try ISO format
        try:
            dtobj = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dtobj.tzinfo is None:
                dtobj = dtobj.replace(tzinfo=dt.timezone.utc)
            return dtobj.astimezone(dt.timezone.utc)
        except Exception:
            # try float epoch string
            sec = float(s)
            return dt.datetime.fromtimestamp(int(sec), tz=dt.timezone.utc)
    except Exception:
        return None
# ----------------------------------------------------------------------
def _fetch_new_token() -> tuple[str, dt.datetime]:
    """Fetch a new OneMap token and parse expiry."""
    url = "https://www.onemap.gov.sg/api/auth/post/getToken"
    payload = {"email": ONEMAP_EMAIL, "password": ONEMAP_PASSWORD}
    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()
    data = r.json()
    token = data.get("access_token")
    exp_raw = data.get("expiry_timestamp")

    # Parse expiry or fallback to +1 day
    try:
        if exp_raw is None:
            exp = _utcnow() + dt.timedelta(days=1)
        elif str(exp_raw).isdigit():
            exp = dt.datetime.fromtimestamp(int(exp_raw), tz=dt.timezone.utc)
        else:
            exp = dt.datetime.fromisoformat(str(exp_raw).replace("Z", "+00:00"))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=dt.timezone.utc)
    except Exception:
        exp = _utcnow() + dt.timedelta(days=1)

    return token, exp

# ----------------------------------------------------------------------
def get_valid_token(force=False) -> str:
    """Return a valid OneMap token, refreshing if expiring soon."""
    rows = sb.table("onemap_token").select("*").eq("id", 1).limit(1).execute().data
    row = rows[0] if rows else None

    token, exp = None, None
    if row:
        token = row.get("access_token")
        exp_raw = row.get("expiry_timestamp")
        exp = _parse_expiry(exp_raw)

    now = _utcnow()
    if force or not token or (exp - now).total_seconds() < REFRESH_EARLY_SEC:
        new_token, new_exp = _fetch_new_token()
        sb.table("onemap_token").update({
            "access_token": new_token,
            "expiry_timestamp": new_exp.isoformat()
        }).eq("id", 1).execute()
        token = new_token

    return token

# ----------------------------------------------------------------------
def refresh_onemap_token() -> str:
    """Force-refresh the OneMap token (for cron/manual use)."""
    return get_valid_token(force=True)