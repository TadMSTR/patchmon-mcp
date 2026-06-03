# patchmon-mcp

FastMCP server wrapping the PatchMon REST API for host inventory and OS patch lifecycle management.

## What it does

Provides read access to host inventory and patch status, and controlled write access to schedule and approve patch runs.

## Tools

Integration API (Basic Auth, read-only):
- `list_hosts` — All managed hosts.
- `get_host` — Single host details.
- `get_host_packages` — Package list for a host.
- `get_host_stats` — Patch statistics for a host.
- `get_package_reports` — Package-level patch reports.
- `get_agent_queue` — PatchMon agent queue status.

Admin API (JWT, patching operations):
- `preview_patch_schedule` — Preview what would be patched.
- `trigger_dry_run` — Run a dry-run patch simulation.
- `trigger_patch` — Execute a patch run.
- `get_patch_run` — Get details of a patch run by ID.
- `list_patch_runs` — List recent patch runs.
- `approve_patch_run` — Approve a pending patch run.

## Structure

```
patchmon_mcp/
  __init__.py
  server.py         FastMCP server — all tools
  client.py         PatchMonClient — async httpx wrapper, dual auth (Basic + JWT)
  models.py         Pydantic models for API responses
  observability.py  configure_logging(), emit_metric()
tests/              pytest with respx mocks
ecosystem.config.js PM2 config
pyproject.toml
```

## Configuration

| Env var                       | Purpose                                        |
|-------------------------------|------------------------------------------------|
| `PATCHMON_URL`                | PatchMon base URL (required)                   |
| `PATCHMON_INTEGRATION_USER`   | Basic Auth username for integration API        |
| `PATCHMON_INTEGRATION_PASS`   | Basic Auth password for integration API        |
| `PATCHMON_ADMIN_TOKEN`        | JWT for admin API (patching operations)        |
| `LOG_LEVEL`                   | Logging verbosity                              |
| `INFLUXDB_URL`                | InfluxDB endpoint for metrics (optional)       |

## Key architecture decisions

- **Always `trigger_dry_run` before `trigger_patch`** — the dry-run previews exactly which packages will be patched. Skip this only with explicit operator approval; unintended upgrades can break services.
- **Two auth modes** — the PatchMon integration API is read-only Basic Auth; the admin API uses JWT. `get_client()` returns a single client with both credential sets available. Tools that invoke admin endpoints use the JWT path automatically.

## Testing

```bash
pip install -e ".[dev]"
pytest
```

Tests use respx to mock httpx calls — no live PatchMon instance required.

## Git workflow

Branch before editing — do not commit directly to `main`.
