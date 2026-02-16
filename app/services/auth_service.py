
from jose import jwt
import os
from datetime import datetime, timedelta
import bcrypt
import hashlib
import secrets
import smtplib
from email.message import EmailMessage
import logging
from app.utils.db import get_db_connection


def _parse_int_env(name: str, default: int) -> int:
    raw_value = os.environ.get(name, str(default))
    if raw_value is None:
        return default

    cleaned_value = str(raw_value).split(",")[0].strip()
    try:
        return int(cleaned_value)
    except (TypeError, ValueError):
        return default

SECRET_KEY = os.environ.get("JWT_SECRET", "CHANGE_ME_FOR_PRODUCTION")
ALGORITHM = "HS256"
RESET_TOKEN_EXPIRY_MINUTES = _parse_int_env("RESET_TOKEN_EXPIRY_MINUTES", 15)
RESET_PASSWORD_BASE_URL = os.environ.get("RESET_PASSWORD_BASE_URL", "")
EMAIL_VERIFICATION_EXPIRY_MINUTES = _parse_int_env("EMAIL_VERIFICATION_EXPIRY_MINUTES", 1440)
VERIFY_EMAIL_BASE_URL = os.environ.get("VERIFY_EMAIL_BASE_URL", "")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.sendgrid.net")
SMTP_PORT = _parse_int_env("SMTP_PORT", 587)
SMTP_USER = os.environ.get("SMTP_USER", "posea_mobile_app")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "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")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", "luminafyp@gmail.com")

