from passlib.context import CryptContext

from app.supabase_client import get_supabase

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, stored_password: str) -> bool:
    # Backward-compatible check: accept either bcrypt hash or plain-text value.
    if stored_password.startswith("$2"):
        return pwd_context.verify(plain_password, stored_password)
    return plain_password == stored_password


def find_user_by_email(email: str) -> dict | None:
    client = get_supabase()
    response = client.table("users").select("*").eq("email", email).limit(1).execute()
    rows = response.data or []
    return rows[0] if rows else None


def create_user(email: str, password: str, role: str, full_name: str) -> dict:
    client = get_supabase()
    payload = {
        "email": email,
        "password_hash": get_password_hash(password),
        "role": role,
        "full_name": full_name,
        "status": "active",
    }
    response = client.table("users").insert(payload).execute()
    rows = response.data or []
    if not rows:
        raise ValueError("Failed to create user")
    return rows[0]


def register_user(email: str, password: str, role: str, full_name: str) -> dict:
    if find_user_by_email(email):
        raise ValueError("User already exists")
    return create_user(email, password, role, full_name)
