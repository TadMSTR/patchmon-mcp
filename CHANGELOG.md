# Changelog

## [Unreleased]

### Added

- Standard CI workflow (`ci.yml`) — ruff (pinned `ruff==0.16.0`) + pytest + pip-audit + build.
- Release workflow (`release.yml`) — a `vX.Y.Z` tag cuts a source-only GitHub Release.
- Explicit ruff config (`select = ["E", "F", "W", "I", "UP", "B", "SIM", "RUF"]`) pinning the
  enforced ruleset against ruff's widening defaults.

## [0.1.1] — 2026-05-27

### Fixed

- **Observability: stdout bug** — `configure_logging()` was falling back to
  `sys.stdout` when `LOG_FILE` was unset, injecting log lines into the MCP JSON-RPC
  stream. Now always writes to `sys.stderr`.
- **Observability: log directory creation** — added `os.makedirs` before `FileHandler`
  so the default log path `/opt/appdata/patchmon-mcp/logs/patchmon-mcp.log` is created
  at startup. Previously, startup would crash silently on first log write.
- **Observability: bare LOG_FILE guard** — added `if log_dir:` guard before `os.makedirs`
  to prevent `FileNotFoundError` when `LOG_FILE` is set to a bare filename.

### Changed

- `configure_logging()` now activates both stderr and file handlers simultaneously.
  File handler is added alongside stderr when `LOG_FILE` is set; stderr is always on.
- Default `LOG_FILE` path baked in: `/opt/appdata/patchmon-mcp/logs/patchmon-mcp.log`.
  Override with the `LOG_FILE` env var; omit to use the default.

## [0.1.0] — 2026-05-25

### Added

- Initial release — FastMCP Python MCP server wrapping PatchMon REST API
- Dual-auth HTTP client (`client.py`):
  - Integration API (`/api/v1/api/`): HTTP Basic Auth with TOKEN_KEY:TOKEN_SECRET
  - Admin API (`/api/v1/`): JWT session from `POST /api/v1/auth/login`
  - JWT cached in-process, auto-refreshed on 401 or within 30s of expiry
  - `PatchMonConfigError` for missing-credential failures (distinct from HTTP errors)
  - `trust_env=False` on httpx client — service is localhost-only, system proxy vars ignored
- 12 MCP tools via FastMCP:
  - Integration API (read-only): `list_hosts`, `get_host`, `get_host_packages`,
    `get_host_stats`, `get_package_reports`, `get_agent_queue`
  - Admin API (patching): `preview_patch_schedule`, `trigger_dry_run`, `trigger_patch`,
    `get_patch_run`, `list_patch_runs`, `approve_patch_run`
- Dry-run workflow: `trigger_dry_run` → `get_patch_run` (review shell_output) → `approve_patch_run`
- PM2 ecosystem config (`ecosystem.config.js`) — no hardcoded credentials; secrets via `--env-file`
- Structured JSON logging via structlog (always on)
- Optional telemetry: InfluxDB, OTEL, NATS (env-gated, off by default)
- Pydantic response models (`models.py`)
- Test suite: 8 tests covering JWT caching, 401 refresh, auth isolation, error propagation
