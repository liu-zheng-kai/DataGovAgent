from fastapi import APIRouter, Depends, HTTPException 
from sqlalchemy.orm import Session 
 
from app.db import get_db 
from app.services.runtime_service import RuntimeService 
 
 
router = APIRouter(prefix='/domains', tags=['domains']) 
 
 
@router.get('/{name}/health') 
def get_domain_health(name: str, db: Session = Depends(get_db)): 
    service = RuntimeService(db) 
    data = service.get_domain_health(name) 
    if not data.get('found'): 
        raise HTTPException(status_code=404, detail=data.get('message')) 
    return data
