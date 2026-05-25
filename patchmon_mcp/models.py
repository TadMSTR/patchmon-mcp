"""
Pydantic models for PatchMon API responses.
Field names confirmed from live Swagger and API probing on 2026-05-25.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Integration API models  (/api/v1/api/*)
# ---------------------------------------------------------------------------

class IntegrationHost(BaseModel):
    id: str
    hostname: Optional[str] = None
    friendly_name: Optional[str] = None
    ip: Optional[str] = None
    os_type: Optional[str] = None
    os_version: Optional[str] = None
    architecture: Optional[str] = None
    last_update: Optional[str] = None
    status: Optional[str] = None

    model_config = {"extra": "allow"}


class IntegrationHostInfo(BaseModel):
    id: str
    hostname: Optional[str] = None
    friendly_name: Optional[str] = None
    ip: Optional[str] = None
    os_type: Optional[str] = None
    os_version: Optional[str] = None
    kernel_version: Optional[str] = None
    system_uptime: Optional[str] = None
    cpu_model: Optional[str] = None
    ram_installed: Optional[str] = None
    last_update: Optional[str] = None
    status: Optional[str] = None

    model_config = {"extra": "allow"}


class HostStats(BaseModel):
    id: Optional[str] = None
    updates_available: Optional[int] = None
    security_updates: Optional[int] = None
    last_check: Optional[str] = None

    model_config = {"extra": "allow"}


class Package(BaseModel):
    name: Optional[str] = None
    current_version: Optional[str] = None
    new_version: Optional[str] = None
    arch: Optional[str] = None
    description: Optional[str] = None
    is_security: Optional[bool] = None

    model_config = {"extra": "allow"}


class AgentQueueEntry(BaseModel):
    id: Optional[str] = None
    action: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Admin API models  (/api/v1/*)
# ---------------------------------------------------------------------------

class PatchRunHosts(BaseModel):
    id: Optional[str] = None
    hostname: Optional[str] = None
    friendly_name: Optional[str] = None
    last_update: Optional[str] = None
    awaiting_post_patch_report_run_id: Optional[str] = None

    model_config = {"extra": "allow"}


class PatchRun(BaseModel):
    id: str
    job_id: Optional[str] = None
    host_id: Optional[str] = None
    hosts: Optional[PatchRunHosts] = None
    status: Optional[str] = None
    dry_run: Optional[bool] = None
    patch_type: Optional[str] = None
    package_name: Optional[str] = None
    packages_affected: Optional[list[str]] = None
    shell_output: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    approved_by_username: Optional[str] = None
    triggered_by_username: Optional[str] = None
    validation_run_id: Optional[str] = None
    policy_id: Optional[str] = None
    policy_name: Optional[str] = None

    model_config = {"extra": "allow"}


class PatchRunPagination(BaseModel):
    limit: int
    offset: int
    pages: int
    total: int


class PatchRunList(BaseModel):
    pagination: PatchRunPagination
    runs: list[PatchRun]


class TriggerResponse(BaseModel):
    job_id: Optional[str] = None
    message: Optional[str] = None
    patch_run_id: str
    queued: Optional[bool] = None
    run_at: Optional[str] = None


class ApproveResponse(BaseModel):
    message: Optional[str] = None
    patch_run_id: str
    run_at: Optional[str] = None
    validation_run_id: Optional[str] = None


class PreviewScheduleResponse(BaseModel):
    host_id: Optional[str] = None
    host_name: Optional[str] = None
    patch_delay_type: Optional[str] = None
    policy_id: Optional[str] = None
    policy_name: Optional[str] = None
    run_at_iso: Optional[str] = None

    model_config = {"extra": "allow"}
