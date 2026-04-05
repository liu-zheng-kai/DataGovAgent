from datetime import date 
 
from sqlalchemy import select 
 
from app.core.serializer import to_jsonable 
from app.models.impact import BusinessImpact 
from app.models.metadata import Asset 
from app.models.report import DailySummaryReport 
from app.services.runtime_service import RuntimeService 
 
 
class ReportService: 
    def __init__(self, db): 
        self.db = db 
        self.runtime_service = RuntimeService(db) 
 
    def generate_daily_summary(self, target_date=None): 
        if target_date is None: 
            target_date = date.today() 
 
        failed = self.runtime_service.get_failed_runs(target_date=target_date) 
        sla_risks = self.runtime_service.get_sla_risk_assets() 
        red_domains = self.runtime_service.get_red_domains() 
 
        high_impact_stmt = ( 
            select(BusinessImpact, Asset) 
            .join(Asset, Asset.id == BusinessImpact.source_asset_id) 
            .where(BusinessImpact.is_active == True, BusinessImpact.impact_level.in_(['CRITICAL', 'HIGH'])) 
        ) 
        high_rows = self.db.execute(high_impact_stmt).all() 
        high_items = [] 
        for impact, asset in high_rows: 
            high_items.append({'source_asset': asset.qualified_name, 'impact_level': impact.impact_level, 'impact_type': impact.impact_type, 'description': impact.description}) 
 
        report = { 
            'report_date': target_date, 
            'failed_jobs': failed['items'], 
            'sla_risks': sla_risks['items'], 
            'red_domains': red_domains, 
            'high_impact_assets': high_items, 
        } 
        json_report = to_jsonable(report) 
 
        existing = self.db.execute(select(DailySummaryReport).where(DailySummaryReport.report_date == target_date)).scalar_one_or_none() 
        if existing: 
            existing.summary_json = json_report 
        else: 
            self.db.add(DailySummaryReport(report_date=target_date, summary_json=json_report)) 
        self.db.commit() 
        return json_report
