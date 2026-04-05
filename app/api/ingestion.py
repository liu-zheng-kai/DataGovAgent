from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.azure_ingestion_service import AzureIngestionService, AzureIntegrationError


router = APIRouter(tags=['ingestion'])


@router.get('/api/admin/ingestion/sources')
def list_ingestion_sources(db: Session = Depends(get_db)):
    return AzureIngestionService(db).list_source_states()


@router.get('/api/admin/ingestion/jobs')
def list_ingestion_jobs(
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return AzureIngestionService(db).list_ingestion_jobs(limit=limit)


@router.post('/api/admin/ingestion/adf/sync')
def sync_adf_metadata(db: Session = Depends(get_db)):
    try:
        return AzureIngestionService(db).sync_adf_metadata()
    except AzureIntegrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
