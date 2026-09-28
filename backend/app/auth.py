"""Username/password auth with argon2 hashing and HS256 JWTs."""

from __future__ import annotations

import os
import secrets
import warnings
from pathlib import Path
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from dotenv import load_dotenv
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import User, get_db

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
if not os.environ.get("SECRET_KEY"):
    warnings.warn("SECRET_KEY not set; using a random key, tokens will not survive restarts", stacklevel=1)
TOKEN_TTL = timedelta(days=30)
# Registering a name listed in ADMIN_USERS needs this code, so nobody else can
# claim an admin name before its owner does. Unset means admin names cannot
# be registered through the API at all.
ADMIN_USERS = {u.strip() for u in os.environ.get("ADMIN_USERS", "").split(",") if u.strip()}
ADMIN_SIGNUP_CODE = os.environ.get("ADMIN_SIGNUP_CODE", "")
# argon2id at OWASP's minimum (19 MiB, 2 passes). The library default is
# 64 MiB per hash, which a few parallel logins turn into an OOM on a 512 MB host.
_hasher = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)
_bearer = HTTPBearer(auto_error=False)


def is_admin(user: User) -> bool:
    return user.username in ADMIN_USERS


def may_register(username: str, admin_code: str | None) -> bool:
    if username not in ADMIN_USERS:
        return True
    return bool(ADMIN_SIGNUP_CODE) and secrets.compare_digest(admin_code or "", ADMIN_SIGNUP_CODE)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def needs_rehash(password_hash: str) -> bool:
    """Hashes made with older parameters are upgraded on the next login."""
    return _hasher.check_needs_rehash(password_hash)


def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "exp": datetime.now(timezone.utc) + TOKEN_TTL,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.scalar(select(User).where(User.id == int(payload["sub"])))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return user


def optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    """The signed in user, or None for anonymous or invalid tokens."""
    if creds is None:
        return None
    try:
        return current_user(creds, db)
    except HTTPException:
        return None


def admin_user(user: User = Depends(current_user)) -> User:
    if not is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user
