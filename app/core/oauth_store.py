import base64
import hashlib
import secrets
import threading
import time
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class OAuthState:
    state: str
    code_verifier: str
    expires_at: float


@dataclass
class OAuthSession:
    session_id: str
    access_token: str
    token_type: str
    refresh_token: str | None
    scope: str | None
    expires_at: float
    created_at: float


class OAuthStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._states: dict[str, OAuthState] = {}
        self._sessions: dict[str, OAuthSession] = {}

    @staticmethod
    def _now() -> float:
        return time.time()

    @staticmethod
    def generate_code_verifier() -> str:
        return secrets.token_urlsafe(64)

    @staticmethod
    def generate_code_challenge(code_verifier: str) -> str:
        digest = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')

    def _cleanup_locked(self):
        now = self._now()
        for key in [k for k, v in self._states.items() if v.expires_at <= now]:
            self._states.pop(key, None)
        for key in [k for k, v in self._sessions.items() if v.expires_at <= now]:
            self._sessions.pop(key, None)

    def create_state(self, ttl_seconds: int | None = None) -> OAuthState:
        state_ttl = ttl_seconds or settings.oauth_state_ttl_seconds
        now = self._now()
        state = OAuthState(
            state=secrets.token_urlsafe(32),
            code_verifier=self.generate_code_verifier(),
            expires_at=now + max(60, state_ttl),
        )
        with self._lock:
            self._cleanup_locked()
            self._states[state.state] = state
        return state

    def pop_state(self, state: str) -> OAuthState | None:
        with self._lock:
            self._cleanup_locked()
            item = self._states.pop(state, None)
            if not item:
                return None
            if item.expires_at <= self._now():
                return None
            return item

    def create_session(
        self,
        access_token: str,
        token_type: str = 'Bearer',
        refresh_token: str | None = None,
        scope: str | None = None,
        provider_expires_in: int | None = None,
    ) -> OAuthSession:
        now = self._now()
        session_ttl = settings.oauth_session_ttl_seconds
        if provider_expires_in and provider_expires_in > 0:
            session_ttl = min(session_ttl, provider_expires_in)
        session = OAuthSession(
            session_id=secrets.token_urlsafe(32),
            access_token=access_token,
            token_type=token_type or 'Bearer',
            refresh_token=refresh_token,
            scope=scope,
            expires_at=now + max(60, session_ttl),
            created_at=now,
        )
        with self._lock:
            self._cleanup_locked()
            self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str | None) -> OAuthSession | None:
        if not session_id:
            return None
        with self._lock:
            self._cleanup_locked()
            session = self._sessions.get(session_id)
            if not session:
                return None
            if session.expires_at <= self._now():
                self._sessions.pop(session_id, None)
                return None
            return session

    def delete_session(self, session_id: str | None):
        if not session_id:
            return
        with self._lock:
            self._sessions.pop(session_id, None)

    def get_access_token(self, session_id: str | None) -> str | None:
        session = self.get_session(session_id)
        return session.access_token if session else None


oauth_store = OAuthStore()
