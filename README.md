# DataGovAgent

English | [中文](./README.zh.md) | [日本語](./README.ja.md)

DataGovAgent is a local metadata-driven governance and metadata tracking prototype built with FastAPI, SQLAlchemy, MySQL, SQLite fallback, and OpenAI-compatible tool calling.

## Overview

DataGovAgent demonstrates an extensible canonical metadata architecture where:

- Data systems write metadata into a standard schema.
- Services and tools query only that schema.
- The LLM agent answers governance questions through tools instead of direct database access.
- Prompt strategy, admin controls, runtime tracing, and operational workflows can evolve without changing the core agent pattern.

## Architecture

![Architecture Diagram](./docs/images/architecture_flow.png)

### Screenshots

#### 1. Admin Console Home
![Admin Console Home](./docs/images/admin_overview.png)

#### 2. Chat Experience with Tool Results
![Chat Experience](./docs/images/chat_effect.png)

#### 3. Prompt Template Management
![Prompt Template Management](./docs/images/prompt_template_effect.png)

### Key Modules

#### 1. Agent Orchestration
- Component: `MetadataAgent` in `app/agent/llm_agent.py`
- Responsibility: orchestrates one Q&A flow without querying the database directly
- Main work: selects prompts, exposes tool definitions, executes requested tools, and assembles grounded answers

#### 2. Tools Layer
- Components: `TOOL_DEFINITIONS` and `MetadataToolRegistry`
- Files: `app/agent/tooling.py`, `app/tools/registry.py`
- Main work: standardizes callable functions and routes model tool calls into the service layer

#### 3. Metadata Store
- Components: database plus canonical ORM models under `app/models/*`
- Responsibility: single source of truth for assets, lineage, runtime state, SLA, impacts, reports, prompts, audit logs, and jobs

#### 4. Prompt Management
- Components: `PromptTemplateRecord`, `ToolPromptBindingRecord`, and admin APIs under `/api/admin/prompt-templates*`
- Main work: decouples prompts from code and supports scene-based defaults, versioning, preview, tool binding, and online tuning

## Canonical Metadata Model

Core entities are intentionally platform-neutral:

- `teams`: ownership and responsibility mapping
- `business_domains`: governance boundaries and domain health context
- `systems`: source and target technical systems such as `Oracle`, `Bronze`, `Silver`, `Gold`, `Cosmos`, and `API`
- `asset_types`: generalized asset classification such as `table`, `dataset`, and `api_endpoint`
- `assets`: canonical metadata records for data products and interfaces
- `asset_dependencies`: lineage edges between assets
- `sla_definitions`: expected interval and warning or breach thresholds
- `asset_runtime_status`: latest operational state per asset
- `runtime_events`: run and failure history
- `domain_health_snapshots`: latest domain health assessment and reason
- `business_impacts`: normalized impact links from technical failures to assets, teams, and domains
- `daily_summary_reports`: persisted generated report snapshots

References:

- SQLAlchemy models: `app/models/`
- Optional SQL DDL: `app/seed/schema.sql`

## Seeded Scenario

Primary lineage chain:

`Oracle.customer_master -> Bronze.customer_master -> Silver.customer_standardized -> Gold.customer_profile -> Cosmos.customer_profile -> API.customer_profile`

Additional branch:

`Bronze.customer_contact -> Silver.customer_contact -> Gold.customer_profile`

Injected incident:

- `Silver.customer_contact` fails today
- `Gold.customer_profile`, `Cosmos.customer_profile`, and `API.customer_profile` become degraded or stale
- `Sales Team` and `CRM Team` are impacted
- `Customer` domain health becomes `RED`

## Project Structure

```text
metadata_governance_poc/
  app/
    agent/
      cli.py
      llm_agent.py
      tooling.py
    api/
      admin.py
      assets.py
      auth.py
      chat.py
      domains.py
      impacts.py
      reports.py
      runtime.py
      sla.py
    core/
      config.py
      serializer.py
    models/
      admin.py
      impact.py
      metadata.py
      reference.py
      report.py
      runtime.py
    schemas/
      admin.py
      api.py
    services/
      admin_service.py
      asset_service.py
      impact_service.py
      report_service.py
      runtime_service.py
    seed/
      schema.sql
      seed_data.py
    static/
      admin/
    db.py
    main.py
  docs/
  scripts/
  requirements.txt
  README.md
  README.zh.md
  README.ja.md
```

## Quick Start

### 1. Prerequisites

- Python `3.11+`
- MySQL `8+`
- Optional OpenAI-compatible API key for `/chat`

### 2. Create and activate a virtual environment

Windows `cmd`:

```bash
cd D:\codexAIcode\metadata_governance_poc
python -m venv .venv
.venv\Scripts\activate
```

Linux or macOS:

```bash
cd /path/to/metadata_governance_poc
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
copy .env.example .env
```

Edit `.env`:

```env
app_name=DataGovAgent
env=local
app_public_base_url=http://127.0.0.1:8000
database_url=mysql+pymysql://root:root@localhost:3306/metadata_governance
database_fallback_url=sqlite:///./metadata_governance.db
database_fallback_on_connect_error=true
llm_provider=openai
openai_auth_mode=api_key
openai_api_key=your_openai_key
openai_oauth_token=
openai_oauth_token_file=~/.codex/auth.json
openai_model=gpt-4o-mini
openai_base_url=https://api.openai.com/v1
gemini_api_key=
gemini_model=gemini-3-flash-preview
gemini_base_url=https://generativelanguage.googleapis.com/v1beta/openai/
agent_max_iterations=6
oauth_authorize_url=
oauth_token_url=
oauth_client_id=
oauth_client_secret=
oauth_redirect_uri=http://127.0.0.1:8000/auth/callback
oauth_scope=openid profile email
oauth_audience=
oauth_state_ttl_seconds=300
oauth_session_ttl_seconds=28800
oauth_session_cookie_name=mg_oauth_session
oauth_cookie_secure=false
oauth_use_pkce=true
oauth_http_timeout_seconds=20
oauth_success_redirect_url=
```

