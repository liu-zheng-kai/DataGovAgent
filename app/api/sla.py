from fastapi import APIRouter, Depends 
from sqlalchemy.orm import Session 
 
from app.db import get_db 
from app.services.runtime_service import RuntimeService 
 
 
router = APIRouter(prefix='/sla', tags=['sla']) 
 
 
@router.get('/risks') 
def get_sla_risks(db: Session = Depends(get_db)): 
    service = RuntimeService(db) 
    return service.get_sla_risk_assets()
