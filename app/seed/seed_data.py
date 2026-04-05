from datetime import datetime, timedelta, timezone 
 
from sqlalchemy import delete 
 
import app.models  # noqa: F401 
from app.db import Base, SessionLocal, engine 
from app.models.impact import BusinessImpact 
from app.models.metadata import Asset, AssetDependency, SlaDefinition 
from app.models.reference import AssetType, BusinessDomain, DependencyType, System, Team 
from app.models.report import DailySummaryReport 
from app.models.runtime import AssetRuntimeStatus, DomainHealthSnapshot, RuntimeEvent 
 
 
def reset_data(db): 
    db.execute(delete(BusinessImpact)) 
    db.execute(delete(RuntimeEvent)) 
    db.execute(delete(AssetRuntimeStatus)) 
    db.execute(delete(DomainHealthSnapshot)) 
    db.execute(delete(SlaDefinition)) 
    db.execute(delete(AssetDependency)) 
    db.execute(delete(DailySummaryReport)) 
    db.execute(delete(Asset)) 
    db.execute(delete(DependencyType)) 
    db.execute(delete(AssetType)) 
    db.execute(delete(System)) 
    db.execute(delete(BusinessDomain)) 
    db.execute(delete(Team)) 
    db.commit() 
 
 
def add_reference_data(db): 
    teams = { 
        'data_platform': Team(name='Data Platform Team', description='Owns metadata and data pipelines.'), 
        'customer_analytics': Team(name='Customer Analytics Team', description='Owns customer analytics domain.'), 
        'sales': Team(name='Sales Team', description='Uses customer profile APIs for sales workflows.'), 
        'crm': Team(name='CRM Team', description='Uses customer profile APIs for CRM processes.'), 
        'api': Team(name='API Team', description='Owns API publication assets.'), 
    } 
    db.add_all(list(teams.values())) 
    db.flush() 
 
    domains = { 
        'customer': BusinessDomain( 
            name='Customer', 
            description='Customer lifecycle and profile domain.', 
            criticality='CRITICAL', 
            owner_team_id=teams['customer_analytics'].id, 
        ) 
    } 
    db.add_all(list(domains.values())) 
    db.flush() 
 
    systems = { 
        'oracle': System(name='Oracle', system_type='database', environment='prod'), 
        'bronze': System(name='Bronze', system_type='lakehouse', environment='prod'), 
        'silver': System(name='Silver', system_type='lakehouse', environment='prod'), 
        'gold': System(name='Gold', system_type='lakehouse', environment='prod'), 
        'cosmos': System(name='Cosmos', system_type='nosql', environment='prod'), 
        'api': System(name='API', system_type='api_gateway', environment='prod'), 
    } 
    db.add_all(list(systems.values())) 
    db.flush() 
 
    asset_types = { 
        'table': AssetType(name='table', description='Structured table-like asset.'), 
        'dataset': AssetType(name='dataset', description='Curated dataset asset.'), 
        'api_endpoint': AssetType(name='api_endpoint', description='Published API data product.'), 
    } 
    db.add_all(list(asset_types.values())) 
    db.flush() 
 
    dependency_types = { 
        'etl': DependencyType(name='ETL', description='Standard ETL dependency.'), 
        'replication': DependencyType(name='REPLICATION', description='Replication dependency.'), 
        'api_publication': DependencyType(name='API_PUBLICATION', description='API publication dependency.'), 
    } 
    db.add_all(list(dependency_types.values())) 
    db.flush() 
 
    return teams, domains, systems, asset_types, dependency_types
 
 
