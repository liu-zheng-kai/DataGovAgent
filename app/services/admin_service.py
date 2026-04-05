from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.agent.tooling import TOOL_DEFINITIONS
from app.core.serializer import to_jsonable
from app.models.admin import (
    AuditLogRecord,
    ChannelRecord,
    ChatMessageRecord,
    ChatSessionRecord,
    DataSourceRecord,
    DataSourceTableRecord,
    JobRunRecord,
    MemoryRecord,
    PromptTemplateRecord,
    PromptTemplateVersionRecord,
    ScheduledJobRecord,
    ToolCallRecord,
    ToolDefinitionRecord,
    ToolPromptBindingRecord,
    ToolVersionRecord,
)
from app.models.metadata import Asset
from app.models.reference import System
from app.models.runtime import RuntimeEvent
from app.services.report_service import ReportService
from app.services.runtime_service import RuntimeService
from app.services.asset_service import AssetService


SCENE_LINEAGE = 'lineage_query'
SCENE_SLA = 'sla_query'
SCENE_DAILY = 'daily_report'
SCENE_FAILED = 'failed_jobs_query'
SCENE_RISK = 'risk_analysis'

SUPPORTED_SCENES = [
    SCENE_LINEAGE,
    SCENE_SLA,
    SCENE_DAILY,
    SCENE_FAILED,
    SCENE_RISK,
]


def infer_scene_type(question: str | None) -> str:
    text = (question or '').lower()
    # Daily report should win over SLA/failed/risk when query asks for a report.
    if any(
        k in text
        for k in [
            'daily report',
            'daily summary',
            'today report',
            'operations report',
            '日报',
            '每日',
            '日常报告',
            '生产日报',
            '运营日报',
            '汇报',
            '汇总报告',
        ]
    ):
        return SCENE_DAILY
    if any(
        k in text
        for k in [
            'failed run',
            'failed job',
            'error code',
            'failure',
            '失败任务',
            '失败作业',
            '报错',
            '故障',
        ]
    ):
        return SCENE_FAILED
    if any(
        k in text
        for k in [
            'lineage',
            'upstream',
            'downstream',
            'dependency',
            '血缘',
            '上游',
            '下游',
            '依赖链',
        ]
    ):
        return SCENE_LINEAGE
    if any(
        k in text
        for k in [
            'sla',
            'breach',
            'delay',
            'risk score',
            '时效',
            '超时',
            '延迟',
        ]
    ):
        return SCENE_SLA
    if any(
        k in text
        for k in [
            'risk',
            'impact',
            'schema drift',
            'stale',
            '风险',
            '影响面',
            '漂移',
            '过期数据',
        ]
    ):
        return SCENE_RISK
    return SCENE_LINEAGE


