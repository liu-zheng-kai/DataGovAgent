from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.admin import (
    ChannelCreateRequest,
    ChannelUpdateRequest,
    JobCreateRequest,
    MemoryCreateRequest,
    MemoryUpdateRequest,
    PromptTemplateCreateRequest,
    PromptTemplatePreviewRequest,
    PromptTemplateUpdateRequest,
    ToolPromptBindingCreateRequest,
    ToolPromptBindingUpdateRequest,
    ToolUpdateRequest,
)
from app.services.admin_service import AdminService


router = APIRouter(tags=['admin'])
_STATIC_INDEX = Path(__file__).resolve().parents[1] / 'static' / 'admin' / 'index.html'


@router.get('/admin')
def admin_console():
    if not _STATIC_INDEX.exists():
        raise HTTPException(status_code=404, detail='Admin page is not available.')
    return FileResponse(_STATIC_INDEX)


@router.get('/admin/')
def admin_console_redirect():
    return RedirectResponse('/admin', status_code=302)


@router.get('/api/admin/dashboard')
def get_dashboard(db: Session = Depends(get_db)):
    return AdminService(db).get_dashboard()


@router.get('/api/admin/tools')
def list_tools(
    q: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return AdminService(db).list_tools(q=q, enabled=enabled)


@router.get('/api/admin/tools/{tool_id}')
def get_tool(tool_id: int, db: Session = Depends(get_db)):
    data = AdminService(db).get_tool(tool_id)
    if not data:
        raise HTTPException(status_code=404, detail='Tool not found.')
    return data


@router.put('/api/admin/tools/{tool_id}')
def update_tool(tool_id: int, payload: ToolUpdateRequest, db: Session = Depends(get_db)):
    data = AdminService(db).update_tool(tool_id, payload.model_dump(exclude_unset=True))
    if not data:
        raise HTTPException(status_code=404, detail='Tool not found.')
    return data


@router.get('/api/admin/tool-versions')
def list_tool_versions(tool_id: int | None = Query(default=None), db: Session = Depends(get_db)):
    return AdminService(db).list_tool_versions(tool_id=tool_id)


@router.get('/api/admin/data-sources')
def list_data_sources(db: Session = Depends(get_db)):
    return AdminService(db).list_data_sources()


@router.get('/api/admin/data-sources/{source_id}')
def get_data_source(source_id: int, db: Session = Depends(get_db)):
    data = AdminService(db).get_data_source(source_id)
    if not data:
        raise HTTPException(status_code=404, detail='Data source not found.')
    return data


@router.get('/api/admin/data-sources/{source_id}/tables')
def list_data_source_tables(
    source_id: int,
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return AdminService(db).list_data_source_tables(source_id=source_id, q=q)


@router.get('/api/admin/preview')
def get_preview(
    source_id: int | None = Query(default=None),
    table_id: int | None = Query(default=None),
    mode: str = Query(default='json'),
    db: Session = Depends(get_db),
):
    data = AdminService(db).get_preview(
        source_id=source_id,
        table_id=table_id,
        format_mode=mode,
    )
    if data is None:
        raise HTTPException(status_code=404, detail='Preview target not found.')
    return data


@router.get('/api/admin/chats')
def list_chats(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return AdminService(db).list_chats(limit=limit)


@router.get('/api/admin/chats/{chat_id}')
def get_chat(chat_id: int, db: Session = Depends(get_db)):
    data = AdminService(db).get_chat(chat_id)
    if not data:
        raise HTTPException(status_code=404, detail='Chat not found.')
    return data


@router.get('/api/admin/memories')
def list_memories(
    memory_type: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return AdminService(db).list_memories(memory_type=memory_type, q=q)


@router.post('/api/admin/memories')
def create_memory(payload: MemoryCreateRequest, db: Session = Depends(get_db)):
    return AdminService(db).create_memory(payload.model_dump())


@router.put('/api/admin/memories/{memory_id}')
def update_memory(memory_id: int, payload: MemoryUpdateRequest, db: Session = Depends(get_db)):
    data = AdminService(db).update_memory(memory_id, payload.model_dump(exclude_unset=True))
    if not data:
        raise HTTPException(status_code=404, detail='Memory not found.')
    return data


@router.delete('/api/admin/memories/{memory_id}')
def delete_memory(memory_id: int, db: Session = Depends(get_db)):
    deleted = AdminService(db).delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail='Memory not found.')
    return {'deleted': True}


@router.get('/api/admin/jobs')
def list_jobs(db: Session = Depends(get_db)):
    return AdminService(db).list_jobs()


@router.post('/api/admin/jobs')
def create_job(payload: JobCreateRequest, db: Session = Depends(get_db)):
    try:
        return AdminService(db).create_job(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get('/api/admin/jobs/{job_id}/runs')
def list_job_runs(
    job_id: int,
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return AdminService(db).list_job_runs(job_id=job_id, limit=limit)


@router.post('/api/admin/jobs/{job_id}/run')
def run_job(job_id: int, db: Session = Depends(get_db)):
    data = AdminService(db).run_job(job_id)
    if not data:
        raise HTTPException(status_code=404, detail='Job not found.')
    return data


@router.get('/api/admin/channels')
def list_channels(db: Session = Depends(get_db)):
    return AdminService(db).list_channels()


@router.post('/api/admin/channels')
def create_channel(payload: ChannelCreateRequest, db: Session = Depends(get_db)):
    try:
        return AdminService(db).create_channel(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put('/api/admin/channels/{channel_pk}')
def update_channel(
    channel_pk: int,
    payload: ChannelUpdateRequest,
    db: Session = Depends(get_db),
):
    data = AdminService(db).update_channel(channel_pk, payload.model_dump(exclude_unset=True))
    if not data:
        raise HTTPException(status_code=404, detail='Channel not found.')
    return data


@router.get('/api/admin/logs/trace')
def list_trace(
    session_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return AdminService(db).list_trace(session_id=session_id, limit=limit)


@router.get('/api/admin/assets')
def list_assets(
    q: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return AdminService(db).list_assets(q=q, limit=limit)


@router.get('/api/admin/lineage')
def get_lineage(
    asset_name: str = Query(...),
    direction: str = Query(default='downstream'),
    db: Session = Depends(get_db),
):
    data = AdminService(db).get_lineage(asset_name=asset_name, direction=direction)
    if not data.get('found'):
        raise HTTPException(status_code=404, detail=data.get('message') or 'Asset not found.')
    return data


@router.get('/api/admin/prompt-templates')
def list_prompt_templates(
    q: str | None = Query(default=None),
    scene_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return AdminService(db).list_prompt_templates(
        q=q,
        scene_type=scene_type,
        status=status,
        limit=limit,
    )


@router.get('/api/admin/prompt-templates/{template_id}')
def get_prompt_template(template_id: int, db: Session = Depends(get_db)):
    data = AdminService(db).get_prompt_template(template_id)
    if not data:
        raise HTTPException(status_code=404, detail='Prompt template not found.')
    return data


@router.post('/api/admin/prompt-templates')
def create_prompt_template(
    payload: PromptTemplateCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        return AdminService(db).create_prompt_template(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put('/api/admin/prompt-templates/{template_id}')
def update_prompt_template(
    template_id: int,
    payload: PromptTemplateUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        data = AdminService(db).update_prompt_template(
            template_id,
            payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not data:
        raise HTTPException(status_code=404, detail='Prompt template not found.')
    return data


@router.delete('/api/admin/prompt-templates/{template_id}')
def delete_prompt_template(template_id: int, db: Session = Depends(get_db)):
    deleted = AdminService(db).delete_prompt_template(template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail='Prompt template not found.')
    return {'deleted': True}


@router.post('/api/admin/prompt-templates/{template_id}/set-default')
def set_default_prompt_template(template_id: int, db: Session = Depends(get_db)):
    data = AdminService(db).set_default_prompt_template(template_id)
    if not data:
        raise HTTPException(status_code=404, detail='Prompt template not found.')
    return data


@router.post('/api/admin/prompt-templates/{template_id}/preview')
def preview_prompt_template(
    template_id: int,
    payload: PromptTemplatePreviewRequest,
    db: Session = Depends(get_db),
):
    data = AdminService(db).preview_prompt_template(
        template_id,
        question=payload.question,
        params=payload.params,
    )
    if not data:
        raise HTTPException(status_code=404, detail='Prompt template not found.')
    return data


@router.get('/api/admin/tools/{tool_id}/prompt-bindings')
def list_tool_prompt_bindings(tool_id: int, db: Session = Depends(get_db)):
    return AdminService(db).list_tool_prompt_bindings(tool_id)


@router.post('/api/admin/tools/{tool_id}/prompt-bindings')
def create_tool_prompt_binding(
    tool_id: int,
    payload: ToolPromptBindingCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        data = AdminService(db).create_tool_prompt_binding(tool_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not data:
        raise HTTPException(status_code=404, detail='Tool not found.')
    return data


@router.put('/api/admin/tools/{tool_id}/prompt-bindings/{binding_id}')
def update_tool_prompt_binding(
    tool_id: int,
    binding_id: int,
    payload: ToolPromptBindingUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        data = AdminService(db).update_tool_prompt_binding(
            tool_id,
            binding_id,
            payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not data:
        raise HTTPException(status_code=404, detail='Tool binding not found.')
    return data


@router.delete('/api/admin/tools/{tool_id}/prompt-bindings/{binding_id}')
def delete_tool_prompt_binding(
    tool_id: int,
    binding_id: int,
    db: Session = Depends(get_db),
):
    deleted = AdminService(db).delete_tool_prompt_binding(tool_id, binding_id)
    if not deleted:
        raise HTTPException(status_code=404, detail='Tool binding not found.')
    return {'deleted': True}


@router.get('/api/admin/search/suggestions')
def search_suggestions(
    type: str = Query(..., alias='type'),
    keyword: str = Query(default=''),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return AdminService(db).search_suggestions(
        suggestion_type=type,
        keyword=keyword,
        limit=limit,
    )
