from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.core.config import settings
from app.core.openai_oauth import load_codex_tokens
from app.core.oauth_store import oauth_store


router = APIRouter(prefix='/auth', tags=['auth'])


def _is_openai_auth_provider() -> bool:
    return 'auth.openai.com' in settings.oauth_authorize_url.lower()


def _load_poc_codex_tokens() -> dict:
    # POC-first: if local Codex auth exists, prefer it and skip strict OAuth config.
    return load_codex_tokens(settings.openai_oauth_token_file)


def _build_success_response_from_session(session):
    success_redirect = settings.oauth_success_redirect_url
    if not success_redirect:
        success_redirect = '/auth/done'
    response: JSONResponse | RedirectResponse = RedirectResponse(
        url=success_redirect,
        status_code=302,
    )
    response.set_cookie(
        key=settings.oauth_session_cookie_name,
        value=session.session_id,
        httponly=True,
        secure=settings.oauth_cookie_secure,
        samesite='lax',
        max_age=max(60, int(session.expires_at - session.created_at)),
        path='/',
    )
    return response


def _build_json_session_response(session):
    response = JSONResponse(
        {
            'authenticated': True,
            'expires_at': datetime.fromtimestamp(
                session.expires_at, tz=timezone.utc
            ).isoformat(),
            'scope': session.scope,
            'token_type': session.token_type,
        }
    )
    response.set_cookie(
        key=settings.oauth_session_cookie_name,
        value=session.session_id,
        httponly=True,
        secure=settings.oauth_cookie_secure,
        samesite='lax',
        max_age=max(60, int(session.expires_at - session.created_at)),
        path='/',
    )
    return response


def _build_url_with_query(url: str, params: dict[str, str]) -> str:
    parts = urlsplit(url)
    query_pairs = dict()
    if parts.query:
        for kv in parts.query.split('&'):
            if not kv:
                continue
            if '=' in kv:
                k, v = kv.split('=', 1)
            else:
                k, v = kv, ''
            query_pairs[k] = v
    query_pairs.update(params)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query_pairs), parts.fragment)
    )


def _validate_oauth_settings():
    missing = []
    if not settings.oauth_authorize_url:
        missing.append('oauth_authorize_url')
    if not settings.oauth_token_url:
        missing.append('oauth_token_url')
    if not settings.oauth_client_id:
        missing.append('oauth_client_id')
    if not settings.oauth_redirect_uri:
        missing.append('oauth_redirect_uri')
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing OAuth settings: {', '.join(missing)}",
        )


def _exchange_refresh_token(refresh_token: str):
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': settings.oauth_client_id,
    }
    if settings.oauth_client_secret:
        payload['client_secret'] = settings.oauth_client_secret
    if settings.oauth_scope:
        payload['scope'] = settings.oauth_scope
    try:
        with httpx.Client(timeout=settings.oauth_http_timeout_seconds) as client:
            token_resp = client.post(settings.oauth_token_url, data=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f'OAuth refresh request failed: {exc}')
    if token_resp.status_code >= 400:
        raise HTTPException(
            status_code=400,
            detail=f'OAuth refresh failed: {token_resp.text[:300]}',
        )
    token_data = token_resp.json()
    access_token = token_data.get('access_token')
    if not access_token:
        raise HTTPException(
            status_code=400,
            detail='OAuth refresh response missing access_token.',
        )
    return token_data


@router.get('/login')
def oauth_login():
    codex_tokens = _load_poc_codex_tokens()
    if codex_tokens.get('access_token'):
        session = oauth_store.create_session(
            access_token=codex_tokens['access_token'],
            token_type=codex_tokens.get('token_type') or 'Bearer',
            refresh_token=codex_tokens.get('refresh_token'),
            scope=codex_tokens.get('scope'),
            provider_expires_in=(
                codex_tokens['expires_at_unix']
                - int(datetime.now(tz=timezone.utc).timestamp())
                if codex_tokens.get('expires_at_unix')
                else None
            ),
        )
        return _build_success_response_from_session(session)

    _validate_oauth_settings()

    state_item = oauth_store.create_state()
    params = {
        'response_type': 'code',
        'client_id': settings.oauth_client_id,
        'redirect_uri': settings.oauth_redirect_uri,
        'state': state_item.state,
    }
    if settings.oauth_scope:
        params['scope'] = settings.oauth_scope
    if settings.oauth_audience:
        params['audience'] = settings.oauth_audience
    if settings.oauth_use_pkce:
        params['code_challenge'] = oauth_store.generate_code_challenge(
            state_item.code_verifier
        )
        params['code_challenge_method'] = 'S256'

    auth_url = _build_url_with_query(settings.oauth_authorize_url, params)
    return RedirectResponse(url=auth_url, status_code=302)


