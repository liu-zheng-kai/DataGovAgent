from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
 
import app.models  # noqa: F401 
from app.api import admin, assets, auth, chat, domains, impacts, reports, runtime, sla
from app.core.config import settings 
from app.db import Base, SessionLocal, engine
from app.services.admin_service import bootstrap_admin_catalog
 
 
app = FastAPI(title=settings.app_name) 


def _startup_links():
    base_url = settings.app_public_base_url.rstrip('/')
    print(f'[Startup] Health: {base_url}/health')
    print(f'[Startup] Docs:   {base_url}/docs')
    if settings.openai_auth_mode == 'oauth_token':
        print(f'[Startup] OAuth login: {base_url}/auth/login')
        print(f'[Startup] OAuth status: {base_url}/auth/me')
        print(f'[Startup] OAuth refresh: {base_url}/auth/refresh')


@app.on_event('startup') 
def on_startup(): 
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        bootstrap_admin_catalog(db)
    finally:
        db.close()
    _startup_links()
 
 
static_dir = Path(__file__).resolve().parent / 'static'
if static_dir.exists():
    app.mount('/static', StaticFiles(directory=static_dir), name='static')


app.include_router(admin.router)
app.include_router(auth.router) 
app.include_router(chat.router) 
app.include_router(assets.router) 
app.include_router(runtime.router) 
app.include_router(domains.router) 
app.include_router(impacts.router) 
app.include_router(sla.router) 
app.include_router(reports.router) 
 
 
@app.get('/health') 
def health(): 
    return {'status': 'ok', 'app': settings.app_name}
