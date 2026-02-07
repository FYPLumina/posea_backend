from fastapi import Depends, HTTPException, status, Header
from jose import jwt, JWTError
import os
from typing import Optional

SECRET_KEY = os.environ.get("JWT_SECRET", "CHANGE_ME_FOR_PRODUCTION")
ALGORITHM = "HS256"


from app.utils.db import get_db_connection

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        # Try to extract user_id (sub) from token, if possible, and set is_logged_in=0
        try:
            from jose import jwt as jose_jwt
            payload = jose_jwt.get_unverified_claims(token)
            user_id = payload.get("sub")
            if user_id is not None:
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("UPDATE users SET is_logged_in=0 WHERE user_id=%s", (user_id,))
                    conn.commit()
                finally:
                    cursor.close()
                    conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing")
    parts = authorization.split()
    if parts[0].lower() != "bearer" or len(parts) != 2:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header format")
    token = parts[1]
    return decode_token(token)
