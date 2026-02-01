from jose import jwt
import os
from datetime import datetime, timedelta

SECRET_KEY = os.environ.get("JWT_SECRET", "CHANGE_ME_FOR_PRODUCTION")
ALGORITHM = "HS256"


class AuthService:
    """Mocked auth service interface. Replace with real persistence-backed implementation."""

    @staticmethod
    def issue_token(user_id: str, expires_minutes: int = 60 * 24):
        to_encode = {"sub": user_id, "exp": datetime.utcnow() + timedelta(minutes=expires_minutes)}
        token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return token

    @staticmethod
    def verify_token(token: str) -> dict:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except Exception:
            raise

    @staticmethod
    def register_user(email: str, password: str, name: str = None) -> dict:
        # Persistence should be implemented elsewhere. Return a mock user object.
        return {"id": "mock-user-id", "email": email, "name": name}

    @staticmethod
    def authenticate(email: str, password: str) -> dict:
        # Implement real verification in service layer. Here we accept any credentials for demo.
        return {"id": "mock-user-id", "email": email}

    @staticmethod
    def logout(user_id: str):
        # Token revocation would be implemented in a real service.
        return True

    @staticmethod
    def update_profile(user_id: str, data: dict):
        return {"id": user_id, **data}

    @staticmethod
    def change_password(user_id: str, old_password: str, new_password: str):
        return True

    @staticmethod
    def delete_account(user_id: str):
        return True


auth_service = AuthService()