def _default_prompt_templates() -> list[dict[str, Any]]:
    return [
        {
            'name': 'Lineage Quick Query',
            'template_key': 'lineage.quick.v1',
            'scene_type': SCENE_LINEAGE,
            'description': 'Fast production lineage lookup with direct dependency and impact summary.',
            'usage_notes': (
                'Use for on-call responders who need quick, verified lineage and immediate risk awareness.'
            ),
            'prompt_content': (
                'You are an enterprise metadata governance specialist focused on production lineage triage.\n'
                'Always call tools first and only report facts that can be verified from tool results.\n'
                'Prioritize direct upstream/downstream dependencies, execution-critical links, and impacted business-facing assets.\n'
                'If data is missing, explicitly mark as "Unknown" and propose the next best validation step.\n'
                'Do not provide generic explanations; provide operationally useful output for incident handling.\n'
                'For pure lineage lookup questions, do NOT output remediation or recommended actions.\n'
                'Only output action steps when user explicitly asks about risk, impact, or remediation.'
            ),
            'output_format': (
                '# Lineage Quick Response - {asset_name}\n'
                '## 1. Snapshot\n'
                '- Asset: {asset_name}\n'
                '- Direction: {direction}\n'
                '- Lineage Confidence: High/Medium/Low\n'
                '- Immediate Risk: None/Low/Medium/High/Critical\n'
                '## 2. Direct Dependencies\n'
                '| Direction | Asset | Dependency Type | Runtime Criticality |\n'
                '| --- | --- | --- | --- |\n'
                '## 3. Immediate Impact Highlights\n'
                '- Impacted APIs:\n'
                '- Impacted Teams:\n'
                '- Impacted Domains:\n'
                '## 4. Operational Note (Optional)\n'
                '- Leave this section empty unless user asks risk/impact/remediation.'
            ),
            'example_input': 'Show downstream lineage for Silver.customer_contact',
            'example_output': (
                'A concise markdown report with dependency table, impact highlights, and short action list.'
            ),
            'is_default': True,
            'status': 'active',
            'version': 'v2',
        },
        {
            'name': 'Lineage Analysis Narrative',
            'template_key': 'lineage.analysis.v1',
            'scene_type': SCENE_LINEAGE,
            'description': 'Deep lineage interpretation with stage-by-stage explanation and bottleneck analysis.',
            'usage_notes': (
                'Use when analysts or platform engineers need a traceable narrative from source to serving/API layer.'
            ),
            'prompt_content': (
                'You are a senior data lineage analyst for enterprise data platforms.\n'
                'Build a stage-by-stage explanation covering ingestion, bronze/silver/gold, serving stores, and APIs.\n'
                'For each stage, explain transformation role, dependency reason, and operational fragility.\n'
                'Highlight points where delay, schema drift, or quality degradation can propagate.\n'
                'If uncertainty exists, label it explicitly and include a validation query/tool step.'
            ),
            'output_format': (
                '# Lineage Analysis Report - {asset_name}\n'
                '## 1. End-to-End Chain Summary\n'
                '- Total stages:\n'
                '- Critical handoff points:\n'
                '## 2. Stage Breakdown\n'
                '| Stage | Assets | Transformation Role | Failure Sensitivity |\n'
                '| --- | --- | --- | --- |\n'
                '## 3. Dependency Interpretation\n'
                '### 3.1 Upstream to Core Processing\n'
                '### 3.2 Core Processing to Serving Layer\n'
                '### 3.3 Serving Layer to API/Consumption\n'
                '## 4. Bottlenecks & Fragile Links\n'
                '| Link | Observed Risk | Evidence | Suggested Hardening |\n'
                '| --- | --- | --- | --- |\n'
                '## 5. Data Needed for Higher Confidence\n'
                '1. ...\n'
                '2. ...'
            ),
            'example_input': 'Explain lineage path from Oracle.customer_master to API.customer_profile',
            'example_output': (
                'Detailed markdown with stage table, dependency interpretation, and bottleneck recommendations.'
            ),
            'is_default': False,
            'status': 'active',
            'version': 'v2',
        },
        {
            'name': 'Lineage Risk & Blast Radius',
            'template_key': 'lineage.risk.v1',
            'scene_type': SCENE_LINEAGE,
            'description': 'Incident-style blast radius report with prioritized business and technical impact.',
            'usage_notes': (
                'Use in incident bridge calls where rapid prioritization and stakeholder communication are required.'
            ),
            'prompt_content': (
                'You are an incident command support specialist for data platform outages.\n'
                'Map the blast radius from failing asset to downstream data products, APIs, domains, and teams.\n'
                'Prioritize CRITICAL and HIGH impact first, with explicit operational and business consequences.\n'
                'Each major issue must include: symptom, likely cause, impact, and recommended action.\n'
                'Use short, decisive language suitable for production bridge updates.'
            ),
            'output_format': (
                '# Blast Radius Assessment - {asset_name}\n'
                '## 1. Incident Severity Headline\n'
                '- Overall Severity: CRITICAL/HIGH/MEDIUM/LOW\n'
                '- Blocker Present: Yes/No\n'
                '- Business-Critical Services Affected: ...\n'
                '## 2. High-Priority Impacted Assets\n'
                '| Asset | Severity | Symptom | Likely Cause | Business Impact | Recommended Action |\n'
                '| --- | --- | --- | --- | --- | --- |\n'
                '## 3. Impacted APIs / Systems / Domains\n'
                '| Target | Type | Severity | Effect | Owner Team |\n'
                '| --- | --- | --- | --- | --- |\n'
                '## 4. Stakeholder Action Plan\n'
                '### Immediate (0-30 min)\n'
                '1. ...\n'
                '### Near-Term (30-120 min)\n'
                '1. ...\n'
                '### Recovery Validation\n'
                '- Freshness check:\n'
                '- Completeness check:'
            ),
            'example_input': 'If Silver.customer_contact fails, what is blast radius?',
            'example_output': (
                'Incident report with severity headline, impact tables, and time-bounded action plan.'
            ),
            'is_default': False,
            'status': 'active',
            'version': 'v2',
        },
        {
            'name': 'SLA Quick Status',
            'template_key': 'sla.quick.v1',
            'scene_type': SCENE_SLA,
            'description': 'One-screen SLA status board with breach urgency and immediate response guidance.',
            'usage_notes': (
                'Use for real-time operations pages and NOC-style health checks.'
            ),
            'prompt_content': (
                'You are an enterprise SLA operations assistant.\n'
                'Report current SLA state for each requested asset using healthy / at_risk / breach.\n'
                'Include delay minutes, configured thresholds, and immediate action recommendation.\n'
                'Prioritize breach and near-breach assets at the top.\n'
                'Do not include vague language; keep actionable.'
            ),
            'output_format': (
                '# SLA Quick Status - {scope}\n'
                '## 1. Current SLA Signal\n'
                '- Overall SLA Health: Green / Yellow / Red\n'
                '- Breached Assets Count:\n'
                '- At-Risk Assets Count:\n'
                '## 2. SLA Table\n'
                '| Asset | Status | Delay (min) | Warning Threshold | Breach Threshold | Owner | Immediate Action |\n'
                '| --- | --- | --- | --- | --- | --- | --- |\n'
                '## 3. Priority Follow-up (Next 30 min)\n'
                '1. ...\n'
                '2. ...'
            ),
            'example_input': 'Current SLA status for API.customer_profile',
            'example_output': (
                'Compact SLA table sorted by urgency, plus 30-minute follow-up actions.'
            ),
            'is_default': True,
            'status': 'active',
            'version': 'v2',
        },
        {
            'name': 'SLA Detailed Analysis',
            'template_key': 'sla.detailed.v1',
            'scene_type': SCENE_SLA,
            'description': 'Production-grade SLA diagnostics with trend, causal chain, and remediation ownership.',
            'usage_notes': (
                'Use for incident review and deeper analysis beyond quick SLA board.'
            ),
            'prompt_content': (
                'You are an SLA diagnostics lead for enterprise data pipelines.\n'
                'Correlate SLA delay with runtime failures, lineage dependencies, and data quality degradation.\n'
                'For each critical issue, provide symptom, root cause hypothesis, business impact, and fix recommendation.\n'
                'Include confidence level and missing evidence required for confirmation.\n'
                'Project near-term risk for the next 2 reporting windows.'
            ),
            'output_format': (
                '# SLA Diagnostic Report - {asset_or_domain}\n'
                '## 1. Current Status & Severity\n'
                '- Status:\n'
                '- Delay:\n'
                '- Breach Risk Horizon:\n'
                '## 2. Signal Correlation\n'
                '| Signal Type | Observation | Evidence |\n'
                '| --- | --- | --- |\n'
                '## 3. Critical Issues\n'
                '| Asset | Symptom | Root Cause Hypothesis | Business Impact | Recommendation | Confidence |\n'
                '| --- | --- | --- | --- | --- | --- |\n'
                '## 4. Risk Projection (Next 2 Windows)\n'
                '- Window 1:\n'
                '- Window 2:\n'
                '## 5. Remediation Plan\n'
                '### Immediate\n'
                '### This Shift\n'
                '### Preventive Hardening'
            ),
            'example_input': 'Analyze why Gold.customer_profile is at SLA risk',
            'example_output': (
                'Detailed SLA diagnosis with correlated evidence, critical issue table, and phased remediation.'
            ),
            'is_default': False,
            'status': 'active',
            'version': 'v2',
        },
        {
            'name': 'SLA Stakeholder Brief',
            'template_key': 'sla.exec.v1',
            'scene_type': SCENE_SLA,
            'description': 'Stakeholder-facing SLA brief with business risk and decision requests.',
            'usage_notes': (
                'Use when clear decisions and impact framing are required for stakeholders.'
            ),
            'prompt_content': (
                'You are a stakeholder communications analyst for data platform reliability.\n'
                'Summarize SLA health in business language while preserving operational accuracy.\n'
                'Highlight revenue/customer/operations risks and decision needs.\n'
                'Avoid deep technical jargon unless essential for decision-making.'
            ),
            'output_format': (
                '# SLA Executive Brief - {date_or_window}\n'
                '## 1. Executive Summary\n'
                '- Platform SLA Status: Green / Yellow / Red\n'
                '- Core Business Risk: Low/Medium/High/Critical\n'
                '- Escalation Required: Yes/No\n'
                '## 2. Business Impact Snapshot\n'
                '| Area | Impact | Severity | Time Sensitivity |\n'
                '| --- | --- | --- | --- |\n'
                '## 3. What Changed Since Last Update\n'
                '- ...\n'
                '## 4. Decisions Needed Today\n'
                '1. ...\n'
                '2. ...\n'
                '## 5. Next Update ETA\n'
                '- ...'
            ),
            'example_input': 'Create SLA brief for Customer domain',
            'example_output': (
                'Executive SLA brief with business impact table and explicit decision requests.'
            ),
            'is_default': False,
            'status': 'active',
            'version': 'v2',
        },
        {
            'name': 'Daily Report Engineer',
            'template_key': 'daily.engineer.v1',
            'scene_type': SCENE_DAILY,
            'description': 'Enterprise-grade daily production report for platform and data engineering teams.',
            'usage_notes': (
                'Use for daily ops review, incident handoff, and cross-team reliability sync.'
            ),
            'prompt_content': (
                'You are an enterprise Data Platform and Data Governance analyst.\n'
                'Generate a production-grade Daily Data Pipeline Report using runtime signals, failed jobs, SLA indicators, lineage impact, and data quality signals.\n'
                'The report must support engineering troubleshooting, platform operations, stakeholder communication, and business risk alignment.\n'
                'Prioritize CRITICAL issues first.\n'
                'Each major issue must include: symptom, likely cause, business/technical impact, and recommended action.\n'
                'Write in professional, concise, execution-focused language.\n'
                'Do not mention any AI/meta wording.\n'
                'If evidence is partial, clearly mark uncertainty and list data needed.\n'
                'Report depth requirements:\n'
                '- Critical section must include all High/Critical signals available.\n'
                '- Include concrete metrics (counts, delay minutes, threshold, trend) whenever available.\n'
                '- Include an ownership/action tracker with owner and ETA.\n'
                '- Include an explicit risk outlook for next 24h.\n'
                '- Include what has recovered vs what remains at risk.'
            ),
            'output_format': (
                '# 📊 Daily Data Pipeline Report - {date}\n'
                '## 🧭 1. Executive Summary\n'
                '- Overall platform status: Green / Yellow / Red\n'
                '- Blocking issues:\n'
                '- Core business impact:\n'
                '- Immediate action required:\n'
                '## 🏥 2. Domain Health Overview\n'
                '### {Domain Name} - {Status}\n'
                '- Status:\n'
                '- Impact Level:\n'
                '- Summary:\n'
                '- Root Cause:\n'
                '## 🚨 3. Critical Failures & Blockers\n'
                '| Asset | Severity | Error Type | Symptom | Likely Cause | Business Impact | Recommendation |\n'
                '| --- | --- | --- | --- | --- | --- | --- |\n'
                '## 🧱 4. Pipeline Execution Summary\n'
                '| Metric | Value | Delta vs Yesterday | Note |\n'
                '| --- | --- | --- | --- |\n'
                '- Total pipelines:\n'
                '- Successful:\n'
                '- Failed:\n'
                '- Retried:\n'
                '## ⏱️ 5. SLA Status & Delay Analysis\n'
                '### SLA Breaches\n'
                '- ...\n'
                '### At Risk\n'
                '- ...\n'
                '## 🗓️ 6. Incident Timeline (Top 3)\n'
                '| Time | Event | Severity | Current State |\n'
                '| --- | --- | --- | --- |\n'
                '## 🔗 7. Impact Analysis\n'
                '### Data Assets\n'
                '### Downstream Systems\n'
                '### Business Impact\n'
                '## 🧠 8. Root Cause Analysis\n'
                '- ...\n'
                '## 🛠️ 9. Recommended Actions\n'
                '### Immediate\n'
                '1. ...\n'
                '### Short-term\n'
                '1. ...\n'
                '### Long-term\n'
                '1. ...\n'
                '## 👥 10. Owner & ETA Tracker\n'
                '| Action | Owner Team | Owner | ETA | Status |\n'
                '| --- | --- | --- | --- | --- |\n'
                '## 📈 11. Trends & Observations\n'
                '- ...\n'
                '## 🧪 12. Data Quality Signals\n'
                '| Metric | Current | Trend | Risk Note |\n'
                '| --- | --- | --- | --- |\n'
                '## 🔮 13. Next 24h Risk Outlook\n'
                '- Expected risk changes:\n'
                '- Watchlist assets:\n'
                '- Escalation trigger:\n'
                '## 📎 14. Appendix\n'
                '- Key errors:\n'
                '- Affected jobs:\n'
                '- Missing windows:'
            ),
            'example_input': 'Generate today daily report',
            'example_output': (
                'A full production daily report with 13 sections, metrics, timeline, owner tracker, and next-24h outlook.'
            ),
            'is_default': True,
            'status': 'active',
            'version': 'v3',
        },
        {
            'name': 'Daily Report Management',
            'template_key': 'daily.management.v1',
            'scene_type': SCENE_DAILY,
            'description': 'Stakeholder daily summary emphasizing risk, continuity, and decisions.',
            'usage_notes': (
                'Use for stakeholder updates and business communication.'
            ),
            'prompt_content': (
                'You are a data platform status reporter.\n'
                'Produce a stakeholder-ready daily summary with clear status, risk, and required decisions.\n'
                'Keep it concise but concrete, with explicit business impact.\n'
                'Prioritize critical issues and mitigation progress.\n'
                'Do not use technical noise unless needed for stakeholder decisions.\n'
                'Include explicit asks to stakeholders when additional resources or risk acceptance is required.'
            ),
            'output_format': (
                '# Daily Data Platform Stakeholder Brief - {date}\n'
                '## 1. Stakeholder Headline\n'
                '- Platform status: Green / Yellow / Red\n'
                '- Business continuity risk:\n'
                '## 2. Top Incidents (Critical First)\n'
                '| Incident | Severity | Business Impact | Mitigation Status | ETA |\n'
                '| --- | --- | --- | --- | --- |\n'
                '## 3. Domain-Level Health\n'
                '| Domain | Status | Trend | Escalation Needed |\n'
                '| --- | --- | --- | --- |\n'
                '## 4. KPI Snapshot\n'
                '| KPI | Today | Yesterday | Trend |\n'
                '| --- | --- | --- | --- |\n'
                '## 5. Decisions / Support Needed\n'
                '1. ...\n'
                '2. ...\n'
                '## 6. Next 24h Risk Outlook\n'
                '- ...'
            ),
            'example_input': 'Daily management report for metadata platform',
            'example_output': (
                'Executive summary with incident table, domain health trend, and clear decision asks.'
            ),
            'is_default': False,
            'status': 'active',
            'version': 'v3',
        },
        {
            'name': 'Daily Report Enterprise Deck',
            'template_key': 'daily.enterprise.v1',
            'scene_type': SCENE_DAILY,
            'description': 'Polished enterprise communication format for cross-functional reporting.',
            'usage_notes': (
                'Use for enterprise portal updates, reliability newsletter, or broad stakeholder broadcast.'
            ),
            'prompt_content': (
                'You are an enterprise reliability communications writer for data governance.\n'
                'Create a polished but factual report suitable for broad distribution.\n'
                'Maintain strong structure, concise language, and clear accountability.\n'
                'Critical issues must still be explicit; do not over-soften operational risk.'
            ),
            'output_format': (
                '# Enterprise Data Reliability Update - {date}\n'
                '## Highlights\n'
                '- ...\n'
                '## Reliability Scorecard\n'
                '| Category | Status | Key Note |\n'
                '| --- | --- | --- |\n'
                '## Incident & Recovery Narrative\n'
                '### What happened\n'
                '### What was impacted\n'
                '### What has been recovered\n'
                '### What still needs attention\n'
                '## Governance Actions\n'
                '- Owner + action + due date\n'
                '## Tomorrow Focus\n'
                '- ...'
            ),
            'example_input': 'Prepare enterprise daily reliability report',
            'example_output': (
                'Polished enterprise report with scorecard, incident narrative, and ownership-oriented actions.'
            ),
            'is_default': False,
            'status': 'active',
            'version': 'v3',
        },
        {
            'name': 'Failed Jobs Quick Triage',
            'template_key': 'failed.quick.v1',
            'scene_type': SCENE_FAILED,
            'description': 'High-speed incident triage for failed jobs with first-action runbook steps.',
            'usage_notes': (
                'Use for first responders to prioritize failure queue and start mitigation quickly.'
            ),
            'prompt_content': (
                'You are a production incident triage assistant for failed pipeline jobs.\n'
                'Group by severity and urgency; put CRITICAL/HIGH first.\n'
                'For each key failure include symptom, likely cause, impact, and first action.\n'
                'Provide concrete and executable steps, not generic advice.'
            ),
            'output_format': (
                '# Failed Jobs Quick Triage - {date_or_window}\n'
                '## 1. Triage Summary\n'
                '- Total failed jobs:\n'
                '- Critical blockers:\n'
                '- Estimated blast radius:\n'
                '## 2. Priority Queue\n'
                '| Priority | Job/Asset | Error Signature | Symptom | Likely Cause | Impact | First Action |\n'
                '| --- | --- | --- | --- | --- | --- | --- |\n'
                '## 3. 30-Minute Runbook\n'
                '1. Stabilize:\n'
                '2. Contain:\n'
                '3. Verify:'
            ),
            'example_input': 'Show failed jobs and what to do first',
            'example_output': (
                'Priority triage table with concrete runbook actions for next 30 minutes.'
            ),
            'is_default': True,
            'status': 'active',
            'version': 'v2',
        },
        {
            'name': 'Failed Jobs Batch Summary',
            'template_key': 'failed.batch.v1',
            'scene_type': SCENE_FAILED,
            'description': 'Pattern-based aggregation for high-volume failure waves.',
            'usage_notes': (
                'Use when many pipelines fail together and correlation is needed for containment strategy.'
            ),
            'prompt_content': (
                'You are a batch-failure pattern analyst.\n'
                'Group failed jobs by error signature, dependency cluster, domain, and time window.\n'
                'Identify likely common cause and proposed containment strategy per cluster.\n'
                'Call out any cluster that threatens business-critical APIs or reporting.'
            ),
            'output_format': (
                '# Batch Failure Pattern Report - {date_or_window}\n'
                '## 1. Cluster Overview\n'
                '| Cluster Key | Failure Count | Dominant Error | Primary Domain | Risk Level |\n'
                '| --- | --- | --- | --- | --- |\n'
                '## 2. Cluster Details\n'
                '| Cluster Key | Representative Jobs/Assets | Likely Common Cause | Business Impact | Containment Action |\n'
                '| --- | --- | --- | --- | --- |\n'
                '## 3. Cross-Cluster Observations\n'
                '- ...\n'
                '## 4. Containment Plan\n'
                '### Immediate\n'
                '### Next 2 Hours'
            ),
            'example_input': 'Summarize all failed jobs by pattern',
            'example_output': (
                'Clustered failure analysis with common-cause hypotheses and containment recommendations.'
            ),
            'is_default': False,
            'status': 'active',
            'version': 'v2',
        },
        {
            'name': 'Failed Jobs Root Cause Analysis',
            'template_key': 'failed.rca.v1',
            'scene_type': SCENE_FAILED,
            'description': 'RCA-ready structure for postmortem drafting and prevention planning.',
            'usage_notes': (
                'Use after stabilization to produce a structured incident RCA draft.'
            ),
            'prompt_content': (
                'You are a senior reliability engineer preparing RCA for pipeline failures.\n'
                'Build a concise but complete root-cause chain from trigger to downstream consequences.\n'
                'Each major finding must include: symptom, probable cause, impact, recommendation.\n'
                'Separate confirmed facts from hypotheses.\n'
                'Include recurrence prevention with owner and control type.'
            ),
            'output_format': (
                '# Failure RCA Draft - {incident_or_window}\n'
                '## 1. Incident Summary\n'
                '- Detection time:\n'
                '- Impact window:\n'
                '- Severity:\n'
                '## 2. Symptoms\n'
                '| Symptom | First Seen | Scope |\n'
                '| --- | --- | --- |\n'
                '## 3. Root Cause Chain\n'
                '| Layer | Finding | Evidence | Confidence |\n'
                '| --- | --- | --- | --- |\n'
                '## 4. Impact Assessment\n'
                '- Technical impact:\n'
                '- Business impact:\n'
                '## 5. Corrective Actions\n'
                '### Immediate Fixes\n'
                '### Preventive Controls\n'
                '## 6. Recurrence Prevention Tracker\n'
                '| Action | Owner | Due Date | Control Type |\n'
                '| --- | --- | --- | --- |'
            ),
            'example_input': 'Analyze root cause for repeated Silver failures',
            'example_output': (
                'Structured RCA draft with evidence table, impact assessment, and prevention tracker.'
            ),
            'is_default': False,
            'status': 'active',
            'version': 'v2',
        },
        {
            'name': 'Risk Technical Assessment',
            'template_key': 'risk.tech.v1',
            'scene_type': SCENE_RISK,
            'description': 'Technical risk scoring matrix for platform reliability and governance controls.',
            'usage_notes': (
                'Use for platform governance review and reliability prioritization.'
            ),
            'prompt_content': (
                'You are an enterprise technical risk analyst for data platforms.\n'
                'Assess risk across schema drift, freshness, lineage fragility, SLA instability, and runtime reliability.\n'
                'Provide severity, confidence, blast radius, and control recommendations.\n'
                'Prioritize CRITICAL and HIGH risks with explicit mitigation timeline.'
            ),
            'output_format': (
                '# Technical Risk Assessment - {scope}\n'
                '## 1. Risk Posture Summary\n'
                '- Overall technical risk:\n'
                '- Critical risk count:\n'
                '- Highest-risk domain:\n'
                '## 2. Risk Matrix\n'
                '| Risk Type | Affected Assets | Severity | Confidence | Blast Radius | Mitigation |\n'
                '| --- | --- | --- | --- | --- | --- |\n'
                '## 3. Watchlist\n'
                '| Asset | Trigger Condition | Early Warning Signal | Owner |\n'
                '| --- | --- | --- | --- |\n'
                '## 4. Priority Mitigation Plan\n'
                '### Immediate\n'
                '### This Week\n'
                '### Structural Hardening'
            ),
            'example_input': 'Assess current technical risks in Customer pipelines',
            'example_output': (
                'Risk matrix with severity/confidence/blast radius and phased mitigation plan.'
            ),
            'is_default': True,
            'status': 'active',
            'version': 'v2',
        },
        {
            'name': 'Risk Business Impact',
            'template_key': 'risk.business.v1',
            'scene_type': SCENE_RISK,
            'description': 'Business-facing risk framing by team, domain, and customer consequence.',
            'usage_notes': (
                'Use for product, operations, and business stakeholders to understand exposure.'
            ),
            'prompt_content': (
                'You are a business risk translator for data platform incidents.\n'
                'Convert technical issues into business consequences by team, domain, and customer journey.\n'
                'State impact severity, urgency, and decision implications.\n'
                'Each high-priority risk must include symptom, cause, impact, and recommended action.'
            ),
            'output_format': (
                '# Business Risk Impact Report - {date_or_scope}\n'
                '## 1. Business Risk Headline\n'
                '- Overall business risk: Low/Medium/High/Critical\n'
                '- Most exposed business process:\n'
                '## 2. Impacted Teams\n'
                '| Team | Risk Level | Symptom | Likely Cause | Business Effect | Recommended Action |\n'
                '| --- | --- | --- | --- | --- | --- |\n'
                '## 3. Impacted Domains / Products\n'
                '| Domain/Product | Risk Level | Service Impact | Decision Required |\n'
                '| --- | --- | --- | --- |\n'
                '## 4. Customer / Revenue / Ops Exposure\n'
                '- ...\n'
                '## 5. Priority Business Actions\n'
                '1. ...\n'
                '2. ...'
            ),
            'example_input': 'What business risks are caused by current pipeline issues?',
            'example_output': (
                'Business risk report with team/domain tables and explicit decision/action points.'
            ),
            'is_default': False,
            'status': 'active',
            'version': 'v2',
        },
        {
            'name': 'Risk Governance Recommendation',
            'template_key': 'risk.governance.v1',
            'scene_type': SCENE_RISK,
            'description': 'Governance control strategy with ownership and measurable outcomes.',
            'usage_notes': (
                'Use for governance committee and data reliability program planning.'
            ),
            'prompt_content': (
                'You are a data governance strategy lead.\n'
                'Based on observed technical and business risks, propose governance controls, ownership model, and policy improvements.\n'
                'Recommendations must be specific, prioritized, and measurable.\n'
                'Include immediate, short-term, and long-term governance actions.'
            ),
            'output_format': (
                '# Governance Recommendation Report - {scope}\n'
                '## 1. Governance Risk Summary\n'
                '- Control maturity:\n'
                '- Highest governance gap:\n'
                '## 2. Priority Controls (30/60/90)\n'
                '| Horizon | Control | Risk Addressed | Owner | Success Metric |\n'
                '| --- | --- | --- | --- | --- |\n'
                '## 3. Ownership & Accountability Model\n'
                '| Function | Responsibility | Escalation Path |\n'
                '| --- | --- | --- |\n'
                '## 4. Policy / Process Updates\n'
                '- Data contract policy:\n'
                '- Schema change protocol:\n'
                '- Incident RCA standard:\n'
                '## 5. KPI Framework\n'
                '| KPI | Baseline | Target | Review Cadence |\n'
                '| --- | --- | --- | --- |'
            ),
            'example_input': 'Provide governance recommendations for risk reduction',
            'example_output': (
                'Governance roadmap with 30/60/90 controls, ownership model, and KPI tracking framework.'
            ),
            'is_default': False,
            'status': 'active',
            'version': 'v2',
        },
    ]


