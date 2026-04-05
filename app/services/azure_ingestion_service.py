from __future__ import annotations

import hashlib
import json
from datetime import datetime
from urllib import error, parse, request

from sqlalchemy import delete, func, select

from app.core.config import settings
from app.models.ingestion import IngestionJob, RawMetadataSnapshot, SourceSyncState
from app.models.metadata import Asset, AssetDependency, AssetProperty, AssetVersion
from app.models.reference import AssetType, BusinessDomain, DependencyType, System, Team


class AzureIntegrationError(RuntimeError):
    pass


class AzureManagementClient:
    def __init__(self):
        self._access_token: str | None = None

    def _require_settings(self):
        required = {
            'azure_tenant_id': settings.azure_tenant_id,
            'azure_client_id': settings.azure_client_id,
            'azure_client_secret': settings.azure_client_secret,
            'azure_subscription_id': settings.azure_subscription_id,
            'azure_resource_group': settings.azure_resource_group,
            'azure_data_factory_name': settings.azure_data_factory_name,
        }
        missing = [key for key, value in required.items() if not value.strip()]
        if missing:
            raise AzureIntegrationError(
                f'Missing Azure settings: {", ".join(missing)}'
            )

    def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token

        self._require_settings()
        body = parse.urlencode(
            {
                'grant_type': 'client_credentials',
                'client_id': settings.azure_client_id,
                'client_secret': settings.azure_client_secret,
                'scope': settings.azure_oauth_scope,
            }
        ).encode('utf-8')
        token_url = (
            f'https://login.microsoftonline.com/{settings.azure_tenant_id}/oauth2/v2.0/token'
        )
        req = request.Request(
            token_url,
            data=body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            method='POST',
        )
        try:
            with request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode('utf-8'))
        except error.HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            raise AzureIntegrationError(
                f'Azure OAuth token request failed: {exc.code} {detail}'
            ) from exc
        except error.URLError as exc:
            raise AzureIntegrationError(f'Azure OAuth token request failed: {exc}') from exc

        token = payload.get('access_token')
        if not token:
            raise AzureIntegrationError('Azure OAuth token response did not include access_token.')
        self._access_token = token
        return token

    def _get_json(self, url: str) -> dict:
        token = self._get_access_token()
        req = request.Request(
            url,
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
            method='GET',
        )
        try:
            with request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except error.HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            raise AzureIntegrationError(
                f'Azure management request failed: {exc.code} {detail}'
            ) from exc
        except error.URLError as exc:
            raise AzureIntegrationError(f'Azure management request failed: {exc}') from exc

    def list_resources(self, entity_path: str) -> list[dict]:
        base = settings.azure_management_base_url.rstrip('/')
        factory_path = (
            f'/subscriptions/{settings.azure_subscription_id}'
            f'/resourceGroups/{settings.azure_resource_group}'
            f'/providers/Microsoft.DataFactory/factories/{settings.azure_data_factory_name}'
        )
        next_url = (
            f'{base}{factory_path}/{entity_path}?api-version={settings.azure_management_api_version}'
        )
        items: list[dict] = []
        while next_url:
            payload = self._get_json(next_url)
            items.extend(payload.get('value', []))
            next_url = payload.get('nextLink')
        return items


