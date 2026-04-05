from fastapi import APIRouter, Depends 
from sqlalchemy.orm import Session 
 
from app.db import get_db 
from app.services.runtime_service import RuntimeService 
 
 
router = APIRouter(prefix='/runtime', tags=['runtime']) 
 
 
@router.get('/failed') 
def get_failed_runs(domain: str = None, db: Session = Depends(get_db)): 
    service = RuntimeService(db) 
    return service.get_failed_runs(domain=domain)