def _default_tool_scene_bindings() -> dict[str, list[str]]:
    return {
        'get_downstream': [SCENE_LINEAGE, SCENE_RISK],
        'get_upstream': [SCENE_LINEAGE, SCENE_RISK],
        'get_asset': [SCENE_LINEAGE, SCENE_SLA],
        'get_asset_detail': [SCENE_LINEAGE, SCENE_SLA, SCENE_RISK],
        'get_failed_runs': [SCENE_FAILED, SCENE_DAILY],
        'get_business_impact': [SCENE_LINEAGE, SCENE_RISK],
        'get_impacted_apis': [SCENE_LINEAGE, SCENE_RISK],
        'get_sla_risk_assets': [SCENE_SLA, SCENE_DAILY, SCENE_RISK],
        'generate_daily_summary': [SCENE_DAILY, SCENE_RISK],
        'get_domain_health': [SCENE_DAILY, SCENE_SLA],
    }


def _seed_prompt_templates(db: Session) -> bool:
    changed = False
    existing = {
        item.template_key: item
        for item in db.execute(select(PromptTemplateRecord)).scalars().all()
    }
    scene_default_map = {
        item.scene_type: item.template_key
        for item in existing.values()
        if item.is_default
    }

    for template in _default_prompt_templates():
        key = template['template_key']
        row = existing.get(key)
        if not row:
            row = PromptTemplateRecord(**template)
            db.add(row)
            existing[key] = row
            changed = True
            continue
        for field in [
            'name',
            'scene_type',
            'description',
            'usage_notes',
            'prompt_content',
            'output_format',
            'example_input',
            'example_output',
            'status',
            'version',
        ]:
            new_value = template.get(field)
            if getattr(row, field) != new_value:
                setattr(row, field, new_value)
                changed = True

    db.flush()

    templates = db.execute(select(PromptTemplateRecord)).scalars().all()
    by_scene: dict[str, list[PromptTemplateRecord]] = {}
    for row in templates:
        by_scene.setdefault(row.scene_type, []).append(row)

    # Keep one default template per scene.
    for scene, rows in by_scene.items():
        preferred_key = scene_default_map.get(scene) or next(
            (
                item['template_key']
                for item in _default_prompt_templates()
                if item['scene_type'] == scene and item.get('is_default')
            ),
            None,
        )
        for row in rows:
            should_default = row.template_key == preferred_key
            if row.is_default != should_default:
                row.is_default = should_default
                changed = True

    # Version snapshots
    existing_versions = {
        (item.prompt_template_id, item.version)
        for item in db.execute(select(PromptTemplateVersionRecord)).scalars().all()
    }
    for row in templates:
        key = (row.id, row.version)
        if key in existing_versions:
            continue
        db.add(
            PromptTemplateVersionRecord(
                prompt_template_id=row.id,
                version=row.version,
                change_log='Bootstrap template snapshot.',
                prompt_content=row.prompt_content,
                output_format=row.output_format,
                status=row.status,
            )
        )
        changed = True
    return changed


