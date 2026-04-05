import json

import app.models  # noqa: F401
from app.db import Base, SessionLocal, engine
from app.services.azure_ingestion_service import AzureIngestionService


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        result = AzureIngestionService(db).sync_adf_metadata()
        print(json.dumps(result, indent=2, default=str))
    finally:
        db.close()


if __name__ == '__main__':
    main()
