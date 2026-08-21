"""
Pydantic request/response models for the API layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConnectionBase(BaseModel):
    name: str
    platform: str
    connector_type: str
    status: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class ConnectionCreate(BaseModel):
    name: str
    platform: str
    connector_type: str
    config: dict[str, Any] = Field(default_factory=dict)


class ConnectionOut(ConnectionBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    last_run_at: datetime | None = None
    created_at: datetime


class AIAssetAccessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    principal_type: str
    principal_id: str | None = None
    principal_name: str | None = None
    display_name: str | None = None
    email: str | None = None
    access_type: str | None = None
    access_level: str | None = None
    license_sku: str | None = None
    source: str | None = None


class AIAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    connection_id: str | None = None
    name: str
    asset_type: str
    provider: str
    saas_platform: str
    ai_capability: str
    enabled: bool
    capability_status: str
    status: str
    purpose: str | None = None
    accessible_resources: list[str] = Field(default_factory=list)
    discovery_source: str | None = None
    monitoring_status: str
    review_status: str
    tenant_id: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    discovered_at: datetime
    last_seen_at: datetime | None = None
    access_count: int = 0
    interaction_count: int = 0
    simulated: bool = False


class AIAssetDetailOut(AIAssetOut):
    accesses: list[AIAssetAccessOut] = Field(default_factory=list)


class AIAssetReviewUpdate(BaseModel):
    review_status: str | None = None
    status: str | None = None
    monitoring_status: str | None = None
    purpose: str | None = None


class AIInteractionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    asset_id: str | None = None
    connection_id: str | None = None
    external_event_id: str | None = None
    user_email: str | None = None
    user_display_name: str | None = None
    principal_type: str | None = None
    saas_application: str | None = None
    ai_feature: str | None = None
    model: str | None = None
    model_available: bool
    timestamp: datetime
    request_info: str | None = None
    request_available: bool
    response_info: str | None = None
    response_available: bool
    token_usage: dict[str, Any] | None = None
    usage_available: bool
    source: str | None = None
    visibility_note: str | None = None
    simulated: bool = False


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    connection_id: str | None = None
    run_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    assets_found: int
    accesses_found: int
    interactions_found: int
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class DashboardStats(BaseModel):
    total_assets: int
    enabled_assets: int
    total_accesses: int
    unique_users_exposed: int
    total_interactions: int
    monitoring_limited: int
    connections: int
    simulated_evidence: bool
    recent_runs: list[RunOut] = Field(default_factory=list)
    visibility_summary: dict[str, int] = Field(default_factory=dict)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class Message(BaseModel):
    message: str
