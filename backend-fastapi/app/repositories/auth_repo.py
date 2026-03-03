from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class UserRecord:
    email: str
    password: str
    role: str
    full_name: str


_USERS: Dict[str, UserRecord] = {
    "producer@desd.local": UserRecord(
        email="producer@desd.local",
        password="password123",
        role="producer",
        full_name="Producer User",
    ),
    "admin@desd.local": UserRecord(
        email="admin@desd.local",
        password="password123",
        role="admin",
        full_name="Admin User",
    ),
    "customer@desd.local": UserRecord(
        email="customer@desd.local",
        password="password123",
        role="customer",
        full_name="Customer User",
    ),
}


def find_user_by_email(email: str) -> Optional[UserRecord]:
    return _USERS.get(email)
