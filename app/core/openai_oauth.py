import json
import base64
from pathlib import Path


def load_codex_access_token(path_str: str) -> str | None:
    if not path_str:
        return None
    path = Path(path_str).expanduser()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    tokens = payload.get('tokens')
    if not isinstance(tokens, dict):
        return None
    access_token = tokens.get('access_token')
    if not isinstance(access_token, str):
        return None
    return access_token.strip() or None


def _decode_jwt_payload_unverified(token: str) -> dict:
    try:
        parts = token.split('.')
        if len(parts) < 2:
            return {}
        payload = parts[1]
        payload += '=' * (-len(payload) % 4)
        raw = base64.urlsafe_b64decode(payload.encode('utf-8'))
        data = json.loads(raw.decode('utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_codex_tokens(path_str: str) -> dict:
    if not path_str:
        return {}
    path = Path(path_str).expanduser()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    tokens = payload.get('tokens')
    if not isinstance(tokens, dict):
        return {}
    access_token = tokens.get('access_token')
    if not isinstance(access_token, str) or not access_token.strip():
        return {}
    decoded = _decode_jwt_payload_unverified(access_token)
    exp = decoded.get('exp')
    return {
        'access_token': access_token.strip(),
        'refresh_token': tokens.get('refresh_token'),
        'token_type': 'Bearer',
        'scope': 'openid profile email offline_access',
        'expires_at_unix': int(exp) if isinstance(exp, int) else None,
    }
