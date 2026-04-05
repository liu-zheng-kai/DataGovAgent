from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = 'DataGovAgent'
    env: str = 'local'
    app_public_base_url: str = 'http://127.0.0.1:8000'
    database_url: str = Field(
        default='mysql+pymysql://root:root@localhost:3306/metadata_governance'
    )
    database_fallback_url: str = 'sqlite:///./metadata_governance.db'
    database_fallback_on_connect_error: bool = True
    llm_provider: Literal['openai', 'gemini'] = 'openai'
    openai_auth_mode: Literal['api_key', 'oauth_token'] = 'api_key'
    openai_api_key: str = ''
    openai_oauth_token: str = ''
    openai_oauth_token_file: str = '~/.codex/auth.json'
    openai_model: str = 'gpt-4o-mini'
    openai_base_url: str = 'https://api.openai.com/v1'
    gemini_api_key: str = ''
    gemini_model: str = 'gemini-3-flash-preview'
    gemini_base_url: str = 'https://generativelanguage.googleapis.com/v1beta/openai/'
    agent_max_iterations: int = 6
    oauth_authorize_url: str = ''
    oauth_token_url: str = ''
    oauth_client_id: str = ''
    oauth_client_secret: str = ''
    oauth_redirect_uri: str = 'http://127.0.0.1:8000/auth/callback'
    oauth_scope: str = 'openid profile email'
    oauth_audience: str = ''
    oauth_state_ttl_seconds: int = 300
    oauth_session_ttl_seconds: int = 28800
    oauth_session_cookie_name: str = 'mg_oauth_session'
    oauth_cookie_secure: bool = False
    oauth_use_pkce: bool = True
    oauth_http_timeout_seconds: int = 20
    oauth_success_redirect_url: str = ''

    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='ignore'
    )


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()
