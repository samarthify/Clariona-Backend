module.exports = {
  apps: [
    {
      name: 'clariti-streaming-pipeline',
      script: './venv/bin/python',
      args: '-m src.services.main',
      instances: 1,
      autorestart: true,
      watch: false,
      min_uptime: '10s',
      max_restarts: 50,
      restart_delay: 5000,
      max_memory_restart: '20G',
      env: {
        PYTHONPATH: '.',
        PYTHONUNBUFFERED: '1',
        NODE_ENV: 'production'
        // Note: spaCy is now disabled by default in topic_classifier.py
        // To enable spaCy (slow but more accurate): ENABLE_SPACY: '1'
      },
      error_file: './logs/pm2-pipeline-error.log',
      out_file: './logs/pm2-pipeline-out.log',
      log_file: './logs/pm2-pipeline-combined.log',
      time: true,
      merge_logs: true,
      kill_timeout: 10000
    }
  ]
};







