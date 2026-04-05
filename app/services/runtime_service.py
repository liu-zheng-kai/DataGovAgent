from datetime import date, datetime, time, timedelta 
 
from sqlalchemy import func, select 
from sqlalchemy.orm import joinedload 
 
from app.models.metadata import Asset, SlaDefinition 
from app.models.reference import BusinessDomain 
from app.models.runtime import AssetRuntimeStatus, DomainHealthSnapshot, RuntimeEvent 
 
 
class RuntimeService: 
    def __init__(self, db): 
        self.db = db 
 
    def _day_window(self, target_date): 
        if target_date is None: 
            target_date = date.today() 
        start = datetime.combine(target_date, time.min) 
        end = start + timedelta(days=1) 
        return start, end 
 
    def get_failed_runs(self, domain=None, target_date=None): 
        start, end = self._day_window(target_date) 
        stmt = ( 
            select(RuntimeEvent) 
            .options(joinedload(RuntimeEvent.asset).joinedload(Asset.domain)) 
            .where( 
                RuntimeEvent.status == 'FAILED', 
                RuntimeEvent.occurred_at >= start, 
                RuntimeEvent.occurred_at < end, 
            ) 
            .order_by(RuntimeEvent.occurred_at.desc()) 
        ) 
        events = self.db.execute(stmt).scalars().all() 
 
        if domain: 
            domain_key = domain.lower() 
            events = [ 
                item for item in events 
                if item.asset and item.asset.domain and item.asset.domain.name.lower() == domain_key 
            ] 
 
        return { 
            'count': len(events), 
            'items': [ 
                { 
                    'asset': item.asset.qualified_name if item.asset else None, 
                    'domain': item.asset.domain.name if item.asset and item.asset.domain else None, 
                    'status': item.status, 
                    'severity': item.severity, 
                    'occurred_at': item.occurred_at, 
                    'error_code': item.error_code, 
                    'error_message': item.error_message, 
                } 
                for item in events 
            ], 
        }
 
    def get_domain_health(self, domain_name): 
        domain = self.db.execute( 
            select(BusinessDomain).where(func.lower(BusinessDomain.name) == domain_name.lower()) 
        ).scalar_one_or_none() 
        if not domain: 
            return {'found': False, 'message': f'Domain not found: {domain_name}'} 
 
        snapshot = self.db.execute( 
            select(DomainHealthSnapshot) 
            .where(DomainHealthSnapshot.domain_id == domain.id) 
            .order_by(DomainHealthSnapshot.observed_at.desc()) 
        ).scalars().first() 
 
        failed = self.get_failed_runs(domain=domain.name) 
        if not snapshot: 
            return { 
                'found': True, 
                'domain': domain.name, 
                'health_status': 'UNKNOWN', 
                'observed_at': None, 
                'reason': 'No health snapshot found.', 
                'failed_runs_today': failed['count'], 
            } 
 
        return { 
            'found': True, 
            'domain': domain.name, 
            'health_status': snapshot.status, 
            'observed_at': snapshot.observed_at, 
            'reason': snapshot.reason, 
            'failed_runs_today': failed['count'], 
        } 
 
    def get_sla_risk_assets(self): 
        stmt = ( 
            select(AssetRuntimeStatus, Asset, SlaDefinition) 
            .join(Asset, Asset.id == AssetRuntimeStatus.asset_id) 
            .join(SlaDefinition, SlaDefinition.asset_id == Asset.id) 
            .options(joinedload(Asset.domain)) 
        ) 
        rows = self.db.execute(stmt).all() 
        risks = [] 
        for runtime, asset, sla in rows: 
            is_warning = runtime.delay_minutes >= sla.warning_after_minutes 
            is_failure = runtime.status in ('FAILED', 'DEGRADED') 
            if is_warning or is_failure: 
                risks.append({ 
                    'asset': asset.qualified_name, 
                    'domain': asset.domain.name if asset.domain else None, 
                    'status': runtime.status, 
                    'delay_minutes': runtime.delay_minutes, 
                    'warning_after_minutes': sla.warning_after_minutes, 
                    'breach_after_minutes': sla.breach_after_minutes, 
                }) 
        risks.sort(key=lambda x: (x['delay_minutes'], x['status']), reverse=True) 
        return {'count': len(risks), 'items': risks} 
 
    def get_red_domains(self): 
        stmt = ( 
            select(DomainHealthSnapshot, BusinessDomain) 
            .join(BusinessDomain, BusinessDomain.id == DomainHealthSnapshot.domain_id) 
            .where(DomainHealthSnapshot.status == 'RED') 
            .order_by(DomainHealthSnapshot.observed_at.desc()) 
        ) 
        rows = self.db.execute(stmt).all() 
        seen = set() 
        result = [] 
        for snapshot, domain in rows: 
            if domain.id in seen: 
                continue 
            seen.add(domain.id) 
            result.append({ 
                'domain': domain.name, 
                'status': snapshot.status, 
                'observed_at': snapshot.observed_at, 
                'reason': snapshot.reason, 
            }) 
        return result