def _seed_tool_prompt_bindings(db: Session) -> bool:
    changed = False
    tools = {
        item.name: item
        for item in db.execute(select(ToolDefinitionRecord)).scalars().all()
    }
    defaults = {
        item.scene_type: item.id
        for item in db.execute(
            select(PromptTemplateRecord).where(PromptTemplateRecord.is_default == True)
        )
        .scalars()
        .all()
    }
    existing = {
        (item.tool_id, item.scene_type, item.prompt_template_id): item
        for item in db.execute(select(ToolPromptBindingRecord)).scalars().all()
    }
    for tool_name, scenes in _default_tool_scene_bindings().items():
        tool = tools.get(tool_name)
        if not tool:
            continue
        for scene in scenes:
            template_id = defaults.get(scene)
            if not template_id:
                continue
            key = (tool.id, scene, template_id)
            if key in existing:
                continue
            db.add(
                ToolPromptBindingRecord(
                    tool_id=tool.id,
                    scene_type=scene,
                    prompt_template_id=template_id,
                    is_default=True,
                )
            )
            changed = True
    db.flush()

    # Normalize one default per tool + scene
    groups: dict[tuple[int, str], list[ToolPromptBindingRecord]] = {}
    for row in db.execute(select(ToolPromptBindingRecord)).scalars().all():
        groups.setdefault((row.tool_id, row.scene_type), []).append(row)
    for _, rows in groups.items():
        default_rows = [r for r in rows if r.is_default]
        if len(default_rows) == 1:
            continue
        chosen = rows[0]
        for row in rows:
            should_default = row.id == chosen.id
            if row.is_default != should_default:
                row.is_default = should_default
                changed = True
    return changed

def bootstrap_admin_catalog(db: Session):
    changed = False

    existing_tools = {
        item.name: item
        for item in db.execute(select(ToolDefinitionRecord)).scalars().all()
    }
    for tool_def in TOOL_DEFINITIONS:
        fn = tool_def.get('function', {})
        name = fn.get('name')
        if not name:
            continue
        schema = fn.get('parameters') or {}
        description = fn.get('description')
        display_name = name.replace('_', ' ').title()
        tool = existing_tools.get(name)
        if not tool:
            tool = ToolDefinitionRecord(
                name=name,
                display_name=display_name,
                description=description,
                enabled=True,
                input_schema_json=schema,
                output_schema_json={},
            )
            db.add(tool)
            existing_tools[name] = tool
            changed = True
            continue
        if not tool.description and description:
            tool.description = description
            changed = True
        if not tool.input_schema_json:
            tool.input_schema_json = schema
            changed = True
        if not tool.display_name:
            tool.display_name = display_name
            changed = True

    db.flush()
    existing_versions = {
        (item.tool_id, item.version)
        for item in db.execute(select(ToolVersionRecord)).scalars().all()
    }
    for tool in existing_tools.values():
        key = (tool.id, 'v1')
        if key in existing_versions:
            continue
        db.add(
            ToolVersionRecord(
                tool_id=tool.id,
                version='v1',
                is_active=True,
                changelog='Initial version synced from tool registry.',
                schema_json=tool.input_schema_json,
            )
        )
        changed = True

    existing_sources = {
        item.name.lower(): item
        for item in db.execute(select(DataSourceRecord)).scalars().all()
    }
    systems = db.execute(select(System)).scalars().all()
    for system in systems:
        key = (system.name or '').lower()
        if key in existing_sources:
            continue
        ds = DataSourceRecord(
            name=system.name,
            source_type=system.system_type or 'database',
            connection_uri='',
            config_json={'environment': system.environment},
            enabled=True,
        )
        db.add(ds)
        existing_sources[key] = ds
        changed = True

    db.flush()
    sources_by_name = {
        item.name.lower(): item
        for item in db.execute(select(DataSourceRecord)).scalars().all()
    }
    existing_tables = {
        (item.data_source_id, item.schema_name, item.table_name)
        for item in db.execute(select(DataSourceTableRecord)).scalars().all()
    }
    assets = db.execute(
        select(Asset).options(
            joinedload(Asset.system),
            joinedload(Asset.domain),
            joinedload(Asset.asset_type),
        )
    ).scalars().all()
    for asset in assets:
        if not asset.system:
            continue
        source = sources_by_name.get(asset.system.name.lower())
        if not source:
            continue
        schema_name = asset.domain.name if asset.domain else 'default'
        key = (source.id, schema_name, asset.name)
        if key in existing_tables:
            continue
        db.add(
            DataSourceTableRecord(
                data_source_id=source.id,
                schema_name=schema_name,
                table_name=asset.name,
                description=asset.description,
                sample_json={
                    'qualified_name': asset.qualified_name,
                    'refresh_frequency': asset.refresh_frequency,
                    'asset_type': asset.asset_type.name if asset.asset_type else None,
                },
            )
        )
        changed = True

    if (
        not db.execute(
            select(ScheduledJobRecord).where(ScheduledJobRecord.name == 'daily_summary')
        ).scalar_one_or_none()
    ):
        db.add(
            ScheduledJobRecord(
                name='daily_summary',
                job_type='daily_summary',
                cron_expr='0 8 * * *',
                enabled=True,
                status='idle',
                config_json={'description': 'Generate daily governance report.'},
            )
        )
        changed = True
    if (
        not db.execute(
            select(ScheduledJobRecord).where(ScheduledJobRecord.name == 'refresh_runtime')
        ).scalar_one_or_none()
    ):
        db.add(
            ScheduledJobRecord(
                name='refresh_runtime',
                job_type='metadata_sync',
                cron_expr='*/15 * * * *',
                enabled=True,
                status='idle',
                config_json={'description': 'Refresh runtime overview cache.'},
            )
        )
        changed = True

    if _seed_prompt_templates(db):
        changed = True
    if _seed_tool_prompt_bindings(db):
        changed = True

    if changed:
        db.commit()