class AzureIngestionService:
    def __init__(self, db):
        self.db = db
        self.client = AzureManagementClient()

    @property
    def source_name(self) -> str:
        factory = settings.azure_data_factory_name or 'unset-factory'
        return f'azure_adf:{factory}'

    @property
    def scope_ref(self) -> str:
        return (
            f'/subscriptions/{settings.azure_subscription_id}'
            f'/resourceGroups/{settings.azure_resource_group}'
            f'/factories/{settings.azure_data_factory_name}'
        )

    def list_source_states(self):
        rows = self.db.execute(
            select(SourceSyncState).order_by(SourceSyncState.updated_at.desc())
        ).scalars().all()
        return {
            'count': len(rows),
            'items': [
                {
                    'source_name': row.source_name,
                    'source_type': row.source_type,
                    'scope_ref': row.scope_ref,
                    'last_status': row.last_status,
                    'record_count': row.record_count,
                    'last_started_at': row.last_started_at,
                    'last_succeeded_at': row.last_succeeded_at,
                    'last_failed_at': row.last_failed_at,
                    'last_error': row.last_error,
                    'updated_at': row.updated_at,
                }
                for row in rows
            ],
        }

    def list_ingestion_jobs(self, limit: int = 20):
        rows = self.db.execute(
            select(IngestionJob)
            .order_by(IngestionJob.started_at.desc())
            .limit(limit)
        ).scalars().all()
        return {
            'count': len(rows),
            'items': [
                {
                    'id': row.id,
                    'source_name': row.source_name,
                    'source_type': row.source_type,
                    'job_type': row.job_type,
                    'status': row.status,
                    'scope_ref': row.scope_ref,
                    'records_scanned': row.records_scanned,
                    'records_written': row.records_written,
                    'started_at': row.started_at,
                    'finished_at': row.finished_at,
                    'error_message': row.error_message,
                    'details': row.details_json,
                }
                for row in rows
            ],
        }

    def sync_adf_metadata(self):
        sync_state = self._get_or_create_sync_state()
        job = self._create_job(sync_state)
        started_at = datetime.utcnow()
        sync_state.last_status = 'RUNNING'
        sync_state.last_started_at = started_at
        sync_state.last_error = None
        self.db.flush()

        try:
            resources = {
                'pipeline': self.client.list_resources('pipelines'),
                'dataset': self.client.list_resources('datasets'),
                'trigger': self.client.list_resources('triggers'),
            }
            reference_data = self._ensure_reference_data()
            assets = self._sync_assets(resources, reference_data, sync_state)
            dependency_count = self._sync_dependencies(resources, assets, reference_data)
            total_records = sum(len(items) for items in resources.values())

            sync_state.last_status = 'SUCCEEDED'
            sync_state.last_succeeded_at = datetime.utcnow()
            sync_state.record_count = total_records
            job.status = 'SUCCEEDED'
            job.finished_at = datetime.utcnow()
            job.records_scanned = total_records
            job.records_written = total_records
            job.details_json = {
                'factory_name': settings.azure_data_factory_name,
                'dependency_count': dependency_count,
                'resource_counts': {key: len(value) for key, value in resources.items()},
            }
            self.db.commit()
            return {
                'status': 'SUCCEEDED',
                'source_name': sync_state.source_name,
                'records_scanned': total_records,
                'records_written': total_records,
                'dependency_count': dependency_count,
                'resource_counts': {key: len(value) for key, value in resources.items()},
                'started_at': started_at,
                'finished_at': job.finished_at,
            }
        except Exception as exc:
            self.db.rollback()
            sync_state = self._get_or_create_sync_state()
            sync_state.last_status = 'FAILED'
            sync_state.last_failed_at = datetime.utcnow()
            sync_state.last_error = str(exc)
            failed_job = IngestionJob(
                id=job.id,
                source_name=self.source_name,
                source_type='azure_adf',
                job_type='metadata_sync',
                status='FAILED',
                scope_ref=self.scope_ref,
                sync_state_id=sync_state.id,
                records_scanned=job.records_scanned,
                records_written=job.records_written,
                started_at=job.started_at,
                finished_at=datetime.utcnow(),
                error_message=str(exc),
            )
            self.db.merge(sync_state)
            self.db.merge(failed_job)
            self.db.commit()
            raise

    def _get_or_create_sync_state(self) -> SourceSyncState:
        state = self.db.execute(
            select(SourceSyncState).where(SourceSyncState.source_name == self.source_name)
        ).scalar_one_or_none()
        if state:
            return state
        state = SourceSyncState(
            source_name=self.source_name,
            source_type='azure_adf',
            scope_ref=self.scope_ref,
            last_status='IDLE',
        )
        self.db.add(state)
        self.db.flush()
        return state

    def _create_job(self, sync_state: SourceSyncState) -> IngestionJob:
        job = IngestionJob(
            source_name=self.source_name,
            source_type='azure_adf',
            job_type='metadata_sync',
            status='RUNNING',
            scope_ref=self.scope_ref,
            sync_state_id=sync_state.id,
        )
        self.db.add(job)
        self.db.flush()
        return job

    def _ensure_reference_data(self) -> dict:
        team = self.db.execute(
            select(Team).where(func.lower(Team.name) == 'data platform team')
        ).scalar_one_or_none()
        if not team:
            team = Team(
                name='Data Platform Team',
                description='Owns Azure metadata ingestion and governance connectors.',
            )
            self.db.add(team)
            self.db.flush()

        domain = self.db.execute(
            select(BusinessDomain).where(func.lower(BusinessDomain.name) == 'platform')
        ).scalar_one_or_none()
        if not domain:
            domain = BusinessDomain(
                name='Platform',
                description='Shared platform and governance infrastructure.',
                criticality='HIGH',
                owner_team_id=team.id,
            )
            self.db.add(domain)
            self.db.flush()

        system_name = f'ADF/{settings.azure_data_factory_name}'
        system = self.db.execute(
            select(System).where(System.name == system_name)
        ).scalar_one_or_none()
        if not system:
            system = System(
                name=system_name,
                system_type='orchestrator',
                environment=settings.env,
                description='Azure Data Factory metadata source.',
            )
            self.db.add(system)
            self.db.flush()

        asset_types: dict[str, AssetType] = {}
        for name, description in {
            'pipeline': 'Azure Data Factory pipeline',
            'dataset': 'Azure Data Factory dataset',
            'trigger': 'Azure Data Factory trigger',
        }.items():
            row = self.db.execute(
                select(AssetType).where(func.lower(AssetType.name) == name)
            ).scalar_one_or_none()
            if not row:
                row = AssetType(name=name, description=description)
                self.db.add(row)
                self.db.flush()
            asset_types[name] = row

        dependency_types: dict[str, DependencyType] = {}
        for name, description in {
            'calls': 'Invocation relationship between executable assets.',
            'reads_from': 'Consumer reads data from upstream asset.',
            'writes_to': 'Producer writes data to downstream asset.',
            'triggers': 'Trigger activates an executable asset.',
        }.items():
            row = self.db.execute(
                select(DependencyType).where(func.lower(DependencyType.name) == name)
            ).scalar_one_or_none()
            if not row:
                row = DependencyType(name=name, description=description)
                self.db.add(row)
                self.db.flush()
            dependency_types[name] = row

        return {
            'team': team,
            'domain': domain,
            'system': system,
            'asset_types': asset_types,
            'dependency_types': dependency_types,
        }

    def _sync_assets(self, resources: dict[str, list[dict]], refs: dict, sync_state: SourceSyncState):
        assets: dict[tuple[str, str], Asset] = {}
        for entity_type, items in resources.items():
            for item in items:
                name = item.get('name')
                if not name:
                    continue
                asset = self._upsert_asset(entity_type, name, item, refs)
                self._store_snapshot(sync_state, entity_type, name, item)
                self._store_asset_metadata(asset, entity_type, item)
                assets[(entity_type, name)] = asset
        self.db.flush()
        return assets

    def _upsert_asset(self, entity_type: str, name: str, payload: dict, refs: dict) -> Asset:
        qualified_name = f'ADF.{settings.azure_data_factory_name}.{entity_type}.{name}'
        asset = self.db.execute(
            select(Asset).where(Asset.qualified_name == qualified_name)
        ).scalar_one_or_none()

        properties = payload.get('properties') or {}
        description = properties.get('description')
        refresh_frequency = properties.get('runtimeState') if entity_type == 'trigger' else None

        if not asset:
            asset = Asset(
                name=name,
                qualified_name=qualified_name,
                display_name=name,
                description=description,
                refresh_frequency=refresh_frequency,
                is_active=True,
                system_id=refs['system'].id,
                domain_id=refs['domain'].id,
                asset_type_id=refs['asset_types'][entity_type].id,
                owner_team_id=refs['team'].id,
            )
            self.db.add(asset)
            self.db.flush()
        else:
            asset.display_name = name
            asset.description = description
            asset.refresh_frequency = refresh_frequency
            asset.is_active = True
            asset.system_id = refs['system'].id
            asset.domain_id = refs['domain'].id
            asset.asset_type_id = refs['asset_types'][entity_type].id
            asset.owner_team_id = refs['team'].id
        return asset

    def _store_snapshot(self, sync_state: SourceSyncState, entity_type: str, entity_key: str, payload: dict):
        normalized_payload = self._normalized_payload(payload)
        version_ref = payload.get('etag') or payload.get('id')
        self.db.add(
            RawMetadataSnapshot(
                source_name=self.source_name,
                source_type='azure_adf',
                sync_state_id=sync_state.id,
                entity_type=entity_type,
                entity_key=entity_key,
                observed_state='deployed',
                source_version=version_ref,
                snapshot_hash=self._hash_payload(normalized_payload),
                payload_json=normalized_payload,
            )
        )

    def _store_asset_metadata(self, asset: Asset, entity_type: str, payload: dict):
        properties = payload.get('properties') or {}
        normalized_payload = self._normalized_payload(payload)
        version_hash = self._hash_payload(normalized_payload)
        self.db.execute(
            delete(AssetProperty).where(
                AssetProperty.asset_id == asset.id,
                AssetProperty.source_name == self.source_name,
                AssetProperty.observed_state == 'deployed',
            )
        )

        property_rows = {
            'entity_type': {'value': entity_type},
            'resource_id': {'value': payload.get('id')},
            'etag': {'value': payload.get('etag')},
            'folder': {'value': (properties.get('folder') or {}).get('name')},
            'annotations': {'value': properties.get('annotations') or []},
            'adf_type': {'value': properties.get('type')},
        }
        for key, value in property_rows.items():
            if value['value'] is None:
                continue
            self.db.add(
                AssetProperty(
                    asset_id=asset.id,
                    property_name=key,
                    property_value_json=value,
                    source_name=self.source_name,
                    observed_state='deployed',
                )
            )

        existing_version = self.db.execute(
            select(AssetVersion).where(
                AssetVersion.asset_id == asset.id,
                AssetVersion.version_hash == version_hash,
                AssetVersion.source_name == self.source_name,
                AssetVersion.observed_state == 'deployed',
            )
        ).scalar_one_or_none()
        if not existing_version:
            self.db.add(
                AssetVersion(
                    asset_id=asset.id,
                    version_kind='metadata_snapshot',
                    version_ref=payload.get('etag') or payload.get('id'),
                    version_hash=version_hash,
                    source_name=self.source_name,
                    observed_state='deployed',
                )
            )

    def _sync_dependencies(self, resources: dict[str, list[dict]], assets: dict, refs: dict) -> int:
        dependency_types = refs['dependency_types']
        dependency_count = 0

        for pipeline in resources.get('pipeline', []):
            pipeline_name = pipeline.get('name')
            if not pipeline_name:
                continue
            pipeline_asset = assets.get(('pipeline', pipeline_name))
            if not pipeline_asset:
                continue

            activities = ((pipeline.get('properties') or {}).get('activities') or [])
            for activity in activities:
                called_pipeline_name = (
                    ((activity.get('typeProperties') or {}).get('pipeline') or {}).get('referenceName')
                )
                if called_pipeline_name:
                    called_asset = assets.get(('pipeline', called_pipeline_name))
                    if called_asset:
                        dependency_count += self._upsert_dependency(
                            pipeline_asset.id,
                            called_asset.id,
                            dependency_types['calls'].id,
                        )

                for dataset_ref in activity.get('inputs') or []:
                    dataset_name = dataset_ref.get('referenceName')
                    dataset_asset = assets.get(('dataset', dataset_name))
                    if dataset_asset:
                        dependency_count += self._upsert_dependency(
                            dataset_asset.id,
                            pipeline_asset.id,
                            dependency_types['reads_from'].id,
                        )

                for dataset_ref in activity.get('outputs') or []:
                    dataset_name = dataset_ref.get('referenceName')
                    dataset_asset = assets.get(('dataset', dataset_name))
                    if dataset_asset:
                        dependency_count += self._upsert_dependency(
                            pipeline_asset.id,
                            dataset_asset.id,
                            dependency_types['writes_to'].id,
                        )

        for trigger in resources.get('trigger', []):
            trigger_name = trigger.get('name')
            if not trigger_name:
                continue
            trigger_asset = assets.get(('trigger', trigger_name))
            pipelines = ((trigger.get('properties') or {}).get('pipelines') or [])
            for pipeline_ref in pipelines:
                pipeline_name = ((pipeline_ref.get('pipelineReference') or {}).get('referenceName'))
                pipeline_asset = assets.get(('pipeline', pipeline_name))
                if pipeline_asset and trigger_asset:
                    dependency_count += self._upsert_dependency(
                        trigger_asset.id,
                        pipeline_asset.id,
                        dependency_types['triggers'].id,
                    )

        return dependency_count

    def _upsert_dependency(self, upstream_asset_id: int, downstream_asset_id: int, dependency_type_id: int) -> int:
        existing = self.db.execute(
            select(AssetDependency).where(
                AssetDependency.upstream_asset_id == upstream_asset_id,
                AssetDependency.downstream_asset_id == downstream_asset_id,
                AssetDependency.dependency_type_id == dependency_type_id,
            )
        ).scalar_one_or_none()
        if existing:
            existing.is_active = True
            return 0

        self.db.add(
            AssetDependency(
                upstream_asset_id=upstream_asset_id,
                downstream_asset_id=downstream_asset_id,
                dependency_type_id=dependency_type_id,
                is_active=True,
            )
        )
        return 1

    def _normalized_payload(self, payload: dict) -> dict:
        return json.loads(json.dumps(payload, sort_keys=True, default=str))

    def _hash_payload(self, payload: dict) -> str:
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=True).encode('utf-8')
        ).hexdigest()
