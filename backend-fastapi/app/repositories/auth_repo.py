from api.models import User


def find_user_by_email(email: str) -> User | None:
    try:
        return User.objects.get(email=email)
    except User.DoesNotExist:
        return None


def verify_password(plain_password: str, user: User) -> bool:
    return user.check_password(plain_password)


def register_user(email: str, password: str, role: str, full_name: str) -> User:
    if User.objects.filter(email=email).exists():
        raise ValueError("User already exists")
    return User.objects.create_user(email=email, password=password, role=role, full_name=full_name)
