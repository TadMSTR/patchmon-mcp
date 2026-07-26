"""
Pydantic models for PatchMon API responses.
Field names confirmed from live Swagger and API probing on 2026-05-25.
"""

from __future__ import annotations

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Integration API models  (/api/v1/api/*)
# ---------------------------------------------------------------------------


class IntegrationHost(BaseModel):
    id: str
    hostname: str | None = None
    friendly_name: str | None = None
    ip: str | None = None
    os_type: str | None = None
    os_version: str | None = None
    architecture: str | None = None
    last_update: str | None = None
    status: str | None = None

    model_config = {"extra": "allow"}


class IntegrationHostInfo(BaseModel):
    id: str
    hostname: str | None = None
    friendly_name: str | None = None
    ip: str | None = None
    os_type: str | None = None
    os_version: str | None = None
    kernel_version: str | None = None
    system_uptime: str | None = None
    cpu_model: str | None = None
    ram_installed: str | None = None
    last_update: str | None = None
    status: str | None = None

    model_config = {"extra": "allow"}


class HostStats(BaseModel):
    id: str | None = None
    updates_available: int | None = None
    security_updates: int | None = None
    last_check: str | None = None

    model_config = {"extra": "allow"}


class Package(BaseModel):
    name: str | None = None
    current_version: str | None = None
    new_version: str | None = None
    arch: str | None = None
    description: str | None = None
    is_security: bool | None = None

    model_config = {"extra": "allow"}


class AgentQueueEntry(BaseModel):
    id: str | None = None
    action: str | None = None
    status: str | None = None
    created_at: str | None = None

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Admin API models  (/api/v1/*)
# ---------------------------------------------------------------------------


class PatchRunHosts(BaseModel):
    id: str | None = None
    hostname: str | None = None
    friendly_name: str | None = None
    last_update: str | None = None
    awaiting_post_patch_report_run_id: str | None = None

    model_config = {"extra": "allow"}


class PatchRun(BaseModel):
    id: str
    job_id: str | None = None
    host_id: str | None = None
    hosts: PatchRunHosts | None = None
    status: str | None = None
    dry_run: bool | None = None
    patch_type: str | None = None
    package_name: str | None = None
    packages_affected: list[str] | None = None
    shell_output: str | None = None
    error_message: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    approved_by_username: str | None = None
    triggered_by_username: str | None = None
    validation_run_id: str | None = None
    policy_id: str | None = None
    policy_name: str | None = None

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
    job_id: str | None = None
    message: str | None = None
    patch_run_id: str
    queued: bool | None = None
    run_at: str | None = None


class ApproveResponse(BaseModel):
    message: str | None = None
    patch_run_id: str
    run_at: str | None = None
    validation_run_id: str | None = None


class PreviewScheduleResponse(BaseModel):
    host_id: str | None = None
    host_name: str | None = None
    patch_delay_type: str | None = None
    policy_id: str | None = None
    policy_name: str | None = None
    run_at_iso: str | None = None

    model_config = {"extra": "allow"}
