module.exports = {
  apps: [
    {
      name: 'clariti-cycle-runner',
      script: './run_cycles.sh',
      interpreter: '/bin/bash',
      instances: 1,
      autorestart: true,
      watch: false,
      min_uptime: '10s',
      max_restarts: 50,
      restart_delay: 5000,
      env: {
        NODE_ENV: 'production'
      },
      error_file: './logs/pm2-cycle-error.log',
      out_file: './logs/pm2-cycle-out.log',
      log_file: './logs/pm2-cycle-combined.log',
      time: true,
      merge_logs: true
    }
  ]
};







