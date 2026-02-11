
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

    #user registration, login, logout, profile update, password change, account deletion methods

    #user registration sql query to insert new user into database. Hash the password before storing it in the database. Check if email already exists before inserting new user.
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

    #user login method to verify email and password. If valid, set is_logged_in = 1 in the database for that user. Return user info if successful, otherwise return None.
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
            # Set is_logged_in = 1
            cursor.execute("UPDATE users SET is_logged_in=1 WHERE user_id=%s", (user["user_id"],))
            conn.commit()
            return {"id": user["user_id"], "email": user["email"], "name": user["name"]}
        finally:
            cursor.close()
            conn.close()

    #user logout method to set is_logged_in = 0 in the database for that user_id
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

    #user profile update method to update name, profile_image, and bio fields in the database for that user_id. Only update fields that are provided in the data dictionary.
    # Return the updated user info after successful update.
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

            #sql query to update user profile in the database. Only update fields that are provided in the data dictionary. Return the updated user info after successful update.
            sql = f"UPDATE users SET {', '.join(fields)} WHERE user_id=%s"
            cursor.execute(sql, tuple(values))
            conn.commit()
            #sql query to get user profile from the database after update and return it. Include id, email, name, profile_image, and bio fields in the returned user info.
            cursor.execute("SELECT user_id, email, name, profile_image, bio FROM users WHERE user_id=%s", (user_id,))
            user = cursor.fetchone()
            return {"id": user["user_id"], "email": user["email"], "name": user["name"], "profile_image": user["profile_image"], "bio": user["bio"]}
        finally:
            cursor.close()
            conn.close()

    #user password change method to update the password_hash field in the database for that user_id. Verify that the old_password is correct before updating to the new_password. Hash the new_password before storing it in the database.
    @staticmethod
    def change_password(user_id: str, old_password: str, new_password: str):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            #sql query to get the current password hash for the user_id from the database. Verify that the old_password matches the current password hash using bcrypt. If it matches, hash the new_password and update the password_hash field in the database with the new hash. Return True if successful, otherwise return False.
            cursor.execute("SELECT password_hash FROM users WHERE user_id=%s", (user_id,))
            user = cursor.fetchone()
            if not user or not bcrypt.checkpw(old_password.encode(), user["password_hash"].encode()):
                return False
            new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
            #sql query to update the password_hash field in the database for that user_id with the new hash.
            cursor.execute("UPDATE users SET password_hash=%s WHERE user_id=%s", (new_hash, user_id))
            conn.commit()
            return True
        finally:
            cursor.close()
            conn.close()

    #user account deletion method to set is_active = 0 in the database for that user_id
    @staticmethod
    def delete_account(user_id: str):
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            #sql query to set is_active = 0 in the database for that user_id to mark the account as deleted.
            cursor.execute("UPDATE users SET is_active=0 WHERE user_id=%s", (user_id,))
            conn.commit()
            return True
        finally:
            cursor.close()
            conn.close()


auth_service = AuthService()
