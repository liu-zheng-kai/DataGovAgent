-- Canonical metadata governance schema (MySQL 8+)  
-- SQLAlchemy models are the runtime source of truth. 
 
CREATE TABLE IF NOT EXISTS teams (id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(100) NOT NULL UNIQUE, description TEXT NULL, email VARCHAR(200) NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP); 
CREATE TABLE IF NOT EXISTS business_domains (id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(100) NOT NULL UNIQUE, description TEXT NULL, criticality VARCHAR(32) NOT NULL DEFAULT 'MEDIUM', owner_team_id INT NULL, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, CONSTRAINT fk_domain_owner_team FOREIGN KEY (owner_team_id) REFERENCES teams (id)); 
CREATE TABLE IF NOT EXISTS systems (id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(100) NOT NULL UNIQUE, system_type VARCHAR(50) NOT NULL, environment VARCHAR(32) NOT NULL DEFAULT 'prod', description TEXT NULL); 
CREATE TABLE IF NOT EXISTS asset_types (id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(64) NOT NULL UNIQUE, description TEXT NULL); 
CREATE TABLE IF NOT EXISTS dependency_types (id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(64) NOT NULL UNIQUE, description TEXT NULL); 
CREATE TABLE IF NOT EXISTS assets (id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(150) NOT NULL, qualified_name VARCHAR(255) NOT NULL UNIQUE, display_name VARCHAR(255) NULL, description TEXT NULL, refresh_frequency VARCHAR(64) NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE, system_id INT NOT NULL, domain_id INT NOT NULL, asset_type_id INT NOT NULL, owner_team_id INT NULL, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, CONSTRAINT fk_asset_system FOREIGN KEY (system_id) REFERENCES systems (id), CONSTRAINT fk_asset_domain FOREIGN KEY (domain_id) REFERENCES business_domains (id), CONSTRAINT fk_asset_type FOREIGN KEY (asset_type_id) REFERENCES asset_types (id), CONSTRAINT fk_asset_owner_team FOREIGN KEY (owner_team_id) REFERENCES teams (id)); 
CREATE TABLE IF NOT EXISTS asset_dependencies (id INT PRIMARY KEY AUTO_INCREMENT, upstream_asset_id INT NOT NULL, downstream_asset_id INT NOT NULL, dependency_type_id INT NOT NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, CONSTRAINT fk_dep_upstream FOREIGN KEY (upstream_asset_id) REFERENCES assets (id), CONSTRAINT fk_dep_downstream FOREIGN KEY (downstream_asset_id) REFERENCES assets (id), CONSTRAINT fk_dep_type FOREIGN KEY (dependency_type_id) REFERENCES dependency_types (id), CONSTRAINT uq_dependency_path UNIQUE (upstream_asset_id, downstream_asset_id, dependency_type_id)); 
CREATE TABLE IF NOT EXISTS sla_definitions (id INT PRIMARY KEY AUTO_INCREMENT, asset_id INT NOT NULL UNIQUE, expected_interval_minutes INT NOT NULL, warning_after_minutes INT NOT NULL, breach_after_minutes INT NOT NULL, timezone VARCHAR(64) NOT NULL DEFAULT 'UTC', is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, CONSTRAINT fk_sla_asset FOREIGN KEY (asset_id) REFERENCES assets (id));
CREATE TABLE IF NOT EXISTS asset_runtime_status (id INT PRIMARY KEY AUTO_INCREMENT, asset_id INT NOT NULL UNIQUE, status VARCHAR(32) NOT NULL, delay_minutes INT NOT NULL DEFAULT 0, sla_risk_score INT NOT NULL DEFAULT 0, message TEXT NULL, last_run_at DATETIME NULL, last_success_at DATETIME NULL, last_failure_at DATETIME NULL, updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, CONSTRAINT fk_runtime_asset FOREIGN KEY (asset_id) REFERENCES assets (id)); 
CREATE TABLE IF NOT EXISTS runtime_events (id INT PRIMARY KEY AUTO_INCREMENT, asset_id INT NOT NULL, event_type VARCHAR(32) NOT NULL, status VARCHAR(32) NOT NULL, severity VARCHAR(32) NOT NULL, occurred_at DATETIME NOT NULL, run_id VARCHAR(128) NULL, error_code VARCHAR(64) NULL, error_message TEXT NULL, details_json JSON NULL, CONSTRAINT fk_event_asset FOREIGN KEY (asset_id) REFERENCES assets (id)); 
CREATE TABLE IF NOT EXISTS domain_health_snapshots (id INT PRIMARY KEY AUTO_INCREMENT, domain_id INT NOT NULL, status VARCHAR(32) NOT NULL, reason TEXT NULL, observed_at DATETIME NOT NULL, CONSTRAINT fk_health_domain FOREIGN KEY (domain_id) REFERENCES business_domains (id)); 
CREATE TABLE IF NOT EXISTS business_impacts (id INT PRIMARY KEY AUTO_INCREMENT, source_asset_id INT NOT NULL, impacted_asset_id INT NULL, impacted_team_id INT NULL, impacted_domain_id INT NULL, impact_type VARCHAR(64) NOT NULL, impact_level VARCHAR(32) NOT NULL, description TEXT NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE, detected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, CONSTRAINT fk_impact_source_asset FOREIGN KEY (source_asset_id) REFERENCES assets (id), CONSTRAINT fk_impact_target_asset FOREIGN KEY (impacted_asset_id) REFERENCES assets (id), CONSTRAINT fk_impact_team FOREIGN KEY (impacted_team_id) REFERENCES teams (id), CONSTRAINT fk_impact_domain FOREIGN KEY (impacted_domain_id) REFERENCES business_domains (id)); 
CREATE TABLE IF NOT EXISTS daily_summary_reports (id INT PRIMARY KEY AUTO_INCREMENT, report_date DATE NOT NULL UNIQUE, summary_json JSON NOT NULL, generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP);

