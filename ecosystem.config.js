module.exports = {
  apps: [
    {
      name: 'clariti-python-api',
      script: './venv/bin/python3',
      args: '-m uvicorn src.api.service:app --host 0.0.0.0 --port 8000',
      instances: 1,
      autorestart: true,
      watch: false,
      // max_memory_restart removed - server has 30GB RAM, no need for restrictive limit
      min_uptime: '10s',        // Process must stay up for 10s before considering it stable
      max_restarts: 50,         // Allow up to 50 restarts (prevents infinite restart loops)
      restart_delay: 4000,      // Wait 4s before restarting
      exp_backoff_restart_delay: 100,  // Exponential backoff starting at 100ms
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: process.cwd()
      },
      error_file: './logs/pm2-error.log',
      out_file: './logs/pm2-out.log',
      log_file: './logs/pm2-combined.log',
      time: true,
      merge_logs: true
    }
  ]
};







