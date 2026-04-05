from sqlalchemy import select 
from sqlalchemy.orm import joinedload 
 
from app.models.impact import BusinessImpact 
from app.models.metadata import Asset 
from app.services.asset_service import AssetService 
 
 
class ImpactService: 
    def __init__(self, db): 
        self.db = db 
        self.asset_service = AssetService(db) 
 
    def get_business_impact(self, asset_name): 
        asset = self.asset_service.resolve_asset(asset_name) 
        if not asset: 
            return {'found': False, 'message': f'Asset not found: {asset_name}'} 
 
        stmt = ( 
            select(BusinessImpact) 
            .options( 
                joinedload(BusinessImpact.impacted_asset), 
                joinedload(BusinessImpact.impacted_team), 
                joinedload(BusinessImpact.impacted_domain), 
            ) 
            .where(BusinessImpact.source_asset_id == asset.id, BusinessImpact.is_active == True) 
        ) 
        impacts = self.db.execute(stmt).scalars().all() 
 
        impacted_assets = [] 
        impacted_teams = [] 
        impacted_domains = [] 
        for impact in impacts: 
            if impact.impacted_asset: 
                impacted_assets.append({ 
                    'asset': impact.impacted_asset.qualified_name, 
                    'impact_level': impact.impact_level, 
                    'impact_type': impact.impact_type, 
                    'description': impact.description, 
                }) 
            if impact.impacted_team: 
                impacted_teams.append({ 
                    'team': impact.impacted_team.name, 
                    'impact_level': impact.impact_level, 
                    'impact_type': impact.impact_type, 
                    'description': impact.description, 
                }) 
            if impact.impacted_domain: 
                impacted_domains.append({ 
                    'domain': impact.impacted_domain.name, 
                    'impact_level': impact.impact_level, 
                    'impact_type': impact.impact_type, 
                    'description': impact.description, 
                }) 
 
        return { 
            'found': True, 
            'source_asset': asset.qualified_name, 
            'impacted_assets': impacted_assets, 
            'impacted_teams': impacted_teams, 
            'impacted_domains': impacted_domains, 
        } 
 
    def get_impacted_apis(self, asset_name): 
        asset = self.asset_service.resolve_asset(asset_name) 
        if not asset: 
            return {'found': False, 'message': f'Asset not found: {asset_name}'} 
 
        impact_data = self.get_business_impact(asset_name) 
        apis = [] 
        for item in impact_data.get('impacted_assets', []): 
            target = self.asset_service.resolve_asset(item['asset']) 
            if not target: 
                continue 
            is_api = target.system and target.system.name.lower() == 'api' 
            if is_api: 
                apis.append({ 
                    'api_asset': target.qualified_name, 
                    'impact_level': item['impact_level'], 
                    'reason': item['description'], 
                }) 
 
        if not apis: 
            downstream = self.asset_service.get_downstream(asset_name) 
            for node in downstream.get('nodes', []): 
                if node.get('system') and node['system'].lower() == 'api': 
                    apis.append({ 
                        'api_asset': node['qualified_name'], 
                        'impact_level': 'UNKNOWN', 
                        'reason': 'Derived from downstream lineage.', 
                    }) 
 
        return { 
            'found': True, 
            'source_asset': asset.qualified_name, 
            'count': len(apis), 
            'items': apis, 
        }
