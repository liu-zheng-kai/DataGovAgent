from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AssetSummary(BaseModel):
    id: int
    name: str
    qualified_name: str
    asset_type: str
    system: str
    domain: str
    owner_team: Optional[str] = None


class AssetDetail(AssetSummary):
    description: Optional[str] = None
    refresh_frequency: Optional[str] = None
    runtime_status: Optional[str] = None
    runtime_delay_minutes: Optional[int] = None
    sla_expected_interval_minutes: Optional[int] = None
    sla_warning_after_minutes: Optional[int] = None
    sla_breach_after_minutes: Optional[int] = None


class DependencyEdge(BaseModel):
    upstream_asset: str
    downstream_asset: str
    dependency_type: str


class LineageResponse(BaseModel):
    root_asset: str
    direction: str
    nodes: list[AssetSummary] = Field(default_factory=list)
    edges: list[DependencyEdge] = Field(default_factory=list)


class FailedRunItem(BaseModel):
    asset: str
    domain: str
    status: str
    severity: str
    occurred_at: datetime
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class DomainHealthResponse(BaseModel):
    domain: str
    health_status: str
    observed_at: datetime
    reason: Optional[str] = None
    failed_runs_today: int


class BusinessImpactResponse(BaseModel):
    source_asset: str
    impacted_assets: list[dict[str, Any]] = Field(default_factory=list)
    impacted_teams: list[dict[str, Any]] = Field(default_factory=list)
    impacted_domains: list[dict[str, Any]] = Field(default_factory=list)


class SlaRiskItem(BaseModel):
    asset: str
    domain: str
    status: str
    delay_minutes: int
    warning_after_minutes: int
    breach_after_minutes: int


class DailySummaryResponse(BaseModel):
    report_date: date
    failed_jobs: list[FailedRunItem] = Field(default_factory=list)
    sla_risks: list[SlaRiskItem] = Field(default_factory=list)
    red_domains: list[dict[str, Any]] = Field(default_factory=list)
    high_impact_assets: list[dict[str, Any]] = Field(default_factory=list)


class ChatRequest(BaseModel):
    question: str
    oauth_access_token: Optional[str] = None
    session_id: Optional[str] = None
    channel_id: Optional[str] = None
    scene_type: Optional[str] = None
    prompt_template_key: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    tool_trace: list[dict[str, Any]] = Field(default_factory=list)
    session_id: Optional[str] = None
    scene_type: Optional[str] = None
    prompt_template_key: Optional[str] = None