def add_assets(db, teams, domains, systems, asset_types): 
    customer_domain_id = domains['customer'].id 
    assets = { 
        'oracle.customer_master': Asset( 
            name='customer_master', qualified_name='Oracle.customer_master', 
            description='Customer master from Oracle.', refresh_frequency='hourly', 
            system_id=systems['oracle'].id, domain_id=customer_domain_id, 
            asset_type_id=asset_types['table'].id, owner_team_id=teams['data_platform'].id, 
        ), 
        'bronze.customer_master': Asset( 
            name='customer_master', qualified_name='Bronze.customer_master', 
            description='Bronze raw customer data.', refresh_frequency='hourly', 
            system_id=systems['bronze'].id, domain_id=customer_domain_id, 
            asset_type_id=asset_types['table'].id, owner_team_id=teams['data_platform'].id, 
        ), 
        'bronze.customer_contact': Asset( 
            name='customer_contact', qualified_name='Bronze.customer_contact', 
            description='Bronze raw customer contact data.', refresh_frequency='hourly', 
            system_id=systems['bronze'].id, domain_id=customer_domain_id, 
            asset_type_id=asset_types['table'].id, owner_team_id=teams['data_platform'].id, 
        ), 
        'silver.customer_standardized': Asset( 
            name='customer_standardized', qualified_name='Silver.customer_standardized', 
            description='Conformed customer attributes.', refresh_frequency='hourly', 
            system_id=systems['silver'].id, domain_id=customer_domain_id, 
            asset_type_id=asset_types['dataset'].id, owner_team_id=teams['data_platform'].id, 
        ), 
        'silver.customer_contact': Asset( 
            name='customer_contact', qualified_name='Silver.customer_contact', 
            description='Validated customer contact dataset.', refresh_frequency='hourly', 
            system_id=systems['silver'].id, domain_id=customer_domain_id, 
            asset_type_id=asset_types['dataset'].id, owner_team_id=teams['data_platform'].id, 
        ), 
        'gold.customer_profile': Asset( 
            name='customer_profile', qualified_name='Gold.customer_profile', 
            description='Golden customer profile.', refresh_frequency='hourly', 
            system_id=systems['gold'].id, domain_id=customer_domain_id, 
            asset_type_id=asset_types['dataset'].id, owner_team_id=teams['customer_analytics'].id, 
        ), 
        'cosmos.customer_profile': Asset( 
            name='customer_profile', qualified_name='Cosmos.customer_profile', 
            description='Customer profile in operational serving store.', refresh_frequency='hourly', 
            system_id=systems['cosmos'].id, domain_id=customer_domain_id, 
            asset_type_id=asset_types['dataset'].id, owner_team_id=teams['data_platform'].id, 
        ), 
        'api.customer_profile': Asset( 
            name='customer_profile', qualified_name='API.customer_profile', 
            description='Public API customer profile endpoint.', refresh_frequency='15m', 
            system_id=systems['api'].id, domain_id=customer_domain_id, 
            asset_type_id=asset_types['api_endpoint'].id, owner_team_id=teams['api'].id, 
        ), 
    } 
    db.add_all(list(assets.values())) 
    db.flush() 
    return assets 
 
 
def add_dependencies(db, assets, dependency_types): 
    etl = dependency_types['etl'].id 
    replication = dependency_types['replication'].id 
    api_pub = dependency_types['api_publication'].id 
 
    links = [ 
        ('oracle.customer_master', 'bronze.customer_master', etl), 
        ('bronze.customer_master', 'silver.customer_standardized', etl), 
        ('bronze.customer_contact', 'silver.customer_contact', etl), 
        ('silver.customer_standardized', 'gold.customer_profile', etl), 
        ('silver.customer_contact', 'gold.customer_profile', etl), 
        ('gold.customer_profile', 'cosmos.customer_profile', replication), 
        ('cosmos.customer_profile', 'api.customer_profile', api_pub), 
    ] 
    rows = [] 
    for upstream_key, downstream_key, dep_type_id in links: 
        rows.append( 
            AssetDependency( 
                upstream_asset_id=assets[upstream_key].id, 
                downstream_asset_id=assets[downstream_key].id, 
                dependency_type_id=dep_type_id, 
                is_active=True, 
            ) 
        ) 
    db.add_all(rows)
 
 
def add_slas(db, assets): 
    rows = [] 
    for key, asset in assets.items(): 
        warning = 75 if key == 'api.customer_profile' else 90 
        breach = 120 if key == 'api.customer_profile' else 150 
        rows.append( 
            SlaDefinition( 
                asset_id=asset.id, 
                expected_interval_minutes=60, 
                warning_after_minutes=warning, 
                breach_after_minutes=breach, 
                timezone='UTC', 
            ) 
        ) 
    db.add_all(rows) 
 
 
