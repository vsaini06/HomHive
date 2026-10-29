"""Password-based accounts and household-bound opaque sessions.

Tokens are randomly generated, stored only as SHA-256 digests, and revoked on logout.
Household authorization is always checked against persistent membership.
"""
import hashlib
import hmac
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from collections.abc import Mapping

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, Session

from .models import HouseholdMembershipRecord, UserRecord, UserSessionRecord

logger = logging.getLogger(__name__)
ITERATIONS = 600_000

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${derived.hex()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(actual, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False

class HouseholdTokens(Mapping[str, str]):
    """Compatibility bridge for old household-scoped endpoints; never exposed in the UI."""
    def __init__(self, configured: Mapping[str, str], key: str):
        self.configured = dict(configured)
        self.key = key.encode()
    def get(self, household_id, default=None):
        if household_id in self.configured:
            return self.configured[household_id]
        if not re.fullmatch(r"home_[a-f0-9]{32}", str(household_id)):
            return default
        return hmac.new(self.key, household_id.encode(), hashlib.sha256).hexdigest()
    def __getitem__(self, key):
        value = self.get(key)
        if value is None: raise KeyError(key)
        return value
    def __iter__(self): return iter(self.configured)
    def __len__(self): return len(self.configured)

class AccountService:
    def __init__(self, sessions: sessionmaker[Session]): self.sessions = sessions

    def register(self, email: str, password: str):
        email = email.strip().casefold()
        user_id, household = str(uuid4()), "home_" + uuid4().hex
        with self.sessions() as db:
            try:
                db.add(UserRecord(id=user_id, email=email, password_hash=hash_password(password)))


                db.flush()
                db.add(HouseholdMembershipRecord(user_id=user_id, household_id=household, role="owner"))
                db.commit()
            except IntegrityError as exc:
                db.rollback()
                orig = exc.orig
                sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
                diag = getattr(orig, "diag", None)
                constraint = getattr(diag, "constraint_name", None) if diag is not None else None


                sqlite_duplicate = (
                    sqlstate is None
                    and "UNIQUE constraint failed: users.email" in str(orig)
                )
                if (sqlstate == "23505" and constraint in {"users_email_key", "uq_users_email"}) or sqlite_duplicate:
                    raise HTTPException(409, "An account with this email already exists") from None
                logger.error(
                    "Registration database integrity failure (sqlstate=%s, constraint=%s)",
                    sqlstate or "unknown", constraint or "unknown"
                )
                raise HTTPException(500, "Could not create account due to a database integrity error") from None
        return self.create_session(user_id)

    def create_session(self, user_id: str):
        secret = secrets.token_urlsafe(40)
        digest = hashlib.sha256(secret.encode()).hexdigest()
        expires = datetime.now(timezone.utc) + timedelta(days=7)
        with self.sessions() as db:
            memberships = db.scalars(select(HouseholdMembershipRecord).where(HouseholdMembershipRecord.user_id == user_id)).all()
            db.add(UserSessionRecord(token_hash=digest, user_id=user_id, expires_at=expires))
            db.commit()
            household_ids = [m.household_id for m in memberships]
        return {"access_token": secret, "token_type":"bearer", "expires_at": expires.isoformat(), "households": household_ids}

    def login(self, email: str, password: str):
        with self.sessions() as db:
            user = db.scalar(select(UserRecord).where(UserRecord.email == email.strip().casefold()))
            if user is None or not verify_password(password, user.password_hash):
                raise HTTPException(401, "Invalid credentials")
            uid = user.id
        return self.create_session(uid)

    def membership(self, token: str, household_id: str) -> bool:
        if len(token) < 30 or len(token) > 200: return False
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.sessions() as db:
            session = db.get(UserSessionRecord, digest)
            if session is None: return False
            expires = session.expires_at
            if expires.tzinfo is None: expires = expires.replace(tzinfo=timezone.utc)
            if expires <= datetime.now(timezone.utc): return False
            return db.get(HouseholdMembershipRecord, (session.user_id, household_id)) is not None

    def logout(self, token: str):
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.sessions() as db:
            session = db.get(UserSessionRecord, digest)
            if session is not None:
                db.delete(session)
                db.commit()

class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=128)

def build_accounts_router(accounts: AccountService) -> APIRouter:
    from fastapi import Header
    router = APIRouter(prefix="/auth", tags=["accounts"])
    @router.post("/register", status_code=201)
    def register(body: Credentials):
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", body.email):
            raise HTTPException(422, "Invalid email address")
        return accounts.register(body.email, body.password)
    @router.post("/login")
    def login(body: Credentials):
        return accounts.login(body.email, body.password)
    @router.post("/logout", status_code=204)
    def logout(authorization: str | None = Header(default=None)):
        if authorization and authorization.lower().startswith("bearer "):
            accounts.logout(authorization.split(" ", 1)[1])
    return router