### 5. Create MySQL database

```sql
CREATE DATABASE IF NOT EXISTS metadata_governance
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

### 6. Create tables and seed mock data

```bash
python -m app.seed.seed_data
```

### 7. Start API server

```bash
uvicorn app.main:app --reload --port 8000
```

### 8. Open the app

- Swagger UI: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`
- Admin console: `http://127.0.0.1:8000/admin`

## REST Examples

```bash
curl http://127.0.0.1:8000/assets/customer_profile
curl http://127.0.0.1:8000/assets/customer_profile/downstream
curl "http://127.0.0.1:8000/runtime/failed?domain=Customer"
curl http://127.0.0.1:8000/domains/Customer/health
curl http://127.0.0.1:8000/impacts/customer_contact
curl http://127.0.0.1:8000/sla/risks
curl "http://127.0.0.1:8000/reports/daily?report_date=2026-04-04"
```

### Chat Endpoint Example

```bash
curl -X POST http://127.0.0.1:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"question\": \"Which teams are impacted by silver.customer_contact failure?\"}"
```

### OAuth Token Mode Example

```bash
curl -X POST http://127.0.0.1:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"question\": \"Which teams are impacted by silver.customer_contact failure?\", \"oauth_access_token\": \"<your_oauth_token>\"}"
```

Note: the official OpenAI API typically uses API key authentication. OAuth token mode is mainly for OpenAI-compatible gateways that issue bearer tokens.

## API Endpoints

- `POST /chat`
- `GET /auth/login`
- `GET /auth/callback`
- `GET /auth/me`
- `GET /auth/done`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /assets/{name}`
- `GET /assets/{name}/downstream`
- `GET /assets/{name}/upstream`
- `GET /runtime/failed`
- `GET /domains/{name}/health`
- `GET /impacts/{asset_name}`
- `GET /impacts/{asset_name}/apis`
- `GET /sla/risks`
- `GET /reports/daily`
- `GET /api/admin/dashboard`
- `GET /api/admin/tools`
- `GET /api/admin/tool-versions`
- `GET /api/admin/data-sources`
- `GET /api/admin/chats`
- `GET /api/admin/jobs`
- `GET /api/admin/channels`
- `GET /api/admin/logs/trace`
- `GET /api/admin/assets`
- `GET /api/admin/lineage`
- `GET /api/admin/prompt-templates`

## Tool Functions

Implemented in `app/tools/registry.py`:

- `get_asset(asset_name)`
- `get_asset_detail(asset_name)`
- `get_downstream(asset_name)`
- `get_upstream(asset_name)`
- `get_failed_runs(domain=None)`
- `get_domain_health(domain_name)`
- `get_business_impact(asset_name)`
- `get_impacted_apis(asset_name)`
- `get_sla_risk_assets()`
- `generate_daily_summary(report_date)`

## Agent Flow

1. A user asks a natural-language governance question.
2. The agent sends the question and tool schemas to the model.
3. The model selects one or more tools.
4. The agent executes the tools through the service layer.
5. Tool results are sent back to the model.
6. The model returns a grounded final answer.

The LLM never queries MySQL directly. Database access happens only through tools and services.

## Troubleshooting

- `OPENAI_API_KEY is empty`
  Set `openai_api_key` in `.env` before using `/chat` or the CLI agent.
- `GEMINI_API_KEY is empty`
  Set `llm_provider=gemini` and configure `gemini_api_key` in `.env`.
- `OpenAI OAuth token is empty`
  Set `openai_auth_mode=oauth_token`, provide `openai_oauth_token`, or complete the `/auth/login` flow.
- MySQL connection error
  Verify `database_url`, credentials, host, and port. Local fallback to SQLite is supported.
- No seeded data
  Re-run `python -m app.seed.seed_data`.
- Endpoint returns not found
  Try both short and qualified names such as `customer_profile` and `API.customer_profile`.

## VS Code Local Development

This repo includes:

- `.vscode/tasks.json` for setup, MySQL startup, seeding, and API run
- `.vscode/launch.json` for FastAPI and seed script debugging
- `scripts/setup_dev_env.cmd` for one-command environment bootstrap
- `docker-compose.yml` for local MySQL 8

### Recommended flow

1. Run `Setup: Python venv + deps`
2. Run `Infra: Start MySQL (Docker)`
3. Run `DB: Seed mock metadata`
4. Run `API: Run FastAPI (reload)` or press `F5`

## Additional Language Versions

- Chinese: [README.zh.md](./README.zh.md)
- Japanese: [README.ja.md](./README.ja.md)

## License

This project is licensed under [`AGPL-3.0-or-later`](./LICENSE).

- If you modify and distribute this project, you must also open source your modified version under the same license.
- If you run a modified version for users over a network, you must provide the corresponding source code of that modified version.
- Repository policy: if you reuse or modify this project for external use, you should publish the modified source in a public Git repository, preferably on GitHub. See [OPEN_SOURCE_POLICY.md](./OPEN_SOURCE_POLICY.md).
