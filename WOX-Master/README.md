# WOX Master

Central panel for WOX agents.

## Default Network Layout
- Master: 192.168.178.40:8000
- Agent/Slave: 192.168.178.38:8001

## Install
```bash
cd WOX-Master
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Runs on port 8000.