-- Admin console extension schema (MVP)
CREATE TABLE IF NOT EXISTS tools (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(120) NOT NULL UNIQUE,
  display_name VARCHAR(120) NULL,
  description TEXT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  input_schema_json JSON NULL,
  output_schema_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tool_versions (
  id INT PRIMARY KEY AUTO_INCREMENT,
  tool_id INT NOT NULL,
  version VARCHAR(32) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  changelog TEXT NULL,
  schema_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_tool_version_tool FOREIGN KEY (tool_id) REFERENCES tools (id)
);

CREATE TABLE IF NOT EXISTS prompt_templates (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(160) NOT NULL,
  template_key VARCHAR(120) NOT NULL UNIQUE,
  scene_type VARCHAR(64) NOT NULL,
  description TEXT NULL,
  usage_notes TEXT NULL,
  prompt_content TEXT NOT NULL,
  output_format TEXT NULL,
  example_input TEXT NULL,
  example_output TEXT NULL,
  is_default BOOLEAN NOT NULL DEFAULT FALSE,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  version VARCHAR(32) NOT NULL DEFAULT 'v1',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prompt_template_versions (
  id INT PRIMARY KEY AUTO_INCREMENT,
  prompt_template_id INT NOT NULL,
  version VARCHAR(32) NOT NULL,
  change_log TEXT NULL,
  prompt_content TEXT NOT NULL,
  output_format TEXT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_prompt_template_version_template FOREIGN KEY (prompt_template_id) REFERENCES prompt_templates (id),
  CONSTRAINT uq_prompt_template_version UNIQUE (prompt_template_id, version)
);

CREATE TABLE IF NOT EXISTS tool_prompt_bindings (
  id INT PRIMARY KEY AUTO_INCREMENT,
  tool_id INT NOT NULL,
  scene_type VARCHAR(64) NOT NULL,
  prompt_template_id INT NOT NULL,
  is_default BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_tool_prompt_binding_tool FOREIGN KEY (tool_id) REFERENCES tools (id),
  CONSTRAINT fk_tool_prompt_binding_template FOREIGN KEY (prompt_template_id) REFERENCES prompt_templates (id),
  CONSTRAINT uq_tool_scene_template_binding UNIQUE (tool_id, scene_type, prompt_template_id)
);

CREATE TABLE IF NOT EXISTS data_sources (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(120) NOT NULL UNIQUE,
  source_type VARCHAR(64) NOT NULL,
  connection_uri VARCHAR(500) NULL,
  config_json JSON NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS data_source_tables (
  id INT PRIMARY KEY AUTO_INCREMENT,
  data_source_id INT NOT NULL,
  schema_name VARCHAR(120) NOT NULL,
  table_name VARCHAR(150) NOT NULL,
  description TEXT NULL,
  sample_json JSON NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_data_source_table_source FOREIGN KEY (data_source_id) REFERENCES data_sources (id),
  CONSTRAINT uq_data_source_table_name UNIQUE (data_source_id, schema_name, table_name)
);

CREATE TABLE IF NOT EXISTS channels (
  id INT PRIMARY KEY AUTO_INCREMENT,
  channel_id VARCHAR(120) NOT NULL UNIQUE,
  channel_name VARCHAR(120) NOT NULL,
  channel_type VARCHAR(64) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  config_json JSON NULL,
  default_assistant_id VARCHAR(120) NULL,
  last_seen_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chats (
  id INT PRIMARY KEY AUTO_INCREMENT,
  session_key VARCHAR(64) NOT NULL UNIQUE,
  title VARCHAR(255) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  channel_id INT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  last_message_at DATETIME NULL,
  CONSTRAINT fk_chat_channel FOREIGN KEY (channel_id) REFERENCES channels (id)
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id INT PRIMARY KEY AUTO_INCREMENT,
  chat_session_id INT NOT NULL,
  role VARCHAR(32) NOT NULL,
  content TEXT NOT NULL,
  message_order INT NOT NULL,
  tool_name VARCHAR(120) NULL,
  metadata_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_chat_message_session FOREIGN KEY (chat_session_id) REFERENCES chats (id)
);

CREATE TABLE IF NOT EXISTS tool_calls (
  id INT PRIMARY KEY AUTO_INCREMENT,
  chat_session_id INT NOT NULL,
  chat_message_id INT NULL,
  tool_name VARCHAR(120) NOT NULL,
  args_json JSON NULL,
  result_json JSON NULL,
  error_message TEXT NULL,
  duration_ms INT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_tool_call_chat FOREIGN KEY (chat_session_id) REFERENCES chats (id),
  CONSTRAINT fk_tool_call_message FOREIGN KEY (chat_message_id) REFERENCES chat_messages (id)
);

CREATE TABLE IF NOT EXISTS memories (
  id INT PRIMARY KEY AUTO_INCREMENT,
  memory_type VARCHAR(64) NOT NULL,
  title VARCHAR(255) NOT NULL,
  content TEXT NOT NULL,
  metadata_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scheduled_jobs (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(120) NOT NULL UNIQUE,
  job_type VARCHAR(64) NOT NULL,
  cron_expr VARCHAR(64) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  status VARCHAR(32) NOT NULL DEFAULT 'idle',
  config_json JSON NULL,
  last_run_at DATETIME NULL,
  next_run_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_runs (
  id INT PRIMARY KEY AUTO_INCREMENT,
  job_id INT NOT NULL,
  status VARCHAR(32) NOT NULL,
  started_at DATETIME NOT NULL,
  finished_at DATETIME NULL,
  duration_ms INT NULL,
  triggered_by VARCHAR(64) NULL,
  error_message TEXT NULL,
  result_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_job_run_job FOREIGN KEY (job_id) REFERENCES scheduled_jobs (id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id INT PRIMARY KEY AUTO_INCREMENT,
  actor VARCHAR(120) NULL,
  action VARCHAR(120) NOT NULL,
  entity_type VARCHAR(64) NOT NULL,
  entity_id VARCHAR(64) NULL,
  details_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
