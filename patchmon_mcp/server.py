"""
patchmon-mcp — FastMCP server wrapping the PatchMon REST API.

Tool surface:
  Integration API (Basic Auth — read-only):
    list_hosts, get_host, get_host_packages, get_host_stats,
    get_package_reports, get_agent_queue

  Admin API (JWT — patching):
    preview_patch_schedule, trigger_dry_run, trigger_patch,
    get_patch_run, list_patch_runs, approve_patch_run
"""

from __future__ import annotations

import time
from typing import Any, Optional

import structlog
from fastmcp import FastMCP

from .client import PatchMonClient, PatchMonError, get_client
from .observability import emit_metric

log = structlog.get_logger(__name__)

mcp = FastMCP(
    name="patchmon",
    instructions=(
        "PatchMon MCP server. Provides host inventory, pending package assessment, "
        "and the full dry-run → approve → execute patching workflow for forge hosts. "
        "Read tools use the Integration API (Basic Auth). Patch tools use the Admin API (JWT). "
        "Always run trigger_dry_run before trigger_patch for a specific package to preview "
        "what will change. Call approve_patch_run after reviewing the dry-run output."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tool_error(tool: str, err: Exception) -> dict:
    log.error("tool_error", tool=tool, error=str(err))
    return {"error": str(err)}


async def _timed_admin(
    client: PatchMonClient,
    method: str,
    path: str,
    **kwargs: Any,
):
    t0 = time.perf_counter()
    resp = await client.request_admin(method, path, **kwargs)
    return resp, time.perf_counter() - t0


async def _timed_integration(
    client: PatchMonClient,
    method: str,
    path: str,
    **kwargs: Any,
):
    t0 = time.perf_counter()
    resp = await client.request_integration(method, path, **kwargs)
    return resp, time.perf_counter() - t0


# ---------------------------------------------------------------------------
# Integration API tools  (read-only, Basic Auth)
# ---------------------------------------------------------------------------

@mcp.tool
async def list_hosts() -> dict:
    """List all enrolled hosts with update counts, reboot flag, and last check-in.

    Returns a list of hosts from the Integration API including pending update statistics.
    """
    client = get_client()
    try:
        resp, duration = await _timed_integration(client, "GET", "/hosts?include=stats")
        data = resp.json()
        hosts = data if isinstance(data, list) else data.get("hosts", data)
        total = len(hosts)
        online = sum(1 for h in hosts if h.get("status") == "online")
        reboot_req = sum(1 for h in hosts if h.get("needs_reboot") or h.get("NeedsReboot"))
        with_updates = sum(
            1 for h in hosts
            if (h.get("updates_available") or h.get("UpdatesAvailable") or 0) > 0
        )
        log.info("list_hosts", total=total, online=online, duration_s=round(duration, 3))
        await emit_metric(
            "patchmon_tool",
            {"tool": "list_hosts"},
            {
                "duration_s": duration,
                "total_hosts": total,
                "online_count": online,
                "reboot_required_count": reboot_req,
                "hosts_with_updates_count": with_updates,
            },
        )
        return {"hosts": hosts, "summary": {"total": total, "online": online,
                "reboot_required": reboot_req, "with_updates": with_updates}}
    except PatchMonError as e:
        return _tool_error("list_hosts", e)


@mcp.tool
async def get_host(host_id: str) -> dict:
    """Get full detail for a single host: OS, uptime, kernel, last check-in.

    Args:
        host_id: Host UUID from list_hosts.
    """
    client = get_client()
    try:
        resp, _ = await _timed_integration(client, "GET", f"/hosts/{host_id}/info")
        return resp.json()
    except PatchMonError as e:
        return _tool_error("get_host", e)


@mcp.tool
async def get_host_packages(host_id: str, pending_only: bool = True) -> dict:
    """Get package list for a host.

    Args:
        host_id: Host UUID from list_hosts.
        pending_only: If True (default), return only packages with pending updates.
    """
    client = get_client()
    try:
        path = f"/hosts/{host_id}/packages"
        if pending_only:
            path += "?update=true"
        resp, _ = await _timed_integration(client, "GET", path)
        data = resp.json()
        packages = data if isinstance(data, list) else data.get("packages", data)
        log.info("get_host_packages", host_id=host_id, count=len(packages), pending_only=pending_only)
        return {"host_id": host_id, "packages": packages, "count": len(packages)}
    except PatchMonError as e:
        return _tool_error("get_host_packages", e)


@mcp.tool
async def get_host_stats(host_id: str) -> dict:
    """Get package/repository statistics for a host.

    Args:
        host_id: Host UUID from list_hosts.
    """
    client = get_client()
    try:
        resp, _ = await _timed_integration(client, "GET", f"/hosts/{host_id}/stats")
        return resp.json()
    except PatchMonError as e:
        return _tool_error("get_host_stats", e)


@mcp.tool
async def get_package_reports(host_id: str, limit: int = 20) -> dict:
    """Get patch history (package reports) for a host from the Integration API.

    Args:
        host_id: Host UUID from list_hosts.
        limit: Maximum number of reports to return (default 20).
    """
    client = get_client()
    try:
        resp, _ = await _timed_integration(
            client, "GET", f"/hosts/{host_id}/package_reports?limit={limit}"
        )
        data = resp.json()
        reports = data if isinstance(data, list) else data.get("reports", data)
        return {"host_id": host_id, "reports": reports}
    except PatchMonError as e:
        return _tool_error("get_package_reports", e)


@mcp.tool
async def get_agent_queue(host_id: str) -> dict:
    """Get the current agent job queue for a host.

    Shows pending and in-progress jobs queued for the PatchMon agent on this host.

    Args:
        host_id: Host UUID from list_hosts.
    """
    client = get_client()
    try:
        resp, _ = await _timed_integration(client, "GET", f"/hosts/{host_id}/agent_queue")
        return resp.json()
    except PatchMonError as e:
        return _tool_error("get_agent_queue", e)


# ---------------------------------------------------------------------------
# Admin API tools  (JWT auth — patching)
# ---------------------------------------------------------------------------

@mcp.tool
async def preview_patch_schedule(host_id: str) -> dict:
    """Preview when the next patch run would be scheduled for a host.

    Returns scheduling info (delay type, policy name, scheduled time) without
    creating any runs. Use this to understand patch timing before triggering.

    Args:
        host_id: Host UUID (use the ID from the admin host list or list_hosts).
    """
    client = get_client()
    try:
        resp, _ = await _timed_admin(
            client, "GET", f"/patching/preview-run?host_id={host_id}"
        )
        return resp.json()
    except PatchMonError as e:
        return _tool_error("preview_patch_schedule", e)


@mcp.tool
async def trigger_dry_run(host_id: str, package_name: str) -> dict:
    """Start a dry-run for a specific package on a host.

    Runs 'apt-get -s install <package>' — simulates the upgrade without making
    changes. The run reaches 'validated' status when complete. Review shell_output,
    then call approve_patch_run with the returned run_id to execute for real.

    Args:
        host_id: Host UUID.
        package_name: Name of the apt package to dry-run (e.g. 'curl', 'nginx').
    """
    client = get_client()
    try:
        resp, duration = await _timed_admin(
            client,
            "POST",
            "/patching/trigger",
            json={
                "host_id": host_id,
                "patch_type": "patch_package",
                "package_name": package_name,
                "dry_run": True,
            },
        )
        data = resp.json()
        run_id = data.get("patch_run_id", "")
        log.info(
            "trigger_dry_run",
            host_id=host_id,
            package=package_name,
            run_id=run_id,
            duration_s=round(duration, 3),
        )
        await emit_metric(
            "patchmon_tool",
            {"tool": "trigger_dry_run"},
            {"duration_s": duration, "host_id": host_id, "run_id": run_id},
        )
        return data
    except PatchMonError as e:
        return _tool_error("trigger_dry_run", e)


@mcp.tool
async def trigger_patch(
    host_id: str,
    patch_type: str,
    package_name: Optional[str] = None,
) -> dict:
    """Trigger an actual patch run on a host. This makes real changes.

    For patch_all: upgrades all pending packages (apt-get upgrade).
    For patch_package: installs/upgrades a specific package.

    Prefer trigger_dry_run + approve_patch_run for patch_package to preview
    changes first. Use trigger_patch with patch_all when you're ready to apply
    all pending updates.

    Args:
        host_id: Host UUID.
        patch_type: 'patch_all' to upgrade all pending packages, or 'patch_package'
                    for a specific package.
        package_name: Required when patch_type is 'patch_package'.
    """
    if patch_type not in ("patch_all", "patch_package"):
        return {"error": "patch_type must be 'patch_all' or 'patch_package'"}
    if patch_type == "patch_package" and not package_name:
        return {"error": "package_name is required when patch_type is 'patch_package'"}

    client = get_client()
    try:
        body: dict[str, Any] = {"host_id": host_id, "patch_type": patch_type}
        if package_name:
            body["package_name"] = package_name

        resp, duration = await _timed_admin(client, "POST", "/patching/trigger", json=body)
        data = resp.json()
        run_id = data.get("patch_run_id", "")
        log.info(
            "trigger_patch",
            host_id=host_id,
            patch_type=patch_type,
            package=package_name,
            run_id=run_id,
            duration_s=round(duration, 3),
        )
        await emit_metric(
            "patchmon_tool",
            {"tool": "trigger_patch"},
            {
                "duration_s": duration,
                "host_id": host_id,
                "run_id": run_id,
                "patch_type": patch_type,
            },
        )
        return data
    except PatchMonError as e:
        return _tool_error("trigger_patch", e)


@mcp.tool
async def get_patch_run(run_id: str) -> dict:
    """Get the status and result of a patch run.

    Poll this after trigger_dry_run or trigger_patch to check progress.
    Status values: queued, running, completed, failed, validated, approved, pending_approval.

    The 'shell_output' field contains the full apt command output.
    The 'packages_affected' field lists packages that were actually changed (null for dry-runs).

    Args:
        run_id: Patch run UUID from trigger_dry_run, trigger_patch, or list_patch_runs.
    """
    client = get_client()
    try:
        resp, duration = await _timed_admin(client, "GET", f"/patching/runs/{run_id}")
        data = resp.json()
        status = data.get("status", "unknown")
        pkgs = data.get("packages_affected")
        log.info(
            "get_patch_run",
            run_id=run_id,
            status=status,
            packages_updated=len(pkgs) if pkgs else 0,
            duration_s=round(duration, 3),
        )
        await emit_metric(
            "patchmon_tool",
            {"tool": "get_patch_run", "status": status},
            {
                "duration_s": duration,
                "run_id": run_id,
                "host_id": data.get("host_id", ""),
                "packages_updated": len(pkgs) if pkgs else 0,
            },
        )
        return data
    except PatchMonError as e:
        return _tool_error("get_patch_run", e)


@mcp.tool
async def list_patch_runs(
    host_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """List patch run history with optional filtering.

    Args:
        host_id: Filter by host UUID (optional).
        status: Filter by status: queued, running, completed, failed,
                validated, approved, pending_approval (optional).
        limit: Max results to return (default 20).
        offset: Pagination offset (default 0).
    """
    client = get_client()
    try:
        params: list[str] = [f"limit={limit}", f"offset={offset}"]
        if host_id:
            params.append(f"host_id={host_id}")
        if status:
            params.append(f"status={status}")
        path = "/patching/runs?" + "&".join(params)
        resp, _ = await _timed_admin(client, "GET", path)
        return resp.json()
    except PatchMonError as e:
        return _tool_error("list_patch_runs", e)


@mcp.tool
async def approve_patch_run(run_id: str) -> dict:
    """Approve a dry-run ('validated') or policy-gated ('pending_approval') patch run.

    After approving a validated dry-run, a new real patch run is created and
    returned in the response as 'patch_run_id'. Use get_patch_run with the new
    run ID to track execution.

    Args:
        run_id: UUID of a run in 'validated' or 'pending_approval' status.
    """
    client = get_client()
    try:
        resp, duration = await _timed_admin(
            client, "POST", f"/patching/runs/{run_id}/approve", json={}
        )
        data = resp.json()
        new_run_id = data.get("patch_run_id", "")
        log.info(
            "approve_patch_run",
            validated_run_id=run_id,
            new_run_id=new_run_id,
            duration_s=round(duration, 3),
        )
        await emit_metric(
            "patchmon_tool",
            {"tool": "approve_patch_run"},
            {
                "duration_s": duration,
                "run_id": run_id,
                "new_run_id": new_run_id,
            },
        )
        return data
    except PatchMonError as e:
        return _tool_error("approve_patch_run", e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
