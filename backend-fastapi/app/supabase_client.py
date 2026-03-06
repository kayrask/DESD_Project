import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client

ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ROOT_ENV_PATH)

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is not None:
        return _client

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or os.getenv("SUPABASE_ANON_KEY", "").strip()
    if not supabase_url or not supabase_key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY/SUPABASE_ANON_KEY in .env")

    _client = create_client(supabase_url, supabase_key)
    return _client
