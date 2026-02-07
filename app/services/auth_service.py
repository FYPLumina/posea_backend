
from jose import jwt
import os
from datetime import datetime, timedelta
import bcrypt
from app.utils.db import get_db_connection

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
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Check if user already exists
            cursor.execute("SELECT user_id FROM users WHERE email=%s", (email,))
            if cursor.fetchone():
                raise ValueError("Email already registered")
            # Hash password
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            cursor.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
                (name, email, hashed)
            )
            user_id = cursor.lastrowid
            conn.commit()
            return {"id": user_id, "email": email, "name": name}
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def authenticate(email: str, password: str) -> dict:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT user_id, email, name, password_hash FROM users WHERE email=%s", (email,))
            user = cursor.fetchone()
            if not user:
                return None
            if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
                return None
            return {"id": user["user_id"], "email": user["email"], "name": user["name"]}
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def logout(user_id: str):
        # Token revocation would be implemented in a real service.
        return True

    @staticmethod
    def update_profile(user_id: str, data: dict):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Only allow updating name and bio (if bio column exists)
            fields = []
            values = []
            if "name" in data:
                fields.append("name=%s")
                values.append(data["name"])
            # If you add a bio column, handle it here
            # if "bio" in data:
            #     fields.append("bio=%s")
            #     values.append(data["bio"])
            if not fields:
                raise ValueError("No updatable fields provided")
            values.append(user_id)
            sql = f"UPDATE users SET {', '.join(fields)} WHERE user_id=%s"
            cursor.execute(sql, tuple(values))
            conn.commit()
            cursor.execute("SELECT user_id, email, name FROM users WHERE user_id=%s", (user_id,))
            user = cursor.fetchone()
            return {"id": user["user_id"], "email": user["email"], "name": user["name"]}
        finally:
            cursor.close()
            conn.close()


    @staticmethod
    def change_password(user_id: str, old_password: str, new_password: str):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT password_hash FROM users WHERE user_id=%s", (user_id,))
            user = cursor.fetchone()
            if not user or not bcrypt.checkpw(old_password.encode(), user["password_hash"].encode()):
                return False
            new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
            cursor.execute("UPDATE users SET password_hash=%s WHERE user_id=%s", (new_hash, user_id))
            conn.commit()
            return True
        finally:
            cursor.close()
            conn.close()


    @staticmethod
    def delete_account(user_id: str):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM users WHERE user_id=%s", (user_id,))
            conn.commit()
            return True
        finally:
            cursor.close()
            conn.close()


auth_service = AuthService()
