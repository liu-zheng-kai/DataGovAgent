from datetime import date 
 
from app.core.serializer import to_jsonable 
from app.services.asset_service import AssetService 
from app.services.impact_service import ImpactService 
from app.services.report_service import ReportService 
from app.services.runtime_service import RuntimeService 
 
 
class MetadataToolRegistry: 
    def __init__(self, db): 
        self.asset_service = AssetService(db) 
        self.runtime_service = RuntimeService(db) 
        self.impact_service = ImpactService(db) 
        self.report_service = ReportService(db) 
 
    def get_asset(self, asset_name): 
        return to_jsonable(self.asset_service.get_asset(asset_name)) 
 
    def get_asset_detail(self, asset_name): 
        return to_jsonable(self.asset_service.get_asset_detail(asset_name)) 
 
    def get_downstream(self, asset_name): 
        return to_jsonable(self.asset_service.get_downstream(asset_name)) 
 
    def get_upstream(self, asset_name): 
        return to_jsonable(self.asset_service.get_upstream(asset_name)) 
 
    def get_failed_runs(self, domain=None): 
        return to_jsonable(self.runtime_service.get_failed_runs(domain=domain)) 
 
    def get_domain_health(self, domain_name): 
        return to_jsonable(self.runtime_service.get_domain_health(domain_name)) 
 
    def get_business_impact(self, asset_name): 
        return to_jsonable(self.impact_service.get_business_impact(asset_name)) 
 
    def get_impacted_apis(self, asset_name): 
        return to_jsonable(self.impact_service.get_impacted_apis(asset_name)) 
 
    def get_sla_risk_assets(self): 
        return to_jsonable(self.runtime_service.get_sla_risk_assets()) 
 
    def generate_daily_summary(self, report_date): 
        parsed = date.fromisoformat(report_date) if report_date else date.today() 
        return to_jsonable(self.report_service.generate_daily_summary(parsed))
