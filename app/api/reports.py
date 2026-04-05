from datetime import date 
 
from fastapi import APIRouter, Depends 
from sqlalchemy.orm import Session 
 
from app.db import get_db 
from app.services.report_service import ReportService 
 
 
router = APIRouter(prefix='/reports', tags=['reports']) 
 
 
@router.get('/daily') 
def get_daily_report(report_date: date = None, db: Session = Depends(get_db)): 
    service = ReportService(db) 
    return service.generate_daily_summary(report_date)
