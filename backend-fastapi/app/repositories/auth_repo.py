from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.database import SessionLocal
from app.models.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def find_user_by_email(email: str) -> User | None:
    db: Session = SessionLocal()
    try:
        return db.query(User).filter(User.email == email).first()
    finally:
        db.close()


def create_user(email: str, password: str, role: str, full_name: str) -> User:
    db: Session = SessionLocal()
    try:
        hashed_password = get_password_hash(password)
        user = User(email=email, password_hash=hashed_password, role=role, full_name=full_name)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def register_user(email: str, password: str, role: str, full_name: str) -> User:
    # Check if user exists
    if find_user_by_email(email):
        raise ValueError("User already exists")
    return create_user(email, password, role, full_name)
