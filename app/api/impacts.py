from fastapi import APIRouter, Depends, HTTPException 
from sqlalchemy.orm import Session 
 
from app.db import get_db 
from app.services.impact_service import ImpactService 
 
 
router = APIRouter(prefix='/impacts', tags=['impacts']) 
 
 
@router.get('/{asset_name}') 
def get_business_impact(asset_name: str, db: Session = Depends(get_db)): 
    service = ImpactService(db) 
    data = service.get_business_impact(asset_name) 
    if not data.get('found'): 
        raise HTTPException(status_code=404, detail=data.get('message')) 
    return data 
 
 
@router.get('/{asset_name}/apis') 
def get_impacted_apis(asset_name: str, db: Session = Depends(get_db)): 
    service = ImpactService(db) 
    data = service.get_impacted_apis(asset_name) 
    if not data.get('found'): 
        raise HTTPException(status_code=404, detail=data.get('message')) 
    return data
