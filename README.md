# patchmon-mcp

> **Retired (2026-10-26).** This server is no longer deployed or maintained, and the repository
> is archived. Patching is done in the PatchMon UI. The code is left here for reference only;
> it will not receive fixes or dependency updates.

FastMCP Python MCP server wrapping the [PatchMon](https://patchmon.net) REST API.

Gives an AI agent structured access to apt patch management across PatchMon-enrolled hosts:
pending updates, dry-run validation, patch approval and execution, job history, and reboot state.

## Tool Reference

### Integration API tools (Basic Auth — read-only)

| Tool | Description |
|------|-------------|
| `list_hosts` | All enrolled hosts with update counts, reboot flag, last check-in |
| `get_host` | Full host detail: OS, uptime, kernel, last check-in |
| `get_host_packages` | Packages for a host (`pending_only=True` for updates only) |
| `get_host_stats` | Package/repository statistics |
| `get_package_reports` | Patch history from the Integration API |
| `get_agent_queue` | Current agent job queue status |

### Admin API tools (JWT — patching)

| Tool | Description |
|------|-------------|
| `preview_patch_schedule` | Preview when the next patch would run (scheduling info, no side effects) |
| `trigger_dry_run` | Dry-run for a specific package — simulates with `apt-get -s install`, status becomes `validated` |
| `trigger_patch` | Execute a real patch run (`patch_all` or `patch_package`) |
| `get_patch_run` | Status and result of any patch run; poll after triggering |
| `list_patch_runs` | Patch run history with optional `host_id`/`status` filtering |
| `approve_patch_run` | Approve a `validated` (dry-run) or `pending_approval` (policy-gated) run |

## Auth Architecture

PatchMon exposes two distinct APIs:

- **Integration API** (`/api/v1/api/`): HTTP Basic Auth with scoped credentials
  (`PATCHMON_TOKEN_KEY:PATCHMON_TOKEN_SECRET`). Read-only host and package data.

- **Admin API** (`/api/v1/`): JWT session token from `POST /api/v1/auth/login`.
  Full access including all patching operations. Admin credentials
  (`PATCHMON_ADMIN_USER` + `PATCHMON_ADMIN_PASSWORD`) required.

The MCP uses both: Integration API for read tools, Admin API JWT for patch tools.
JWT is cached in-process and refreshed automatically on 401 or approaching expiry.

## Dry-Run Workflow

For safe per-package patching, use the 3-step workflow:

```
1. trigger_dry_run(host_id, "curl")
   → run_id, status becomes "validated"

2. get_patch_run(run_id)
   → review shell_output (apt-get -s output), confirm the package change

3. approve_patch_run(run_id)
   → new_run_id returned; a real patch run is created and executed
   → get_patch_run(new_run_id) to track completion
```

For patching all pending updates: `trigger_patch(host_id, "patch_all")` directly.
`patch_all` does not support dry-run (`apt-get upgrade` preview requires `patch_package`).

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `PATCHMON_ENDPOINT` | yes | — | Base URL, e.g. `http://localhost:3005` |
| `PATCHMON_ADMIN_USER` | yes | — | Admin username for JWT login |
| `PATCHMON_ADMIN_PASSWORD` | yes | — | Admin password |
| `PATCHMON_TOKEN_KEY` | for read tools | — | Integration API credential key |
| `PATCHMON_TOKEN_SECRET` | for read tools | — | Integration API credential secret |
| `LOG_LEVEL` | no | `INFO` | structlog verbosity |
| `LOG_FILE` | no | — | Log to file path; stdout if unset |
| `INFLUXDB_URL` | no | — | Enables InfluxDB telemetry when set |
| `INFLUXDB_TOKEN` | no | — | InfluxDB auth token |
| `INFLUXDB_BUCKET` | no | `patchmon-mcp` | InfluxDB bucket name |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | no | — | Enables OTEL traces when set |
| `NATS_URL` | no | — | Enables NATS event publishing when set |
| `NATS_SUBJECT_PREFIX` | no | `patchmon` | NATS subject prefix |

## forge.env Line Endings

`~/.secrets/forge.env` uses Windows `\r\n` line endings. PM2's `--env-file` flag
(Go-based env parser) handles this correctly. Shell scripts that source forge.env
must strip CRs: `source <(tr -d '\r' < ~/.secrets/forge.env)`.

## Deployment (forge, PM2)

```bash
# Clone
cd ~/repos/personal
git clone <repo-url> patchmon-mcp

# Install
cd patchmon-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Start (secrets injected via --env-file)
pm2 start ecosystem.config.js --env-file ~/.secrets/forge.env
pm2 save
```

## Development

```bash
pip install -e ".[dev]"
pytest
pytest --cov=patchmon_mcp
```

## Observability

| Feature | Default | Enable with |
|---------|---------|-------------|
| Structured JSON logging | **ON** | `LOG_LEVEL`, `LOG_FILE` |
| InfluxDB telemetry | off | `INFLUXDB_URL` |
| OTEL traces | off | `OTEL_EXPORTER_OTLP_ENDPOINT` |
| NATS publishing | off | `NATS_URL` |