def add_runtime(db, assets, domains): 
    now = datetime.now(timezone.utc) 
 
    statuses = [ 
        AssetRuntimeStatus(asset_id=assets['oracle.customer_master'].id, status='HEALTHY', delay_minutes=5, sla_risk_score=10, last_run_at=now - timedelta(minutes=5), last_success_at=now - timedelta(minutes=5)), 
        AssetRuntimeStatus(asset_id=assets['bronze.customer_master'].id, status='HEALTHY', delay_minutes=8, sla_risk_score=15, last_run_at=now - timedelta(minutes=8), last_success_at=now - timedelta(minutes=8)), 
        AssetRuntimeStatus(asset_id=assets['bronze.customer_contact'].id, status='HEALTHY', delay_minutes=12, sla_risk_score=20, last_run_at=now - timedelta(minutes=12), last_success_at=now - timedelta(minutes=12)), 
        AssetRuntimeStatus(asset_id=assets['silver.customer_standardized'].id, status='HEALTHY', delay_minutes=20, sla_risk_score=25, last_run_at=now - timedelta(minutes=20), last_success_at=now - timedelta(minutes=20)), 
        AssetRuntimeStatus(asset_id=assets['silver.customer_contact'].id, status='FAILED', delay_minutes=190, sla_risk_score=98, last_run_at=now - timedelta(minutes=190), last_success_at=now - timedelta(hours=5), last_failure_at=now - timedelta(minutes=30), message='Schema drift and null explosion in contact pipeline'), 
        AssetRuntimeStatus(asset_id=assets['gold.customer_profile'].id, status='DEGRADED', delay_minutes=140, sla_risk_score=86, last_run_at=now - timedelta(minutes=140), last_success_at=now - timedelta(hours=3), message='Waiting for Silver.customer_contact'), 
        AssetRuntimeStatus(asset_id=assets['cosmos.customer_profile'].id, status='DEGRADED', delay_minutes=110, sla_risk_score=78, last_run_at=now - timedelta(minutes=110), last_success_at=now - timedelta(hours=3), message='Upstream gold profile delayed'), 
        AssetRuntimeStatus(asset_id=assets['api.customer_profile'].id, status='DEGRADED', delay_minutes=85, sla_risk_score=72, last_run_at=now - timedelta(minutes=85), last_success_at=now - timedelta(hours=2), message='Serving stale profile cache'), 
    ] 
    db.add_all(statuses) 
 
    events = [ 
        RuntimeEvent(asset_id=assets['silver.customer_contact'].id, event_type='PIPELINE_RUN', status='FAILED', severity='CRITICAL', occurred_at=now - timedelta(minutes=30), run_id='run_silver_contact_001', error_code='SCHEMA_DRIFT', error_message='Column phone_number failed validation', details_json={'null_rate': 0.78}), 
        RuntimeEvent(asset_id=assets['gold.customer_profile'].id, event_type='PIPELINE_RUN', status='FAILED', severity='HIGH', occurred_at=now - timedelta(minutes=15), run_id='run_gold_profile_001', error_code='UPSTREAM_MISSING', error_message='Dependency Silver.customer_contact missing window', details_json={'missing_dependency': 'Silver.customer_contact'}), 
    ] 
    db.add_all(events) 
 
    db.add(DomainHealthSnapshot(domain_id=domains['customer'].id, status='RED', observed_at=now - timedelta(minutes=10), reason='Silver.customer_contact failed; downstream profile assets stale.')) 
 
 
def add_impacts(db, assets, teams, domains): 
    rows = [ 
        BusinessImpact(source_asset_id=assets['silver.customer_contact'].id, impacted_asset_id=assets['gold.customer_profile'].id, impact_type='DATA_DELAY', impact_level='HIGH', description='Gold profile cannot complete due to missing contact feed'), 
        BusinessImpact(source_asset_id=assets['silver.customer_contact'].id, impacted_asset_id=assets['cosmos.customer_profile'].id, impact_type='DATA_STALE', impact_level='HIGH', description='Cosmos serving layer receives stale profile records'), 
        BusinessImpact(source_asset_id=assets['silver.customer_contact'].id, impacted_asset_id=assets['api.customer_profile'].id, impact_type='API_DEGRADATION', impact_level='CRITICAL', description='API returns stale customer contact attributes'), 
        BusinessImpact(source_asset_id=assets['silver.customer_contact'].id, impacted_team_id=teams['sales'].id, impact_type='BUSINESS_OPERATION', impact_level='HIGH', description='Sales workflows lose fresh contact enrichment'), 
        BusinessImpact(source_asset_id=assets['silver.customer_contact'].id, impacted_team_id=teams['crm'].id, impact_type='BUSINESS_OPERATION', impact_level='MEDIUM', description='CRM campaign audience quality is degraded'), 
        BusinessImpact(source_asset_id=assets['silver.customer_contact'].id, impacted_domain_id=domains['customer'].id, impact_type='DOMAIN_HEALTH', impact_level='CRITICAL', description='Customer domain health dropped to RED'), 
    ] 
    db.add_all(rows) 
 
 
def main(): 
    Base.metadata.create_all(bind=engine) 
    db = SessionLocal() 
    try: 
        reset_data(db) 
        teams, domains, systems, asset_types, dependency_types = add_reference_data(db) 
        assets = add_assets(db, teams, domains, systems, asset_types) 
        add_dependencies(db, assets, dependency_types) 
        add_slas(db, assets) 
        add_runtime(db, assets, domains) 
        add_impacts(db, assets, teams, domains) 
        db.commit() 
        print('Seed completed successfully.') 
    finally: 
        db.close() 
 
 
if __name__ == '__main__': 
    main()