class AdminService:
    def __init__(self, db: Session):
        self.db = db
        self.asset_service = AssetService(db)

    def _add_audit_log(
        self,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        details: dict[str, Any] | None = None,
        actor: str | None = 'admin_ui',
    ):
        self.db.add(
            AuditLogRecord(
                actor=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details_json=details or {},
            )
        )

    def get_dashboard(self):
        failed_event_count = self.db.scalar(
            select(func.count(RuntimeEvent.id)).where(RuntimeEvent.status == 'FAILED')
        ) or 0
        tool_count = self.db.scalar(select(func.count(ToolDefinitionRecord.id))) or 0
        source_count = self.db.scalar(select(func.count(DataSourceRecord.id))) or 0
        chat_count = self.db.scalar(select(func.count(ChatSessionRecord.id))) or 0
        memory_count = self.db.scalar(select(func.count(MemoryRecord.id))) or 0
        job_count = self.db.scalar(select(func.count(ScheduledJobRecord.id))) or 0
        channel_count = self.db.scalar(select(func.count(ChannelRecord.id))) or 0
        prompt_template_count = (
            self.db.scalar(select(func.count(PromptTemplateRecord.id))) or 0
        )

        recent_runs = self.db.execute(
            select(JobRunRecord, ScheduledJobRecord)
            .join(ScheduledJobRecord, ScheduledJobRecord.id == JobRunRecord.job_id)
            .order_by(JobRunRecord.started_at.desc())
            .limit(5)
        ).all()

        recent_errors = self.db.execute(
            select(RuntimeEvent)
            .where(RuntimeEvent.status == 'FAILED')
            .order_by(RuntimeEvent.occurred_at.desc())
            .limit(5)
        ).scalars().all()

        status = 'degraded' if failed_event_count > 0 else 'healthy'
        return to_jsonable(
            {
                'stats': {
                    'tools': tool_count,
                    'data_sources': source_count,
                    'chat_sessions': chat_count,
                    'memories': memory_count,
                    'jobs': job_count,
                    'channels': channel_count,
                    'prompt_templates': prompt_template_count,
                },
                'system_status': status,
                'recent_tasks': [
                    {
                        'run_id': run.id,
                        'job_name': job.name,
                        'status': run.status,
                        'started_at': run.started_at,
                        'duration_ms': run.duration_ms,
                    }
                    for run, job in recent_runs
                ],
                'recent_errors': [
                    {
                        'event_id': item.id,
                        'status': item.status,
                        'severity': item.severity,
                        'error_code': item.error_code,
                        'error_message': item.error_message,
                        'occurred_at': item.occurred_at,
                    }
                    for item in recent_errors
                ],
            }
        )

    def list_tools(self, q: str | None = None, enabled: bool | None = None):
        stmt = select(ToolDefinitionRecord).order_by(ToolDefinitionRecord.name.asc())
        if q:
            like_q = f'%{q.strip()}%'
            stmt = stmt.where(
                ToolDefinitionRecord.name.like(like_q)
                | ToolDefinitionRecord.description.like(like_q)
            )
        if enabled is not None:
            stmt = stmt.where(ToolDefinitionRecord.enabled == enabled)
        tools = self.db.execute(stmt).scalars().all()
        version_map: dict[int, list[ToolVersionRecord]] = {}
        all_versions = self.db.execute(select(ToolVersionRecord)).scalars().all()
        for version in all_versions:
            version_map.setdefault(version.tool_id, []).append(version)
        binding_rows = self.db.execute(select(ToolPromptBindingRecord)).scalars().all()
        binding_map: dict[int, list[ToolPromptBindingRecord]] = {}
        for binding in binding_rows:
            binding_map.setdefault(binding.tool_id, []).append(binding)
        return to_jsonable(
            [
                {
                    'id': item.id,
                    'name': item.name,
                    'display_name': item.display_name,
                    'description': item.description,
                    'enabled': item.enabled,
                    'input_schema_json': item.input_schema_json,
                    'output_schema_json': item.output_schema_json,
                    'active_version': next(
                        (
                            version.version
                            for version in version_map.get(item.id, [])
                            if version.is_active
                        ),
                        None,
                    ),
                    'version_count': len(version_map.get(item.id, [])),
                    'bound_prompt_count': len(binding_map.get(item.id, [])),
                    'bound_scenes': sorted(
                        list({row.scene_type for row in binding_map.get(item.id, [])})
                    ),
                    'updated_at': item.updated_at,
                }
                for item in tools
            ]
        )

    def get_tool(self, tool_id: int):
        tool = self.db.get(ToolDefinitionRecord, tool_id)
        if not tool:
            return None
        versions = self.db.execute(
            select(ToolVersionRecord)
            .where(ToolVersionRecord.tool_id == tool.id)
            .order_by(ToolVersionRecord.created_at.desc())
        ).scalars().all()
        bindings = self.db.execute(
            select(ToolPromptBindingRecord, PromptTemplateRecord)
            .join(
                PromptTemplateRecord,
                PromptTemplateRecord.id == ToolPromptBindingRecord.prompt_template_id,
            )
            .where(ToolPromptBindingRecord.tool_id == tool.id)
            .order_by(ToolPromptBindingRecord.scene_type.asc(), PromptTemplateRecord.name.asc())
        ).all()
        return to_jsonable(
            {
                'id': tool.id,
                'name': tool.name,
                'display_name': tool.display_name,
                'description': tool.description,
                'enabled': tool.enabled,
                'input_schema_json': tool.input_schema_json,
                'output_schema_json': tool.output_schema_json,
                'versions': [
                    {
                        'id': version.id,
                        'version': version.version,
                        'is_active': version.is_active,
                        'changelog': version.changelog,
                        'schema_json': version.schema_json,
                        'created_at': version.created_at,
                    }
                    for version in versions
                ],
                'prompt_bindings': [
                    {
                        'id': binding.id,
                        'scene_type': binding.scene_type,
                        'prompt_template_id': binding.prompt_template_id,
                        'is_default': binding.is_default,
                        'template_key': template.template_key,
                        'template_name': template.name,
                        'template_status': template.status,
                        'template_version': template.version,
                    }
                    for binding, template in bindings
                ],
            }
        )

    def update_tool(self, tool_id: int, payload: dict[str, Any]):
        tool = self.db.get(ToolDefinitionRecord, tool_id)
        if not tool:
            return None
        if payload.get('description') is not None:
            tool.description = payload['description']
        if payload.get('enabled') is not None:
            tool.enabled = bool(payload['enabled'])
        if payload.get('output_schema_json') is not None:
            tool.output_schema_json = payload['output_schema_json']
        self._add_audit_log(
            action='tool.updated',
            entity_type='tool',
            entity_id=str(tool.id),
            details=payload,
        )
        self.db.commit()
        return self.get_tool(tool.id)

    def list_tool_versions(self, tool_id: int | None = None):
        stmt = select(ToolVersionRecord, ToolDefinitionRecord).join(
            ToolDefinitionRecord, ToolDefinitionRecord.id == ToolVersionRecord.tool_id
        )
        if tool_id:
            stmt = stmt.where(ToolVersionRecord.tool_id == tool_id)
        rows = self.db.execute(stmt.order_by(ToolVersionRecord.created_at.desc())).all()
        return to_jsonable(
            [
                {
                    'id': version.id,
                    'tool_id': version.tool_id,
                    'tool_name': tool.name,
                    'version': version.version,
                    'is_active': version.is_active,
                    'changelog': version.changelog,
                    'schema_json': version.schema_json,
                    'created_at': version.created_at,
                }
                for version, tool in rows
            ]
        )

    def list_data_sources(self):
        rows = self.db.execute(
            select(DataSourceRecord).order_by(DataSourceRecord.name.asc())
        ).scalars().all()
        table_counts = {
            source_id: count
            for source_id, count in self.db.execute(
                select(
                    DataSourceTableRecord.data_source_id,
                    func.count(DataSourceTableRecord.id),
                ).group_by(DataSourceTableRecord.data_source_id)
            ).all()
        }
        return to_jsonable(
            [
                {
                    'id': item.id,
                    'name': item.name,
                    'source_type': item.source_type,
                    'connection_uri': item.connection_uri,
                    'enabled': item.enabled,
                    'config_json': item.config_json,
                    'table_count': table_counts.get(item.id, 0),
                    'updated_at': item.updated_at,
                }
                for item in rows
            ]
        )

    def get_data_source(self, source_id: int):
        source = self.db.get(DataSourceRecord, source_id)
        if not source:
            return None
        tables = self.db.execute(
            select(DataSourceTableRecord)
            .where(DataSourceTableRecord.data_source_id == source.id)
            .order_by(
                DataSourceTableRecord.schema_name.asc(),
                DataSourceTableRecord.table_name.asc(),
            )
        ).scalars().all()
        return to_jsonable(
            {
                'id': source.id,
                'name': source.name,
                'source_type': source.source_type,
                'connection_uri': source.connection_uri,
                'enabled': source.enabled,
                'config_json': source.config_json,
                'tables': [
                    {
                        'id': table.id,
                        'schema_name': table.schema_name,
                        'table_name': table.table_name,
                        'description': table.description,
                        'sample_json': table.sample_json,
                        'updated_at': table.updated_at,
                    }
                    for table in tables
                ],
            }
        )

    def list_data_source_tables(self, source_id: int, q: str | None = None):
        filters = [DataSourceTableRecord.data_source_id == source_id]
        if q:
            filters.append(
                (DataSourceTableRecord.table_name.like(f'%{q}%'))
                | (DataSourceTableRecord.schema_name.like(f'%{q}%'))
            )
        tables = self.db.execute(
            select(DataSourceTableRecord)
            .where(and_(*filters))
            .order_by(
                DataSourceTableRecord.schema_name.asc(),
                DataSourceTableRecord.table_name.asc(),
            )
        ).scalars().all()
        return to_jsonable(
            [
                {
                    'id': item.id,
                    'data_source_id': item.data_source_id,
                    'schema_name': item.schema_name,
                    'table_name': item.table_name,
                    'description': item.description,
                    'sample_json': item.sample_json,
                    'updated_at': item.updated_at,
                }
                for item in tables
            ]
        )

    def get_preview(
        self,
        source_id: int | None = None,
        table_id: int | None = None,
        format_mode: str = 'json',
    ):
        if table_id:
            table = self.db.get(DataSourceTableRecord, table_id)
            if not table:
                return None
            sample = table.sample_json or {}
            return to_jsonable(
                {
                    'mode': format_mode,
                    'source': {
                        'data_source_id': table.data_source_id,
                        'table_id': table.id,
                        'schema_name': table.schema_name,
                        'table_name': table.table_name,
                    },
                    'json': sample,
                    'rows': [sample] if isinstance(sample, dict) else sample,
                }
            )
        if source_id:
            rows = self.list_data_source_tables(source_id)
            return to_jsonable(
                {
                    'mode': format_mode,
                    'source': {'data_source_id': source_id},
                    'json': rows,
                    'rows': rows,
                }
            )
        recent_failed = RuntimeService(self.db).get_failed_runs().get('items', [])[:10]
        return to_jsonable(
            {
                'mode': format_mode,
                'source': {'data_source_id': None},
                'json': recent_failed,
                'rows': recent_failed,
            }
        )

    def list_chats(self, limit: int = 50):
        sessions = self.db.execute(
            select(ChatSessionRecord)
            .order_by(ChatSessionRecord.updated_at.desc())
            .limit(limit)
        ).scalars().all()
        message_counts = {
            chat_id: count
            for chat_id, count in self.db.execute(
                select(
                    ChatMessageRecord.chat_session_id,
                    func.count(ChatMessageRecord.id),
                ).group_by(ChatMessageRecord.chat_session_id)
            ).all()
        }
        tool_call_counts = {
            chat_id: count
            for chat_id, count in self.db.execute(
                select(
                    ToolCallRecord.chat_session_id,
                    func.count(ToolCallRecord.id),
                ).group_by(ToolCallRecord.chat_session_id)
            ).all()
        }
        return to_jsonable(
            [
                {
                    'id': item.id,
                    'session_key': item.session_key,
                    'title': item.title,
                    'status': item.status,
                    'channel_id': item.channel_id,
                    'message_count': message_counts.get(item.id, 0),
                    'tool_call_count': tool_call_counts.get(item.id, 0),
                    'last_message_at': item.last_message_at,
                    'updated_at': item.updated_at,
                    'created_at': item.created_at,
                }
                for item in sessions
            ]
        )

    def get_chat(self, chat_id: int):
        session = self.db.get(ChatSessionRecord, chat_id)
        if not session:
            return None
        messages = self.db.execute(
            select(ChatMessageRecord)
            .where(ChatMessageRecord.chat_session_id == chat_id)
            .order_by(ChatMessageRecord.message_order.asc())
        ).scalars().all()
        tool_calls = self.db.execute(
            select(ToolCallRecord)
            .where(ToolCallRecord.chat_session_id == chat_id)
            .order_by(ToolCallRecord.created_at.asc())
        ).scalars().all()
        return to_jsonable(
            {
                'session': {
                    'id': session.id,
                    'session_key': session.session_key,
                    'title': session.title,
                    'status': session.status,
                    'channel_id': session.channel_id,
                    'last_message_at': session.last_message_at,
                    'updated_at': session.updated_at,
                    'created_at': session.created_at,
                },
                'messages': [
                    {
                        'id': msg.id,
                        'role': msg.role,
                        'content': msg.content,
                        'message_order': msg.message_order,
                        'tool_name': msg.tool_name,
                        'metadata_json': msg.metadata_json,
                        'created_at': msg.created_at,
                    }
                    for msg in messages
                ],
                'tool_calls': [
                    {
                        'id': call.id,
                        'chat_message_id': call.chat_message_id,
                        'tool_name': call.tool_name,
                        'args_json': call.args_json,
                        'result_json': call.result_json,
                        'error_message': call.error_message,
                        'duration_ms': call.duration_ms,
                        'created_at': call.created_at,
                    }
                    for call in tool_calls
                ],
            }
        )

    def list_memories(self, memory_type: str | None = None, q: str | None = None):
        stmt = select(MemoryRecord).order_by(MemoryRecord.updated_at.desc())
        if memory_type:
            stmt = stmt.where(MemoryRecord.memory_type == memory_type)
        if q:
            like_q = f'%{q}%'
            stmt = stmt.where(
                MemoryRecord.title.like(like_q) | MemoryRecord.content.like(like_q)
            )
        items = self.db.execute(stmt).scalars().all()
        return to_jsonable(
            [
                {
                    'id': item.id,
                    'memory_type': item.memory_type,
                    'title': item.title,
                    'content': item.content,
                    'metadata_json': item.metadata_json,
                    'created_at': item.created_at,
                    'updated_at': item.updated_at,
                }
                for item in items
            ]
        )

    def create_memory(self, payload: dict[str, Any]):
        item = MemoryRecord(
            memory_type=payload.get('memory_type') or 'note',
            title=payload['title'],
            content=payload['content'],
            metadata_json=payload.get('metadata_json') or {},
        )
        self.db.add(item)
        self._add_audit_log(
            action='memory.created',
            entity_type='memory',
            details={'title': item.title, 'memory_type': item.memory_type},
        )
        self.db.commit()
        return to_jsonable(
            {
                'id': item.id,
                'memory_type': item.memory_type,
                'title': item.title,
                'content': item.content,
                'metadata_json': item.metadata_json,
                'created_at': item.created_at,
                'updated_at': item.updated_at,
            }
        )

    def update_memory(self, memory_id: int, payload: dict[str, Any]):
        item = self.db.get(MemoryRecord, memory_id)
        if not item:
            return None
        if payload.get('memory_type') is not None:
            item.memory_type = payload['memory_type']
        if payload.get('title') is not None:
            item.title = payload['title']
        if payload.get('content') is not None:
            item.content = payload['content']
        if payload.get('metadata_json') is not None:
            item.metadata_json = payload['metadata_json']
        self._add_audit_log(
            action='memory.updated',
            entity_type='memory',
            entity_id=str(item.id),
            details=payload,
        )
        self.db.commit()
        return to_jsonable(
            {
                'id': item.id,
                'memory_type': item.memory_type,
                'title': item.title,
                'content': item.content,
                'metadata_json': item.metadata_json,
                'created_at': item.created_at,
                'updated_at': item.updated_at,
            }
        )

    def delete_memory(self, memory_id: int):
        item = self.db.get(MemoryRecord, memory_id)
        if not item:
            return False
        self._add_audit_log(
            action='memory.deleted',
            entity_type='memory',
            entity_id=str(item.id),
            details={'title': item.title},
        )
        self.db.delete(item)
        self.db.commit()
        return True

    def list_jobs(self):
        jobs = self.db.execute(
            select(ScheduledJobRecord).order_by(ScheduledJobRecord.name.asc())
        ).scalars().all()
        run_counts = {
            job_id: count
            for job_id, count in self.db.execute(
                select(JobRunRecord.job_id, func.count(JobRunRecord.id)).group_by(
                    JobRunRecord.job_id
                )
            ).all()
        }
        return to_jsonable(
            [
                {
                    'id': item.id,
                    'name': item.name,
                    'job_type': item.job_type,
                    'cron_expr': item.cron_expr,
                    'enabled': item.enabled,
                    'status': item.status,
                    'config_json': item.config_json,
                    'last_run_at': item.last_run_at,
                    'next_run_at': item.next_run_at,
                    'run_count': run_counts.get(item.id, 0),
                    'updated_at': item.updated_at,
                }
                for item in jobs
            ]
        )

    def create_job(self, payload: dict[str, Any]):
        item = ScheduledJobRecord(
            name=payload['name'],
            job_type=payload.get('job_type') or 'metadata_sync',
            cron_expr=payload.get('cron_expr') or '*/15 * * * *',
            enabled=bool(payload.get('enabled', True)),
            status='idle',
            config_json=payload.get('config_json') or {},
        )
        self.db.add(item)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ValueError('Job name already exists.')
        self._add_audit_log(
            action='job.created',
            entity_type='job',
            entity_id=str(item.id),
            details={'name': item.name},
        )
        self.db.commit()
        return to_jsonable(
            {
                'id': item.id,
                'name': item.name,
                'job_type': item.job_type,
                'cron_expr': item.cron_expr,
                'enabled': item.enabled,
                'status': item.status,
                'config_json': item.config_json,
                'created_at': item.created_at,
            }
        )

    def run_job(self, job_id: int, triggered_by: str = 'manual'):
        job = self.db.get(ScheduledJobRecord, job_id)
        if not job:
            return None
        started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        run = JobRunRecord(
            job_id=job.id,
            status='RUNNING',
            started_at=started_at,
            triggered_by=triggered_by,
            result_json={},
        )
        job.status = 'RUNNING'
        self.db.add(run)
        self.db.flush()

        result: dict[str, Any] = {}
        status = 'SUCCESS'
        error_message = None
        try:
            if job.job_type == 'daily_summary':
                result = ReportService(self.db).generate_daily_summary(date.today())
            elif job.job_type == 'metadata_sync':
                result = {
                    'failed_runs': RuntimeService(self.db).get_failed_runs().get('count', 0),
                    'synced_at': datetime.now(timezone.utc).isoformat(),
                }
            else:
                result = {'message': 'No-op runner', 'job_type': job.job_type}
        except Exception as exc:
            status = 'FAILED'
            error_message = str(exc)

        finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        run.status = status
        run.finished_at = finished_at
        run.duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        run.error_message = error_message
        run.result_json = to_jsonable(result)
        job.status = 'IDLE' if status == 'SUCCESS' else 'FAILED'
        job.last_run_at = finished_at
        job.next_run_at = finished_at + timedelta(minutes=15)

        self._add_audit_log(
            action='job.run',
            entity_type='job',
            entity_id=str(job.id),
            details={'run_id': run.id, 'status': status},
        )
        self.db.commit()
        return to_jsonable(
            {
                'run_id': run.id,
                'job_id': job.id,
                'job_name': job.name,
                'status': run.status,
                'started_at': run.started_at,
                'finished_at': run.finished_at,
                'duration_ms': run.duration_ms,
                'error_message': run.error_message,
                'result_json': run.result_json,
            }
        )

    def list_job_runs(self, job_id: int, limit: int = 20):
        runs = self.db.execute(
            select(JobRunRecord)
            .where(JobRunRecord.job_id == job_id)
            .order_by(JobRunRecord.started_at.desc())
            .limit(limit)
        ).scalars().all()
        return to_jsonable(
            [
                {
                    'id': item.id,
                    'job_id': item.job_id,
                    'status': item.status,
                    'started_at': item.started_at,
                    'finished_at': item.finished_at,
                    'duration_ms': item.duration_ms,
                    'triggered_by': item.triggered_by,
                    'error_message': item.error_message,
                    'result_json': item.result_json,
                }
                for item in runs
            ]
        )

    def list_channels(self):
        channels = self.db.execute(
            select(ChannelRecord).order_by(ChannelRecord.updated_at.desc())
        ).scalars().all()
        return to_jsonable(
            [
                {
                    'id': item.id,
                    'channel_id': item.channel_id,
                    'channel_name': item.channel_name,
                    'channel_type': item.channel_type,
                    'enabled': item.enabled,
                    'config_json': item.config_json,
                    'default_assistant_id': item.default_assistant_id,
                    'last_seen_at': item.last_seen_at,
                    'created_at': item.created_at,
                    'updated_at': item.updated_at,
                }
                for item in channels
            ]
        )

    def create_channel(self, payload: dict[str, Any]):
        item = ChannelRecord(
            channel_id=payload['channel_id'],
            channel_name=payload['channel_name'],
            channel_type=payload.get('channel_type') or 'telegram',
            enabled=bool(payload.get('enabled', True)),
            config_json=payload.get('config_json') or {},
            default_assistant_id=payload.get('default_assistant_id'),
        )
        self.db.add(item)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ValueError('Channel ID already exists.')
        self._add_audit_log(
            action='channel.created',
            entity_type='channel',
            entity_id=str(item.id),
            details={
                'channel_id': item.channel_id,
                'channel_type': item.channel_type,
            },
        )
        self.db.commit()
        return to_jsonable(
            {
                'id': item.id,
                'channel_id': item.channel_id,
                'channel_name': item.channel_name,
                'channel_type': item.channel_type,
                'enabled': item.enabled,
                'config_json': item.config_json,
                'default_assistant_id': item.default_assistant_id,
                'created_at': item.created_at,
                'updated_at': item.updated_at,
            }
        )

    def update_channel(self, channel_id: int, payload: dict[str, Any]):
        item = self.db.get(ChannelRecord, channel_id)
        if not item:
            return None
        if payload.get('channel_name') is not None:
            item.channel_name = payload['channel_name']
        if payload.get('channel_type') is not None:
            item.channel_type = payload['channel_type']
        if payload.get('enabled') is not None:
            item.enabled = bool(payload['enabled'])
        if payload.get('config_json') is not None:
            item.config_json = payload['config_json']
        if payload.get('default_assistant_id') is not None:
            item.default_assistant_id = payload['default_assistant_id']
        self._add_audit_log(
            action='channel.updated',
            entity_type='channel',
            entity_id=str(item.id),
            details=payload,
        )
        self.db.commit()
        return to_jsonable(
            {
                'id': item.id,
                'channel_id': item.channel_id,
                'channel_name': item.channel_name,
                'channel_type': item.channel_type,
                'enabled': item.enabled,
                'config_json': item.config_json,
                'default_assistant_id': item.default_assistant_id,
                'created_at': item.created_at,
                'updated_at': item.updated_at,
            }
        )

    def list_trace(self, session_id: int | None = None, limit: int = 100):
        trace_stmt = (
            select(ToolCallRecord)
            .order_by(ToolCallRecord.created_at.desc())
            .limit(limit)
        )
        if session_id:
            trace_stmt = (
                select(ToolCallRecord)
                .where(ToolCallRecord.chat_session_id == session_id)
                .order_by(ToolCallRecord.created_at.desc())
                .limit(limit)
            )
        traces = self.db.execute(trace_stmt).scalars().all()
        runtime_errors = self.db.execute(
            select(RuntimeEvent)
            .where(RuntimeEvent.status == 'FAILED')
            .order_by(RuntimeEvent.occurred_at.desc())
            .limit(20)
        ).scalars().all()
        logs = self.db.execute(
            select(AuditLogRecord).order_by(AuditLogRecord.created_at.desc()).limit(50)
        ).scalars().all()
        return to_jsonable(
            {
                'tool_traces': [
                    {
                        'id': item.id,
                        'chat_session_id': item.chat_session_id,
                        'chat_message_id': item.chat_message_id,
                        'tool_name': item.tool_name,
                        'args_json': item.args_json,
                        'result_json': item.result_json,
                        'error_message': item.error_message,
                        'duration_ms': item.duration_ms,
                        'created_at': item.created_at,
                    }
                    for item in traces
                ],
                'runtime_errors': [
                    {
                        'id': item.id,
                        'asset_id': item.asset_id,
                        'status': item.status,
                        'severity': item.severity,
                        'occurred_at': item.occurred_at,
                        'error_code': item.error_code,
                        'error_message': item.error_message,
                        'details_json': item.details_json,
                    }
                    for item in runtime_errors
                ],
                'audit_logs': [
                    {
                        'id': item.id,
                        'actor': item.actor,
                        'action': item.action,
                        'entity_type': item.entity_type,
                        'entity_id': item.entity_id,
                        'details_json': item.details_json,
                        'created_at': item.created_at,
                    }
                    for item in logs
                ],
            }
        )

    def list_assets(self, q: str | None = None, limit: int = 200):
        stmt = (
            select(Asset)
            .options(
                joinedload(Asset.system),
                joinedload(Asset.domain),
                joinedload(Asset.asset_type),
            )
            .order_by(Asset.qualified_name.asc())
            .limit(limit)
        )
        if q:
            like_q = f'%{q.strip()}%'
            stmt = (
                select(Asset)
                .options(
                    joinedload(Asset.system),
                    joinedload(Asset.domain),
                    joinedload(Asset.asset_type),
                )
                .where(
                    Asset.name.like(like_q)
                    | Asset.qualified_name.like(like_q)
                    | Asset.description.like(like_q)
                )
                .order_by(Asset.qualified_name.asc())
                .limit(limit)
            )
        rows = self.db.execute(stmt).scalars().all()
        return to_jsonable(
            [
                {
                    'id': item.id,
                    'name': item.name,
                    'qualified_name': item.qualified_name,
                    'system': item.system.name if item.system else None,
                    'domain': item.domain.name if item.domain else None,
                    'asset_type': item.asset_type.name if item.asset_type else None,
                    'description': item.description,
                }
                for item in rows
            ]
        )

    def get_lineage(self, asset_name: str, direction: str = 'downstream'):
        normalized = (direction or 'downstream').strip().lower()
        if normalized == 'upstream':
            return self.asset_service.get_upstream(asset_name)
        return self.asset_service.get_downstream(asset_name)

    def list_prompt_templates(
        self,
        q: str | None = None,
        scene_type: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ):
        stmt = select(PromptTemplateRecord).order_by(PromptTemplateRecord.updated_at.desc())
        if q:
            like_q = f'%{q.strip()}%'
            stmt = stmt.where(
                PromptTemplateRecord.name.like(like_q)
                | PromptTemplateRecord.template_key.like(like_q)
                | PromptTemplateRecord.description.like(like_q)
            )
        if scene_type:
            stmt = stmt.where(PromptTemplateRecord.scene_type == scene_type)
        if status:
            stmt = stmt.where(PromptTemplateRecord.status == status)
        rows = self.db.execute(stmt.limit(limit)).scalars().all()
        return to_jsonable(
            [
                {
                    'id': row.id,
                    'name': row.name,
                    'template_key': row.template_key,
                    'scene_type': row.scene_type,
                    'description': row.description,
                    'usage_notes': row.usage_notes,
                    'prompt_content': row.prompt_content,
                    'output_format': row.output_format,
                    'example_input': row.example_input,
                    'example_output': row.example_output,
                    'is_default': row.is_default,
                    'status': row.status,
                    'version': row.version,
                    'created_at': row.created_at,
                    'updated_at': row.updated_at,
                }
                for row in rows
            ]
        )

    def get_prompt_template(self, template_id: int):
        row = self.db.get(PromptTemplateRecord, template_id)
        if not row:
            return None
        versions = self.db.execute(
            select(PromptTemplateVersionRecord)
            .where(PromptTemplateVersionRecord.prompt_template_id == row.id)
            .order_by(PromptTemplateVersionRecord.created_at.desc())
        ).scalars().all()
        bindings = self.db.execute(
            select(ToolPromptBindingRecord, ToolDefinitionRecord)
            .join(ToolDefinitionRecord, ToolDefinitionRecord.id == ToolPromptBindingRecord.tool_id)
            .where(ToolPromptBindingRecord.prompt_template_id == row.id)
            .order_by(ToolDefinitionRecord.name.asc())
        ).all()
        return to_jsonable(
            {
                'id': row.id,
                'name': row.name,
                'template_key': row.template_key,
                'scene_type': row.scene_type,
                'description': row.description,
                'usage_notes': row.usage_notes,
                'prompt_content': row.prompt_content,
                'output_format': row.output_format,
                'example_input': row.example_input,
                'example_output': row.example_output,
                'is_default': row.is_default,
                'status': row.status,
                'version': row.version,
                'created_at': row.created_at,
                'updated_at': row.updated_at,
                'versions': [
                    {
                        'id': item.id,
                        'version': item.version,
                        'change_log': item.change_log,
                        'status': item.status,
                        'created_at': item.created_at,
                    }
                    for item in versions
                ],
                'used_by_tools': [
                    {
                        'binding_id': binding.id,
                        'tool_id': tool.id,
                        'tool_name': tool.name,
                        'scene_type': binding.scene_type,
                        'is_default': binding.is_default,
                    }
                    for binding, tool in bindings
                ],
            }
        )

    def _normalize_scene_default(self, scene_type: str, current_id: int):
        others = self.db.execute(
            select(PromptTemplateRecord).where(
                PromptTemplateRecord.scene_type == scene_type,
                PromptTemplateRecord.id != current_id,
                PromptTemplateRecord.is_default == True,
            )
        ).scalars().all()
        for item in others:
            item.is_default = False

    def create_prompt_template(self, payload: dict[str, Any]):
        row = PromptTemplateRecord(
            name=payload['name'],
            template_key=payload['template_key'],
            scene_type=payload['scene_type'],
            description=payload.get('description'),
            usage_notes=payload.get('usage_notes'),
            prompt_content=payload['prompt_content'],
            output_format=payload.get('output_format'),
            example_input=payload.get('example_input'),
            example_output=payload.get('example_output'),
            is_default=bool(payload.get('is_default', False)),
            status=payload.get('status') or 'draft',
            version=payload.get('version') or 'v1',
        )
        self.db.add(row)
        self.db.flush()
        if row.is_default:
            self._normalize_scene_default(row.scene_type, row.id)
        self.db.add(
            PromptTemplateVersionRecord(
                prompt_template_id=row.id,
                version=row.version,
                change_log='Initial version',
                prompt_content=row.prompt_content,
                output_format=row.output_format,
                status=row.status,
            )
        )
        self._add_audit_log(
            action='prompt_template.created',
            entity_type='prompt_template',
            entity_id=str(row.id),
            details={'template_key': row.template_key, 'scene_type': row.scene_type},
        )
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ValueError('template_key already exists.')
        return self.get_prompt_template(row.id)

    def update_prompt_template(self, template_id: int, payload: dict[str, Any]):
        row = self.db.get(PromptTemplateRecord, template_id)
        if not row:
            return None
        fields = [
            'name',
            'template_key',
            'scene_type',
            'description',
            'usage_notes',
            'prompt_content',
            'output_format',
            'example_input',
            'example_output',
            'status',
            'version',
        ]
        changed = False
        for field in fields:
            if field in payload and payload[field] is not None:
                if getattr(row, field) != payload[field]:
                    setattr(row, field, payload[field])
                    changed = True
        if payload.get('is_default') is not None:
            row.is_default = bool(payload['is_default'])
            if row.is_default:
                self._normalize_scene_default(row.scene_type, row.id)
            changed = True

        if changed:
            existing_version = self.db.execute(
                select(PromptTemplateVersionRecord).where(
                    PromptTemplateVersionRecord.prompt_template_id == row.id,
                    PromptTemplateVersionRecord.version == row.version,
                )
            ).scalar_one_or_none()
            if existing_version:
                existing_version.change_log = 'Updated template snapshot'
                existing_version.prompt_content = row.prompt_content
                existing_version.output_format = row.output_format
                existing_version.status = row.status
            else:
                self.db.add(
                    PromptTemplateVersionRecord(
                        prompt_template_id=row.id,
                        version=row.version,
                        change_log='Updated template snapshot',
                        prompt_content=row.prompt_content,
                        output_format=row.output_format,
                        status=row.status,
                    )
                )
            self._add_audit_log(
                action='prompt_template.updated',
                entity_type='prompt_template',
                entity_id=str(row.id),
                details=payload,
            )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            err_msg = str(getattr(exc, 'orig', exc)).lower()
            if 'template_key' in err_msg:
                raise ValueError('template_key already exists.')
            if 'uq_prompt_template_version' in err_msg or (
                'prompt_template_id' in err_msg and 'version' in err_msg
            ):
                raise ValueError(
                    'Version already exists for this template. Please use a new version.'
                )
            raise ValueError('Prompt template update failed due to a uniqueness conflict.')
        return self.get_prompt_template(row.id)

    def delete_prompt_template(self, template_id: int):
        row = self.db.get(PromptTemplateRecord, template_id)
        if not row:
            return False
        bindings = self.db.execute(
            select(ToolPromptBindingRecord).where(
                ToolPromptBindingRecord.prompt_template_id == row.id
            )
        ).scalars().all()
        for binding in bindings:
            self.db.delete(binding)
        self._add_audit_log(
            action='prompt_template.deleted',
            entity_type='prompt_template',
            entity_id=str(row.id),
            details={'template_key': row.template_key},
        )
        self.db.delete(row)
        self.db.commit()
        return True

    def set_default_prompt_template(self, template_id: int):
        row = self.db.get(PromptTemplateRecord, template_id)
        if not row:
            return None
        row.is_default = True
        row.status = 'active'
        self._normalize_scene_default(row.scene_type, row.id)
        self._add_audit_log(
            action='prompt_template.set_default',
            entity_type='prompt_template',
            entity_id=str(row.id),
            details={'scene_type': row.scene_type, 'template_key': row.template_key},
        )
        self.db.commit()
        return self.get_prompt_template(row.id)

    def preview_prompt_template(
        self,
        template_id: int,
        question: str = '',
        params: dict[str, Any] | None = None,
    ):
        row = self.db.get(PromptTemplateRecord, template_id)
        if not row:
            return None
        params = params or {}
        rendered = row.prompt_content
        for key, value in params.items():
            rendered = rendered.replace(f'{{{{{key}}}}}', str(value))
        final_prompt = (
            f'SCENE: {row.scene_type}\n'
            f'TEMPLATE: {row.template_key}\n'
            f'\n'
            f'{rendered}\n'
            f'\n'
            f'OUTPUT FORMAT:\n{row.output_format or ""}\n'
            f'\n'
            f'USER QUESTION:\n{question or "(empty)"}'
        )
        return to_jsonable(
            {
                'template_id': row.id,
                'template_key': row.template_key,
                'scene_type': row.scene_type,
                'rendered_prompt': final_prompt,
            }
        )

    def list_tool_prompt_bindings(self, tool_id: int):
        rows = self.db.execute(
            select(ToolPromptBindingRecord, PromptTemplateRecord)
            .join(
                PromptTemplateRecord,
                PromptTemplateRecord.id == ToolPromptBindingRecord.prompt_template_id,
            )
            .where(ToolPromptBindingRecord.tool_id == tool_id)
            .order_by(ToolPromptBindingRecord.scene_type.asc(), PromptTemplateRecord.name.asc())
        ).all()
        return to_jsonable(
            [
                {
                    'id': binding.id,
                    'tool_id': binding.tool_id,
                    'scene_type': binding.scene_type,
                    'prompt_template_id': binding.prompt_template_id,
                    'is_default': binding.is_default,
                    'created_at': binding.created_at,
                    'updated_at': binding.updated_at,
                    'template': {
                        'id': template.id,
                        'name': template.name,
                        'template_key': template.template_key,
                        'status': template.status,
                        'version': template.version,
                    },
                }
                for binding, template in rows
            ]
        )

    def _normalize_tool_scene_default(self, tool_id: int, scene_type: str, current_id: int):
        rows = self.db.execute(
            select(ToolPromptBindingRecord).where(
                ToolPromptBindingRecord.tool_id == tool_id,
                ToolPromptBindingRecord.scene_type == scene_type,
                ToolPromptBindingRecord.id != current_id,
                ToolPromptBindingRecord.is_default == True,
            )
        ).scalars().all()
        for row in rows:
            row.is_default = False

    def create_tool_prompt_binding(self, tool_id: int, payload: dict[str, Any]):
        tool = self.db.get(ToolDefinitionRecord, tool_id)
        if not tool:
            return None
        template = self.db.get(PromptTemplateRecord, payload['prompt_template_id'])
        if not template:
            raise ValueError('Prompt template not found.')
        scene_type = payload.get('scene_type') or template.scene_type
        row = ToolPromptBindingRecord(
            tool_id=tool.id,
            scene_type=scene_type,
            prompt_template_id=template.id,
            is_default=bool(payload.get('is_default', True)),
        )
        self.db.add(row)
        self.db.flush()
        if row.is_default:
            self._normalize_tool_scene_default(tool.id, row.scene_type, row.id)
        self._add_audit_log(
            action='tool_prompt_binding.created',
            entity_type='tool_prompt_binding',
            entity_id=str(row.id),
            details={'tool_id': tool.id, 'scene_type': row.scene_type},
        )
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ValueError('Binding already exists for same tool/scene/template.')
        return to_jsonable({'id': row.id})

    def update_tool_prompt_binding(
        self, tool_id: int, binding_id: int, payload: dict[str, Any]
    ):
        row = self.db.get(ToolPromptBindingRecord, binding_id)
        if not row or row.tool_id != tool_id:
            return None
        if payload.get('scene_type') is not None:
            row.scene_type = payload['scene_type']
        if payload.get('prompt_template_id') is not None:
            template = self.db.get(
                PromptTemplateRecord, payload['prompt_template_id']
            )
            if not template:
                raise ValueError('Prompt template not found.')
            row.prompt_template_id = template.id
        if payload.get('is_default') is not None:
            row.is_default = bool(payload['is_default'])
            if row.is_default:
                self._normalize_tool_scene_default(row.tool_id, row.scene_type, row.id)
        self._add_audit_log(
            action='tool_prompt_binding.updated',
            entity_type='tool_prompt_binding',
            entity_id=str(row.id),
            details=payload,
        )
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ValueError('Binding conflicts with existing binding.')
        return to_jsonable({'updated': True})

    def delete_tool_prompt_binding(self, tool_id: int, binding_id: int):
        row = self.db.get(ToolPromptBindingRecord, binding_id)
        if not row or row.tool_id != tool_id:
            return False
        self._add_audit_log(
            action='tool_prompt_binding.deleted',
            entity_type='tool_prompt_binding',
            entity_id=str(row.id),
            details={'tool_id': tool_id, 'scene_type': row.scene_type},
        )
        self.db.delete(row)
        self.db.commit()
        return True

    def resolve_prompt_template(
        self,
        scene_type: str | None = None,
        prompt_template_key: str | None = None,
        question: str | None = None,
    ):
        if prompt_template_key:
            row = self.db.execute(
                select(PromptTemplateRecord).where(
                    PromptTemplateRecord.template_key == prompt_template_key
                )
            ).scalar_one_or_none()
            if row:
                return row
        final_scene = scene_type or infer_scene_type(question)
        row = self.db.execute(
            select(PromptTemplateRecord).where(
                PromptTemplateRecord.scene_type == final_scene,
                PromptTemplateRecord.is_default == True,
                PromptTemplateRecord.status == 'active',
            )
        ).scalar_one_or_none()
        if row:
            return row
        return self.db.execute(
            select(PromptTemplateRecord)
            .where(PromptTemplateRecord.scene_type == final_scene)
            .order_by(PromptTemplateRecord.updated_at.desc())
        ).scalars().first()

    def search_suggestions(self, suggestion_type: str, keyword: str, limit: int = 20):
        key = (keyword or '').strip()
        like_q = f'%{key}%'
        result: list[dict[str, Any]] = []
        if suggestion_type == 'asset':
            stmt = select(Asset).order_by(Asset.qualified_name.asc()).limit(limit)
            if key:
                stmt = (
                    select(Asset)
                    .where(Asset.qualified_name.like(like_q) | Asset.name.like(like_q))
                    .order_by(Asset.qualified_name.asc())
                    .limit(limit)
                )
            rows = self.db.execute(stmt).scalars().all()
            result = [
                {
                    'value': item.qualified_name,
                    'label': item.qualified_name,
                    'type': 'asset',
                    'id': item.id,
                }
                for item in rows
            ]
        elif suggestion_type == 'tool':
            stmt = select(ToolDefinitionRecord).order_by(ToolDefinitionRecord.name.asc()).limit(limit)
            if key:
                stmt = (
                    select(ToolDefinitionRecord)
                    .where(ToolDefinitionRecord.name.like(like_q))
                    .order_by(ToolDefinitionRecord.name.asc())
                    .limit(limit)
                )
            rows = self.db.execute(stmt).scalars().all()
            result = [
                {'value': item.name, 'label': item.display_name or item.name, 'type': 'tool', 'id': item.id}
                for item in rows
            ]
        elif suggestion_type == 'prompt_template':
            stmt = select(PromptTemplateRecord).order_by(PromptTemplateRecord.updated_at.desc()).limit(limit)
            if key:
                stmt = (
                    select(PromptTemplateRecord)
                    .where(
                        PromptTemplateRecord.name.like(like_q)
                        | PromptTemplateRecord.template_key.like(like_q)
                    )
                    .order_by(PromptTemplateRecord.updated_at.desc())
                    .limit(limit)
                )
            rows = self.db.execute(stmt).scalars().all()
            result = [
                {
                    'value': item.template_key,
                    'label': f'{item.name} ({item.scene_type})',
                    'type': 'prompt_template',
                    'id': item.id,
                    'scene_type': item.scene_type,
                }
                for item in rows
            ]
        elif suggestion_type == 'data_source':
            stmt = select(DataSourceRecord).order_by(DataSourceRecord.name.asc()).limit(limit)
            if key:
                stmt = (
                    select(DataSourceRecord)
                    .where(DataSourceRecord.name.like(like_q))
                    .order_by(DataSourceRecord.name.asc())
                    .limit(limit)
                )
            rows = self.db.execute(stmt).scalars().all()
            result = [
                {
                    'value': item.name,
                    'label': f'{item.name} ({item.source_type})',
                    'type': 'data_source',
                    'id': item.id,
                }
                for item in rows
            ]
        elif suggestion_type == 'data_source_table':
            stmt = (
                select(DataSourceTableRecord, DataSourceRecord)
                .join(
                    DataSourceRecord,
                    DataSourceRecord.id == DataSourceTableRecord.data_source_id,
                )
                .order_by(
                    DataSourceRecord.name.asc(),
                    DataSourceTableRecord.schema_name.asc(),
                    DataSourceTableRecord.table_name.asc(),
                )
                .limit(limit)
            )
            if key:
                stmt = (
                    select(DataSourceTableRecord, DataSourceRecord)
                    .join(
                        DataSourceRecord,
                        DataSourceRecord.id == DataSourceTableRecord.data_source_id,
                    )
                    .where(
                        DataSourceTableRecord.table_name.like(like_q)
                        | DataSourceTableRecord.schema_name.like(like_q)
                        | DataSourceRecord.name.like(like_q)
                    )
                    .order_by(
                        DataSourceRecord.name.asc(),
                        DataSourceTableRecord.schema_name.asc(),
                        DataSourceTableRecord.table_name.asc(),
                    )
                    .limit(limit)
                )
            rows = self.db.execute(stmt).all()
            result = [
                {
                    'value': str(table.id),
                    'label': (
                        f'{source.name}.{table.schema_name}.{table.table_name}'
                    ),
                    'type': 'data_source_table',
                    'id': table.id,
                    'data_source_id': table.data_source_id,
                }
                for table, source in rows
            ]
        elif suggestion_type == 'job':
            stmt = select(ScheduledJobRecord).order_by(ScheduledJobRecord.name.asc()).limit(limit)
            if key:
                stmt = (
                    select(ScheduledJobRecord)
                    .where(ScheduledJobRecord.name.like(like_q))
                    .order_by(ScheduledJobRecord.name.asc())
                    .limit(limit)
                )
            rows = self.db.execute(stmt).scalars().all()
            result = [
                {'value': item.name, 'label': f'{item.name} ({item.job_type})', 'type': 'job', 'id': item.id}
                for item in rows
            ]
        elif suggestion_type == 'channel':
            stmt = select(ChannelRecord).order_by(ChannelRecord.channel_name.asc()).limit(limit)
            if key:
                stmt = (
                    select(ChannelRecord)
                    .where(ChannelRecord.channel_name.like(like_q) | ChannelRecord.channel_id.like(like_q))
                    .order_by(ChannelRecord.channel_name.asc())
                    .limit(limit)
                )
            rows = self.db.execute(stmt).scalars().all()
            result = [
                {
                    'value': item.channel_id,
                    'label': f'{item.channel_name} ({item.channel_type})',
                    'type': 'channel',
                    'id': item.id,
                }
                for item in rows
            ]
        elif suggestion_type == 'memory':
            stmt = select(MemoryRecord).order_by(MemoryRecord.updated_at.desc()).limit(limit)
            if key:
                stmt = (
                    select(MemoryRecord)
                    .where(MemoryRecord.title.like(like_q))
                    .order_by(MemoryRecord.updated_at.desc())
                    .limit(limit)
                )
            rows = self.db.execute(stmt).scalars().all()
            result = [
                {
                    'value': item.title,
                    'label': f'{item.title} ({item.memory_type})',
                    'type': 'memory',
                    'id': item.id,
                }
                for item in rows
            ]
        elif suggestion_type == 'chat_session':
            stmt = select(ChatSessionRecord).order_by(ChatSessionRecord.updated_at.desc()).limit(limit)
            if key:
                stmt = (
                    select(ChatSessionRecord)
                    .where(ChatSessionRecord.session_key.like(like_q) | ChatSessionRecord.title.like(like_q))
                    .order_by(ChatSessionRecord.updated_at.desc())
                    .limit(limit)
                )
            rows = self.db.execute(stmt).scalars().all()
            result = [
                {
                    'value': item.session_key,
                    'label': item.title or item.session_key,
                    'type': 'chat_session',
                    'id': item.id,
                }
                for item in rows
            ]

        return to_jsonable({'type': suggestion_type, 'items': result})

    def record_chat_exchange(
        self,
        question: str,
        answer: str,
        tool_trace: list[dict[str, Any]],
        session_key: str | None = None,
        channel_external_id: str | None = None,
        duration_ms: int | None = None,
        scene_type: str | None = None,
        prompt_template_key: str | None = None,
    ):
        session = None
        if session_key:
            session = self.db.execute(
                select(ChatSessionRecord).where(
                    ChatSessionRecord.session_key == session_key
                )
            ).scalar_one_or_none()
        if not session:
            key = session_key or uuid.uuid4().hex[:16]
            channel_ref = None
            if channel_external_id:
                channel_ref = self.db.execute(
                    select(ChannelRecord).where(
                        ChannelRecord.channel_id == channel_external_id
                    )
                ).scalar_one_or_none()
            session = ChatSessionRecord(
                session_key=key,
                title=(question[:120] if question else 'Chat Session'),
                status='active',
                channel_id=(channel_ref.id if channel_ref else None),
                last_message_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            self.db.add(session)
            self.db.flush()

        max_order = self.db.scalar(
            select(func.max(ChatMessageRecord.message_order)).where(
                ChatMessageRecord.chat_session_id == session.id
            )
        )
        next_order = int(max_order or 0) + 1
        user_message = ChatMessageRecord(
            chat_session_id=session.id,
            role='user',
            content=question or '',
            message_order=next_order,
            metadata_json={},
        )
        self.db.add(user_message)
        self.db.flush()
        next_order += 1

        assistant_message = ChatMessageRecord(
            chat_session_id=session.id,
            role='assistant',
            content=answer or '',
            message_order=next_order,
            metadata_json={
                'duration_ms': duration_ms,
                'scene_type': scene_type,
                'prompt_template_key': prompt_template_key,
            },
        )
        self.db.add(assistant_message)
        self.db.flush()
        next_order += 1

        for trace in tool_trace or []:
            tool_name = trace.get('tool') or 'unknown'
            args = trace.get('args') or {}
            result = trace.get('result')
            err = None
            if isinstance(result, dict) and result.get('error'):
                err = str(result.get('error'))
            self.db.add(
                ToolCallRecord(
                    chat_session_id=session.id,
                    chat_message_id=assistant_message.id,
                    tool_name=tool_name,
                    args_json=to_jsonable(args),
                    result_json=to_jsonable(result),
                    error_message=err,
                    duration_ms=None,
                )
            )
            self.db.add(
                ChatMessageRecord(
                    chat_session_id=session.id,
                    role='tool',
                    content=json.dumps(to_jsonable(result), ensure_ascii=False),
                    tool_name=tool_name,
                    message_order=next_order,
                    metadata_json={'args': to_jsonable(args)},
                )
            )
            next_order += 1

        session.last_message_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.commit()
        return session.session_key
