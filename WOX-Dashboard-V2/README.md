# WOX Dashboard V2 -> Agent Node Edition

This folder now runs as a Linux agent node.

## Features
- Flask API agent
- Token auth
- CPU / RAM / Disk status
- Allowed systemd service control
- Heartbeat to future master panel
- Debian venv installer

## Install
```bash
git clone https://github.com/andumc/WebDashboard.git
cd WebDashboard/WOX-Dashboard-V2
chmod +x scripts/install_debian.sh
./scripts/install_debian.sh
```

## API
- /api/health
- /api/status
- /api/services
- /api/services/<service>/<action>
- /api/master/ping
