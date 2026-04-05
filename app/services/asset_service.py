from collections import deque 
 
from sqlalchemy import func, select 
from sqlalchemy.orm import joinedload 
 
from app.models.metadata import Asset, AssetDependency, SlaDefinition 
from app.models.runtime import AssetRuntimeStatus 
 
 
class AssetService: 
    def __init__(self, db): 
        self.db = db 
 
    def _to_summary(self, asset): 
        return { 
            'id': asset.id, 
            'name': asset.name, 
            'qualified_name': asset.qualified_name, 
            'asset_type': asset.asset_type.name if asset.asset_type else None, 
            'system': asset.system.name if asset.system else None, 
            'domain': asset.domain.name if asset.domain else None, 
            'owner_team': asset.owner_team.name if asset.owner_team else None, 
        }
 
    def resolve_asset(self, asset_name): 
        key = asset_name.strip().lower() 
        stmt = ( 
            select(Asset) 
            .options( 
                joinedload(Asset.asset_type), 
                joinedload(Asset.system), 
                joinedload(Asset.domain), 
                joinedload(Asset.owner_team), 
            ) 
            .where(func.lower(Asset.qualified_name) == key) 
        ) 
        asset = self.db.execute(stmt).scalar_one_or_none() 
        if asset: 
            return asset 
 
        stmt = ( 
            select(Asset) 
            .options( 
                joinedload(Asset.asset_type), 
                joinedload(Asset.system), 
                joinedload(Asset.domain), 
                joinedload(Asset.owner_team), 
            ) 
            .where(func.lower(Asset.name) == key) 
            .order_by(Asset.id) 
        ) 
        return self.db.execute(stmt).scalars().first() 
 
    def get_asset(self, asset_name): 
        asset = self.resolve_asset(asset_name) 
        if not asset: 
            return {'found': False, 'message': f'Asset not found: {asset_name}'} 
        return {'found': True, 'asset': self._to_summary(asset)} 
 
    def get_asset_detail(self, asset_name): 
        asset = self.resolve_asset(asset_name) 
        if not asset: 
            return {'found': False, 'message': f'Asset not found: {asset_name}'} 
 
        runtime = self.db.execute( 
            select(AssetRuntimeStatus).where(AssetRuntimeStatus.asset_id == asset.id) 
        ).scalar_one_or_none() 
        sla = self.db.execute( 
            select(SlaDefinition).where(SlaDefinition.asset_id == asset.id) 
        ).scalar_one_or_none() 
 
        detail = self._to_summary(asset) 
        detail['description'] = asset.description 
        detail['refresh_frequency'] = asset.refresh_frequency 
        detail['runtime_status'] = runtime.status if runtime else None 
        detail['runtime_delay_minutes'] = runtime.delay_minutes if runtime else None 
        detail['sla_expected_interval_minutes'] = sla.expected_interval_minutes if sla else None 
        detail['sla_warning_after_minutes'] = sla.warning_after_minutes if sla else None 
        detail['sla_breach_after_minutes'] = sla.breach_after_minutes if sla else None 
        return {'found': True, 'asset': detail}
 
    def _lineage(self, asset_name, direction): 
        asset = self.resolve_asset(asset_name) 
        if not asset: 
            return {'found': False, 'message': f'Asset not found: {asset_name}'} 
 
        visited = {asset.id} 
        node_map = {asset.id: asset} 
        edges = [] 
        frontier = deque([(asset.id, 0)]) 
 
        while frontier: 
            current_id, depth = frontier.popleft() 
            if depth == 20: 
                continue 
 
            if direction == 'downstream': 
                stmt = ( 
                    select(AssetDependency) 
                    .options( 
                        joinedload(AssetDependency.dependency_type), 
                        joinedload(AssetDependency.upstream_asset).joinedload(Asset.asset_type), 
                        joinedload(AssetDependency.upstream_asset).joinedload(Asset.system), 
                        joinedload(AssetDependency.upstream_asset).joinedload(Asset.domain), 
                        joinedload(AssetDependency.upstream_asset).joinedload(Asset.owner_team), 
                        joinedload(AssetDependency.downstream_asset).joinedload(Asset.asset_type), 
                        joinedload(AssetDependency.downstream_asset).joinedload(Asset.system), 
                        joinedload(AssetDependency.downstream_asset).joinedload(Asset.domain), 
                        joinedload(AssetDependency.downstream_asset).joinedload(Asset.owner_team), 
                    ) 
                    .where(AssetDependency.upstream_asset_id == current_id, AssetDependency.is_active == True) 
                ) 
                deps = self.db.execute(stmt).scalars().all() 
                for dep in deps: 
                    next_asset = dep.downstream_asset 
                    edges.append({ 
                        'upstream_asset': dep.upstream_asset.qualified_name, 
                        'downstream_asset': dep.downstream_asset.qualified_name, 
                        'dependency_type': dep.dependency_type.name if dep.dependency_type else 'UNKNOWN', 
                    }) 
                    if next_asset and next_asset.id not in visited: 
                        visited.add(next_asset.id) 
                        node_map[next_asset.id] = next_asset 
                        frontier.append((next_asset.id, depth + 1)) 
            else: 
                stmt = ( 
                    select(AssetDependency) 
                    .options( 
                        joinedload(AssetDependency.dependency_type), 
                        joinedload(AssetDependency.upstream_asset).joinedload(Asset.asset_type), 
                        joinedload(AssetDependency.upstream_asset).joinedload(Asset.system), 
                        joinedload(AssetDependency.upstream_asset).joinedload(Asset.domain), 
                        joinedload(AssetDependency.upstream_asset).joinedload(Asset.owner_team), 
                        joinedload(AssetDependency.downstream_asset).joinedload(Asset.asset_type), 
                        joinedload(AssetDependency.downstream_asset).joinedload(Asset.system), 
                        joinedload(AssetDependency.downstream_asset).joinedload(Asset.domain), 
                        joinedload(AssetDependency.downstream_asset).joinedload(Asset.owner_team), 
                    ) 
                    .where(AssetDependency.downstream_asset_id == current_id, AssetDependency.is_active == True) 
                ) 
                deps = self.db.execute(stmt).scalars().all() 
                for dep in deps: 
                    next_asset = dep.upstream_asset 
                    edges.append({ 
                        'upstream_asset': dep.upstream_asset.qualified_name, 
                        'downstream_asset': dep.downstream_asset.qualified_name, 
                        'dependency_type': dep.dependency_type.name if dep.dependency_type else 'UNKNOWN', 
                    }) 
                    if next_asset and next_asset.id not in visited: 
                        visited.add(next_asset.id) 
                        node_map[next_asset.id] = next_asset 
                        frontier.append((next_asset.id, depth + 1)) 
 
        nodes = [self._to_summary(item) for item in node_map.values()] 
        return { 
            'found': True, 
            'root_asset': asset.qualified_name, 
            'direction': direction, 
            'nodes': nodes, 
            'edges': edges, 
        } 
 
    def get_downstream(self, asset_name): 
        return self._lineage(asset_name, 'downstream') 
 
    def get_upstream(self, asset_name): 
        return self._lineage(asset_name, 'upstream')
