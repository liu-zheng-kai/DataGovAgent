TOOL_DEFINITIONS = [ 
    { 
        'type': 'function', 
        'function': { 
            'name': 'get_asset', 
            'description': 'Get basic metadata for an asset.', 
            'parameters': { 
                'type': 'object', 
                'properties': {'asset_name': {'type': 'string'}}, 
                'required': ['asset_name'], 
            }, 
        }, 
    }, 
    { 
        'type': 'function', 
        'function': { 
            'name': 'get_asset_detail', 
            'description': 'Get detailed metadata, SLA, and runtime status for an asset.', 
            'parameters': { 
                'type': 'object', 
                'properties': {'asset_name': {'type': 'string'}}, 
                'required': ['asset_name'], 
            }, 
        }, 
    }, 
    { 
        'type': 'function', 
        'function': { 
            'name': 'get_downstream', 
            'description': 'Get downstream lineage graph for an asset.', 
            'parameters': { 
                'type': 'object', 
                'properties': {'asset_name': {'type': 'string'}}, 
                'required': ['asset_name'], 
            }, 
        }, 
    }, 
    { 
        'type': 'function', 
        'function': { 
            'name': 'get_upstream', 
            'description': 'Get upstream lineage graph for an asset.', 
            'parameters': { 
                'type': 'object', 
                'properties': {'asset_name': {'type': 'string'}}, 
                'required': ['asset_name'], 
            }, 
        }, 
    }, 
    { 
        'type': 'function', 
        'function': { 
            'name': 'get_failed_runs', 
            'description': 'Get failed jobs for today, optionally filtered by domain.', 
            'parameters': { 
                'type': 'object', 
                'properties': {'domain': {'type': 'string'}}, 
            }, 
        }, 
    }, 
    { 
        'type': 'function', 
        'function': { 
            'name': 'get_domain_health', 
            'description': 'Get latest health status for a business domain.', 
            'parameters': { 
                'type': 'object', 
                'properties': {'domain_name': {'type': 'string'}}, 
                'required': ['domain_name'], 
            }, 
        }, 
    }, 
    { 
        'type': 'function', 
        'function': { 
            'name': 'get_business_impact', 
            'description': 'Get business impact relationships for an asset.', 
            'parameters': { 
                'type': 'object', 
                'properties': {'asset_name': {'type': 'string'}}, 
                'required': ['asset_name'], 
            }, 
        }, 
    }, 
    { 
        'type': 'function', 
        'function': { 
            'name': 'get_impacted_apis', 
            'description': 'Get impacted APIs for an upstream failing asset.', 
            'parameters': { 
                'type': 'object', 
                'properties': {'asset_name': {'type': 'string'}}, 
                'required': ['asset_name'], 
            }, 
        }, 
    }, 
    { 
        'type': 'function', 
        'function': { 
            'name': 'get_sla_risk_assets', 
            'description': 'Get assets that are close to or in SLA breach risk.', 
            'parameters': {'type': 'object', 'properties': {}}, 
        }, 
    }, 
    { 
        'type': 'function', 
        'function': { 
            'name': 'generate_daily_summary', 
            'description': 'Generate and persist daily summary report for a date.', 
            'parameters': { 
                'type': 'object', 
                'properties': {'report_date': {'type': 'string', 'description': 'YYYY-MM-DD'}}, 
            }, 
        }, 
    }, 
]
