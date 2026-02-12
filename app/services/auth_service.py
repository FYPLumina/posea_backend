
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
    def issue_token(user_id: str, expires_minutes: int = 60 * 24 * 90):
        to_encode = {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(minutes=expires_minutes)}
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
    def register_user(email: str, password: str, name: str = None, profile_image: str = None, bio: str = None) -> dict:
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
                "INSERT INTO users (name, email, password_hash, profile_image, bio) VALUES (%s, %s, %s, %s, %s)",
                (name, email, hashed, profile_image, bio)
            )
            user_id = cursor.lastrowid
            conn.commit()
            return {"id": user_id, "email": email, "name": name, "profile_image": profile_image, "bio": bio}
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def authenticate(email: str, password: str) -> dict:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT user_id, email, name, password_hash, is_active FROM users WHERE email=%s", (email,))
            user = cursor.fetchone()
            if not user:
                return None
            if user.get("is_active") == 0:
                cursor.execute("UPDATE users SET is_logged_in=0 WHERE user_id=%s", (user["user_id"],))
                conn.commit()
                return None
            if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
                return None
            # Set is_logged_in = 1
            cursor.execute("UPDATE users SET is_logged_in=1 WHERE user_id=%s", (user["user_id"],))
            conn.commit()
            return {"id": user["user_id"], "email": user["email"], "name": user["name"]}
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def logout(user_id: str):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET is_logged_in=0 WHERE user_id=%s", (user_id,))
            conn.commit()
            return True
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def update_profile(user_id: str, data: dict):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            fields = []
            values = []
            if "name" in data:
                fields.append("name=%s")
                values.append(data["name"])
            if "bio" in data:
                fields.append("bio=%s")
                values.append(data["bio"])
            if "profile_image" in data:
                fields.append("profile_image=%s")
                values.append(data["profile_image"])
            if not fields:
                raise ValueError("No updatable fields provided")
            values.append(user_id)
            sql = f"UPDATE users SET {', '.join(fields)} WHERE user_id=%s"
            cursor.execute(sql, tuple(values))
            conn.commit()
            cursor.execute("SELECT user_id, email, name, profile_image, bio FROM users WHERE user_id=%s", (user_id,))
            user = cursor.fetchone()
            return {"id": user["user_id"], "email": user["email"], "name": user["name"], "profile_image": user["profile_image"], "bio": user["bio"]}
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
            cursor.execute("UPDATE users SET is_active=0 WHERE user_id=%s", (user_id,))
            conn.commit()
            return True
        finally:
            cursor.close()
            conn.close()


auth_service = AuthService()
