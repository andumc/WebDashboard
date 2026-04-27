import json
import os
import platform
import socket
import subprocess
import time
from pathlib import Path

import psutil
import requests
from flask import Flask, jsonify, request, render_template

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config" / "agent.json"

app = Flask(__name__)
STARTED_AT = time.time()


def load_config():
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def cfg():
    return load_config()


def token_ok():
    config = cfg()
    expected = os.getenv("WOX_AGENT_TOKEN") or config.get("agent_token", "change-me")
    provided = request.headers.get("X-WOX-Token") or request.args.get("token")
    return bool(provided and provided == expected)


def require_token():
    if not token_ok():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    return None


def run_cmd(args, timeout=15):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def system_snapshot():
    disk = psutil.disk_usage("/")
    boot_time = psutil.boot_time()
    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "uptime_seconds": int(time.time() - boot_time),
        "agent_uptime_seconds": int(time.time() - STARTED_AT),
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "memory": {
            "total": psutil.virtual_memory().total,
            "used": psutil.virtual_memory().used,
            "percent": psutil.virtual_memory().percent,
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "percent": disk.percent,
        },
    }


def allowed_services():
    return cfg().get("allowed_services", [])


@app.route("/")
def index():
    return render_template("index.html", config=cfg())


@app.route("/api/health")
def health():
    return jsonify({"ok": True, "role": "agent", "node": cfg().get("node_name", socket.gethostname())})


@app.route("/api/status")
def status():
    auth = require_token()
    if auth:
        return auth
    return jsonify({"ok": True, "status": system_snapshot()})


@app.route("/api/services")
def services():
    auth = require_token()
    if auth:
        return auth
    output = []
    for service in allowed_services():
        cmd = run_cmd(["systemctl", "is-active", service])
        output.append({"name": service, "active": cmd["stdout"], "returncode": cmd["returncode"]})
    return jsonify({"ok": True, "services": output})


@app.route("/api/services/<service>/<action>", methods=["POST"])
def service_action(service, action):
    auth = require_token()
    if auth:
        return auth
    if service not in allowed_services():
        return jsonify({"ok": False, "error": "service_not_allowed"}), 403
    if action not in ["start", "stop", "restart", "status"]:
        return jsonify({"ok": False, "error": "action_not_allowed"}), 400
    cmd = ["systemctl", action, service] if action != "status" else ["systemctl", "status", service, "--no-pager"]
    return jsonify({"ok": True, "service": service, "action": action, "result": run_cmd(cmd, timeout=30)})


@app.route("/api/master/ping", methods=["POST"])
def ping_master():
    auth = require_token()
    if auth:
        return auth
    config = cfg()
    master_url = config.get("master_url", "").rstrip("/")
    if not master_url:
        return jsonify({"ok": False, "error": "master_url_not_configured"}), 400
    payload = {
        "node_name": config.get("node_name", socket.gethostname()),
        "role": "agent",
        "status": system_snapshot(),
    }
    try:
        response = requests.post(f"{master_url}/api/agents/heartbeat", json=payload, timeout=10)
        return jsonify({"ok": True, "master_status": response.status_code, "master_response": response.text[:500]})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502


if __name__ == "__main__":
    host = os.getenv("WOX_AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("WOX_AGENT_PORT", "8001"))
    app.run(host=host, port=port)