@router.get('/callback')
def oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    _validate_oauth_settings()
    if error:
        detail = error if not error_description else f'{error}: {error_description}'
        raise HTTPException(status_code=400, detail=detail)
    if not code or not state:
        raise HTTPException(status_code=400, detail='Missing code or state.')

    state_item = oauth_store.pop_state(state)
    if not state_item:
        raise HTTPException(status_code=400, detail='Invalid or expired OAuth state.')

    payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': settings.oauth_redirect_uri,
        'client_id': settings.oauth_client_id,
    }
    if settings.oauth_client_secret:
        payload['client_secret'] = settings.oauth_client_secret
    if settings.oauth_use_pkce:
        payload['code_verifier'] = state_item.code_verifier

    try:
        with httpx.Client(timeout=settings.oauth_http_timeout_seconds) as client:
            token_resp = client.post(settings.oauth_token_url, data=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f'OAuth token request failed: {exc}')

    if token_resp.status_code >= 400:
        raise HTTPException(
            status_code=400,
            detail=f'OAuth token exchange failed: {token_resp.text[:300]}',
        )

    token_data = token_resp.json()
    access_token = token_data.get('access_token')
    if not access_token:
        raise HTTPException(status_code=400, detail='OAuth token response missing access_token.')

    session = oauth_store.create_session(
        access_token=access_token,
        token_type=token_data.get('token_type') or 'Bearer',
        refresh_token=token_data.get('refresh_token'),
        scope=token_data.get('scope'),
        provider_expires_in=token_data.get('expires_in'),
    )

    return _build_success_response_from_session(session)


@router.get('/done')
def oauth_done():
    return HTMLResponse(
        content=(
            '<html><head><meta charset="utf-8"><title>OAuth Done</title></head>'
            '<body style="font-family:Arial,sans-serif;padding:24px;">'
            '<h2>OAuth authentication completed.</h2>'
            '<p>You are now signed in. You can return to your app and call <code>/chat</code>.</p>'
            '<p>If OpenAI web login fails, this page can still be reached via local Codex token sync.</p>'
            '<p><a href="/auth/me">Check login status</a></p>'
            '<p><a href="/docs">Open API docs</a></p>'
            '</body></html>'
        )
    )


@router.get('/me')
def oauth_me(request: Request):
    session_id = request.cookies.get(settings.oauth_session_cookie_name)
    session = oauth_store.get_session(session_id)
    if not session:
        return {'authenticated': False}
    return {
        'authenticated': True,
        'expires_at': datetime.fromtimestamp(
            session.expires_at, tz=timezone.utc
        ).isoformat(),
        'scope': session.scope,
        'token_type': session.token_type,
    }


def _oauth_refresh_impl(request: Request):
    session_id = request.cookies.get(settings.oauth_session_cookie_name)
    session = oauth_store.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=401,
            detail='No active OAuth session. Login first via /auth/login.',
        )

    codex_tokens = _load_poc_codex_tokens()
    if codex_tokens.get('access_token'):
        # POC-first sync path: refresh from local Codex token store, no OAuth params required.
        synced = oauth_store.create_session(
            access_token=codex_tokens['access_token'],
            token_type=codex_tokens.get('token_type') or session.token_type or 'Bearer',
            refresh_token=codex_tokens.get('refresh_token') or session.refresh_token,
            scope=codex_tokens.get('scope') or session.scope,
            provider_expires_in=(
                codex_tokens['expires_at_unix']
                - int(datetime.now(tz=timezone.utc).timestamp())
                if codex_tokens.get('expires_at_unix')
                else None
            ),
        )
        oauth_store.delete_session(session_id)
        return _build_json_session_response(synced)

    _validate_oauth_settings()
    refresh_token = session.refresh_token
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail='Current session does not have a refresh_token.',
        )

    token_data = _exchange_refresh_token(refresh_token)
    new_session = oauth_store.create_session(
        access_token=token_data.get('access_token'),
        token_type=token_data.get('token_type') or session.token_type or 'Bearer',
        refresh_token=token_data.get('refresh_token') or refresh_token,
        scope=token_data.get('scope') or session.scope,
        provider_expires_in=token_data.get('expires_in'),
    )
    oauth_store.delete_session(session_id)
    return _build_json_session_response(new_session)


@router.post('/refresh')
def oauth_refresh(request: Request):
    return _oauth_refresh_impl(request)


@router.get('/refresh')
def oauth_refresh_get(request: Request):
    return _oauth_refresh_impl(request)


@router.post('/logout')
def oauth_logout(request: Request):
    session_id = request.cookies.get(settings.oauth_session_cookie_name)
    oauth_store.delete_session(session_id)
    response = JSONResponse({'logged_out': True})
    response.delete_cookie(settings.oauth_session_cookie_name, path='/')
    return response