logger = logging.getLogger("auth_service")


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
        AuthService._ensure_email_verification_schema()

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Hash password
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

            # Check if user already exists
            cursor.execute("SELECT user_id, is_active FROM users WHERE email=%s", (email,))
            existing_user = cursor.fetchone()
            if existing_user:
                if existing_user.get("is_active") == 1:
                    raise ValueError("Email already registered")

                # Reactivate inactive account and allow re-registration with same email
                cursor.execute(
                    """
                    UPDATE users
                    SET name=%s, password_hash=%s, profile_image=%s, bio=%s, is_active=1, is_logged_in=0, email_verified=0
                    WHERE user_id=%s
                    """,
                    (name, hashed, profile_image, bio, existing_user["user_id"])
                )
                user_id = existing_user["user_id"]
            else:
                cursor.execute(
                    "INSERT INTO users (name, email, password_hash, profile_image, bio, email_verified) VALUES (%s, %s, %s, %s, %s, 0)",
                    (name, email, hashed, profile_image, bio)
                )
                user_id = cursor.lastrowid

            token = AuthService._create_email_verification_token(cursor, user_id)
            conn.commit()

            AuthService._send_verification_email(email, token)
            return {
                "id": user_id,
                "email": email,
                "name": name,
                "profile_image": profile_image,
                "bio": bio,
                "email_verified": False,
            }
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def authenticate(email: str, password: str) -> dict:
        AuthService._ensure_email_verification_schema()

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT user_id, email, name, password_hash, is_active, email_verified FROM users WHERE email=%s", (email,))
            user = cursor.fetchone()
            if not user:
                return None
            if user.get("is_active") == 0:
                cursor.execute("UPDATE users SET is_logged_in=0 WHERE user_id=%s", (user["user_id"],))
                conn.commit()
                return None
            if user.get("email_verified") == 0:
                return {"requires_verification": True}
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
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT profile_image FROM users WHERE user_id=%s", (user_id,))
            user = cursor.fetchone()
            if not user:
                return False

            cursor.execute("SELECT file_path FROM background_image WHERE user_id=%s", (user_id,))
            background_rows = cursor.fetchall()

            cursor.execute("DELETE FROM captured_image WHERE user_id=%s", (user_id,))
            cursor.execute("DELETE FROM pose_selection WHERE user_id=%s", (user_id,))
            cursor.execute("DELETE FROM background_image WHERE user_id=%s", (user_id,))
            cursor.execute("DELETE FROM users WHERE user_id=%s", (user_id,))
            conn.commit()

            media_paths = []
            if user.get("profile_image"):
                media_paths.append(user["profile_image"])
            for row in background_rows:
                if row.get("file_path"):
                    media_paths.append(row["file_path"])

            app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            project_dir = os.path.abspath(os.path.join(app_dir, ".."))

            for media_path in media_paths:
                absolute_path = media_path
                if not os.path.isabs(absolute_path):
                    if media_path.startswith("/static/"):
                        absolute_path = os.path.join(app_dir, media_path.lstrip("/"))
                    else:
                        absolute_path = os.path.join(project_dir, media_path)

                absolute_path = os.path.normpath(absolute_path)
                try:
                    if os.path.exists(absolute_path):
                        os.remove(absolute_path)
                except Exception:
                    pass

            return True
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def _resolve_media_path(media_path: str) -> str:
        app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        project_dir = os.path.abspath(os.path.join(app_dir, ".."))

        absolute_path = media_path
        if not os.path.isabs(absolute_path):
            if media_path.startswith("/static/"):
                absolute_path = os.path.join(app_dir, media_path.lstrip("/"))
            else:
                absolute_path = os.path.join(project_dir, media_path)

        return os.path.normpath(absolute_path)

    @staticmethod
    def remove_profile_image(user_id: str):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT profile_image FROM users WHERE user_id=%s", (user_id,))
            user = cursor.fetchone()
            if not user:
                raise ValueError("User not found")

            profile_image_path = user.get("profile_image")
            cursor.execute("UPDATE users SET profile_image=NULL WHERE user_id=%s", (user_id,))
            conn.commit()

            if profile_image_path:
                absolute_path = AuthService._resolve_media_path(profile_image_path)
                try:
                    if os.path.exists(absolute_path):
                        os.remove(absolute_path)
                except Exception:
                    pass

            cursor.execute("SELECT user_id, email, name, profile_image, bio FROM users WHERE user_id=%s", (user_id,))
            updated_user = cursor.fetchone()
            return {
                "id": updated_user["user_id"],
                "email": updated_user["email"],
                "name": updated_user["name"],
                "profile_image": updated_user["profile_image"],
                "bio": updated_user["bio"],
            }
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def clear_bio(user_id: str):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT user_id FROM users WHERE user_id=%s", (user_id,))
            user = cursor.fetchone()
            if not user:
                raise ValueError("User not found")

            cursor.execute("UPDATE users SET bio=NULL WHERE user_id=%s", (user_id,))
            conn.commit()

            cursor.execute("SELECT user_id, email, name, profile_image, bio FROM users WHERE user_id=%s", (user_id,))
            updated_user = cursor.fetchone()
            return {
                "id": updated_user["user_id"],
                "email": updated_user["email"],
                "name": updated_user["name"],
                "profile_image": updated_user["profile_image"],
                "bio": updated_user["bio"],
            }
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def _ensure_password_reset_table():
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    token_hash VARCHAR(64) NOT NULL UNIQUE,
                    expires_at DATETIME NOT NULL,
                    used TINYINT(1) NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_password_reset_user_id (user_id),
                    INDEX idx_password_reset_expires_at (expires_at),
                    CONSTRAINT fk_password_reset_user
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def _column_exists(cursor, table_name: str, column_name: str) -> bool:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s
            LIMIT 1
            """,
            (table_name, column_name),
        )
        return cursor.fetchone() is not None

    @staticmethod
    def _ensure_email_verification_schema():
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if not AuthService._column_exists(cursor, "users", "email_verified"):
                cursor.execute("ALTER TABLE users ADD COLUMN email_verified TINYINT(1) NOT NULL DEFAULT 0")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS email_verification_tokens (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    token_hash VARCHAR(64) NOT NULL UNIQUE,
                    expires_at DATETIME NOT NULL,
                    used TINYINT(1) NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_email_verification_user_id (user_id),
                    INDEX idx_email_verification_expires_at (expires_at),
                    CONSTRAINT fk_email_verification_user
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def _create_email_verification_token(cursor, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        cursor.execute(
            "DELETE FROM email_verification_tokens WHERE user_id=%s OR expires_at < UTC_TIMESTAMP() OR used=1",
            (user_id,),
        )
        cursor.execute(
            """
            INSERT INTO email_verification_tokens (user_id, token_hash, expires_at, used)
            VALUES (%s, %s, DATE_ADD(UTC_TIMESTAMP(), INTERVAL %s MINUTE), 0)
            """,
            (user_id, token_hash, EMAIL_VERIFICATION_EXPIRY_MINUTES),
        )
        return token

    @staticmethod
    def _send_verification_email(email: str, token: str):
        verify_link = f"{VERIFY_EMAIL_BASE_URL}?token={token}" if VERIFY_EMAIL_BASE_URL else f"token={token}"

        if not SMTP_HOST or not SMTP_FROM_EMAIL:
            logger.info("Email verification requested for %s. Verification link: %s", email, verify_link)
            return

        msg = EmailMessage()
        msg["Subject"] = "Verify your email"
        msg["From"] = SMTP_FROM_EMAIL
        msg["To"] = email
        msg.set_content(
            f"Use the link below to verify your email address. This link expires in {EMAIL_VERIFICATION_EXPIRY_MINUTES} minutes.\n\n{verify_link}"
        )

        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                if SMTP_USER and SMTP_PASSWORD:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        except Exception:
            logger.exception("Failed to send verification email to %s", email)

    @staticmethod
    def _send_reset_password_email(email: str, token: str):
        reset_link = f"{RESET_PASSWORD_BASE_URL}?token={token}" if RESET_PASSWORD_BASE_URL else f"token={token}"

        if not SMTP_HOST or not SMTP_FROM_EMAIL:
            logger.info("Password reset requested for %s. Reset link: %s", email, reset_link)
            return

        msg = EmailMessage()
        msg["Subject"] = "Reset your password"
        msg["From"] = SMTP_FROM_EMAIL
        msg["To"] = email
        msg.set_content(
            f"Use the link below to reset your password. This link expires in {RESET_TOKEN_EXPIRY_MINUTES} minutes.\n\n{reset_link}"
        )

        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                if SMTP_USER and SMTP_PASSWORD:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        except Exception:
            logger.exception("Failed to send reset password email to %s", email)

    @staticmethod
    def forgot_password(email: str):
        AuthService._ensure_password_reset_table()

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT user_id, email, is_active FROM users WHERE email=%s", (email,))
            user = cursor.fetchone()

            if not user or user.get("is_active") == 0:
                return True

            user_id = user["user_id"]
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode()).hexdigest()

            cursor.execute(
                "DELETE FROM password_reset_tokens WHERE user_id=%s OR expires_at < UTC_TIMESTAMP() OR used=1",
                (user_id,),
            )
            cursor.execute(
                """
                INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, used)
                VALUES (%s, %s, DATE_ADD(UTC_TIMESTAMP(), INTERVAL %s MINUTE), 0)
                """,
                (user_id, token_hash, RESET_TOKEN_EXPIRY_MINUTES),
            )
            conn.commit()

            AuthService._send_reset_password_email(user["email"], token)
            return True
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def verify_email(token: str):
        if not token:
            return False

        AuthService._ensure_email_verification_schema()

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT id, user_id
                FROM email_verification_tokens
                WHERE token_hash=%s AND used=0 AND expires_at > UTC_TIMESTAMP()
                LIMIT 1
                """,
                (token_hash,),
            )
            token_row = cursor.fetchone()
            if not token_row:
                return False

            cursor.execute("UPDATE users SET email_verified=1 WHERE user_id=%s", (token_row["user_id"],))
            cursor.execute("UPDATE email_verification_tokens SET used=1 WHERE id=%s", (token_row["id"],))
            cursor.execute("UPDATE email_verification_tokens SET used=1 WHERE user_id=%s", (token_row["user_id"],))
            conn.commit()
            return True
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def resend_verification(email: str):
        AuthService._ensure_email_verification_schema()

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT user_id, email, is_active, email_verified FROM users WHERE email=%s", (email,))
            user = cursor.fetchone()
            if not user or user.get("is_active") == 0 or user.get("email_verified") == 1:
                return True

            token = AuthService._create_email_verification_token(cursor, user["user_id"])
            conn.commit()
            AuthService._send_verification_email(user["email"], token)
            return True
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def reset_password(token: str, new_password: str):
        if not token or not new_password:
            return False
        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters long")

        AuthService._ensure_password_reset_table()

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT id, user_id
                FROM password_reset_tokens
                WHERE token_hash=%s AND used=0 AND expires_at > UTC_TIMESTAMP()
                LIMIT 1
                """,
                (token_hash,),
            )
            reset_row = cursor.fetchone()
            if not reset_row:
                return False

            new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
            cursor.execute("UPDATE users SET password_hash=%s, is_logged_in=0 WHERE user_id=%s", (new_hash, reset_row["user_id"]))
            cursor.execute("UPDATE password_reset_tokens SET used=1 WHERE id=%s", (reset_row["id"],))
            cursor.execute("UPDATE password_reset_tokens SET used=1 WHERE user_id=%s", (reset_row["user_id"],))
            conn.commit()
            return True
        finally:
            cursor.close()
            conn.close()


auth_service = AuthService()
