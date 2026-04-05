from fastapi import APIRouter, Depends, HTTPException 
from sqlalchemy.orm import Session 
 
from app.db import get_db 
from app.services.asset_service import AssetService 
 
 
router = APIRouter(prefix='/assets', tags=['assets']) 
 
 
@router.get('/{name}') 
def get_asset(name: str, db: Session = Depends(get_db)): 
    service = AssetService(db) 
    data = service.get_asset_detail(name) 
    if not data.get('found'): 
        raise HTTPException(status_code=404, detail=data.get('message')) 
    return data 
 
 
@router.get('/{name}/downstream') 
def get_downstream(name: str, db: Session = Depends(get_db)): 
    service = AssetService(db) 
    data = service.get_downstream(name) 
    if not data.get('found'): 
        raise HTTPException(status_code=404, detail=data.get('message')) 
    return data 
 
 
@router.get('/{name}/upstream') 
def get_upstream(name: str, db: Session = Depends(get_db)): 
    service = AssetService(db) 
    data = service.get_upstream(name) 
    if not data.get('found'): 
        raise HTTPException(status_code=404, detail=data.get('message')) 
    return data
