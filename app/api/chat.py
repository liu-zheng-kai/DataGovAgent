from time import perf_counter

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from openai import OpenAIError
from sqlalchemy.orm import Session 
 
from app.agent.llm_agent import MetadataAgent 
from app.core.config import settings
from app.core.oauth_store import oauth_store
from app.db import get_db 
from app.schemas.api import ChatRequest 
from app.services.admin_service import AdminService
 
 
router = APIRouter(tags=['chat']) 
 
 
@router.post('/chat')
def chat(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    oauth_access_token = payload.oauth_access_token
    if not oauth_access_token and authorization and authorization.lower().startswith(
        'bearer '
    ):
        oauth_access_token = authorization[7:].strip()
    if not oauth_access_token and settings.openai_auth_mode == 'oauth_token':
        session_id = request.cookies.get(settings.oauth_session_cookie_name)
        oauth_access_token = oauth_store.get_access_token(session_id)

    try:
        t0 = perf_counter()
        agent = MetadataAgent(db, oauth_access_token=oauth_access_token)
        response = agent.ask(
            payload.question,
            scene_type=payload.scene_type,
            prompt_template_key=payload.prompt_template_key,
        )
        duration_ms = int((perf_counter() - t0) * 1000)
        try:
            session_key = AdminService(db).record_chat_exchange(
                question=payload.question,
                answer=response.get('answer', ''),
                tool_trace=response.get('tool_trace', []),
                session_key=payload.session_id,
                channel_external_id=payload.channel_id,
                duration_ms=duration_ms,
                scene_type=response.get('scene_type') or payload.scene_type,
                prompt_template_key=(
                    response.get('prompt_template_key') or payload.prompt_template_key
                ),
            )
            response['session_id'] = session_key
        except Exception:
            # Chat response should still be returned even if admin trace persistence fails.
            pass
        return response
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OpenAIError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
