// PM2 config for forge deployment.
// Start: pm2 start ecosystem.config.js --env-file ~/.secrets/forge.env
// Secrets (PATCHMON_ADMIN_USER, PATCHMON_ADMIN_PASSWORD, PATCHMON_TOKEN_KEY,
//          PATCHMON_TOKEN_SECRET) are injected via --env-file at deploy time.
// forge.env uses Windows line endings (\r\n) — pm2 --env-file handles this correctly.

module.exports = {
  apps: [
    {
      name: "patchmon-mcp",
      script: "python3",
      args: ["-m", "patchmon_mcp.server"],
      cwd: "/home/ted/repos/personal/patchmon-mcp",
      interpreter: "none",

      restart_delay: 5000,
      max_restarts: 10,
      min_uptime: "10s",

      out_file: "/home/ted/logs/patchmon-mcp.log",
      error_file: "/home/ted/logs/patchmon-mcp.log",
      merge_logs: true,
      time: true,

      env: {
        PATCHMON_ENDPOINT: "http://localhost:3005",
        LOG_LEVEL: "INFO",
        LOG_FILE: "/home/ted/logs/patchmon-mcp.log",
      },
      // PATCHMON_ADMIN_USER, PATCHMON_ADMIN_PASSWORD, PATCHMON_TOKEN_KEY,
      // PATCHMON_TOKEN_SECRET injected from ~/.secrets/forge.env via --env-file
    },
  ],
};
