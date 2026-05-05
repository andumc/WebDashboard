# -*- coding: utf-8 -*-
import os
import subprocess
import time
import socket
import random
import string
import re
import json
import shutil
import atexit
from functools import wraps

from flask import Flask, jsonify, request, send_from_directory, send_file, abort
from mcrcon import MCRcon

app = Flask(__name__)

BASE_PATH = os.getenv("WOX_SERVER_BASE", r"C:\Users\Administrator\Desktop\MC Server")
SERVER_LIST_FILE = os.getenv("WOX_SERVER_LIST", "servers.txt")
INSTALLER_LIST_FILE = os.getenv("WOX_INSTALLER_LIST", "installers.txt")
PID_FILE = os.getenv("WOX_AGENT_PID", r"C:\Web\Agent\agent.pid")

CONSOLE_FILTERS = []
FILTERED_KEYS = []

DEFAULT_SERVERS = {}
DEFAULT_INSTALLERS = [
    {
        "id": "paper",
        "name": "Paper Minecraft Server",
        "source": r"C:\Web\Management\installers\paper.jar",
        "target": "server.jar",
        "start_bat": "start.bat",
        "start_content": "java -Xms1G -Xmx4G -jar server.jar nogui\r\npause\r\n",
    },
    {
        "id": "velocity",
        "name": "Velocity Proxy",
        "source": r"C:\Web\Management\installers\velocity.jar",
        "target": "server.jar",
        "start_bat": "start.bat",
        "start_content": "java -Xms512M -Xmx1G -jar server.jar\r\npause\r\n",
    },
]


def write_pid_file():
    try:
        os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass


def remove_pid_file():
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except Exception:
        pass


def read_json_txt(path, fallback):
    if not os.path.exists(path):
        write_json_txt(path, fallback)
        return fallback
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().strip()
        if not content:
            return fallback
        return json.loads(content)
    except Exception:
        return fallback


def write_json_txt(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_servers():
    servers = read_json_txt(SERVER_LIST_FILE, DEFAULT_SERVERS)
    for sid, server in servers.items():
        server.setdefault("remote", False)
        server.setdefault("minecraft_host", "127.0.0.1")
        server.setdefault("rcon_host", "127.0.0.1")
        server.setdefault("start_bat", "start.bat")
    return servers


def save_servers(servers):
    write_json_txt(SERVER_LIST_FILE, servers)


def load_installers():
    return read_json_txt(INSTALLER_LIST_FILE, DEFAULT_INSTALLERS)


def installer_by_id(installer_id):
    for installer in load_installers():
        if installer.get("id") == installer_id:
            return installer
    return None


def sanitize_server_id(value):
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    value = value.strip("-")
    return value


def get_config_path(server_id, server):
    if server_id == "proxy" or server.get("type") == "velocity":
        return os.path.join(server["path"], "velocity.toml")
    return os.path.join(server["path"], "server.properties")


def get_log_path(server):
    return os.path.join(server["path"], "logs", "latest.log")


def send_rcon_command(server, command):
    cmd = command.strip()
    if cmd.startswith("/"):
        cmd = cmd[1:]
    with MCRcon(
        server.get("rcon_host", "127.0.0.1"),
        server["rcon_password"],
        port=int(server["rcon_port"]),
    ) as mcr:
        return mcr.command(cmd)


def create_server_files(server):
    os.makedirs(server["path"], exist_ok=False)
    installer = installer_by_id(server.get("installer_id"))
    if installer:
        source = installer.get("source", "")
        target_name = installer.get("target", os.path.basename(source) or "server.jar")
        if source and os.path.isfile(source):
            shutil.copy2(source, os.path.join(server["path"], target_name))
        server["start_bat"] = installer.get("start_bat", server.get("start_bat", "start.bat"))
        if installer.get("start_content"):
            with open(os.path.join(server["path"], server["start_bat"]), "w", encoding="utf-8", newline="") as f:
                f.write(installer["start_content"])

    if server.get("type") != "velocity":
        props_path = os.path.join(server["path"], "server.properties")
        if not os.path.exists(props_path):
            with open(props_path, "w", encoding="utf-8") as f:
                f.write(
                    f"server-port={server['minecraft_port']}\n"
                    "enable-rcon=true\n"
                    f"rcon.port={server['rcon_port']}\n"
                    f"rcon.password={server['rcon_password']}\n"
                )
        eula_path = os.path.join(server["path"], "eula.txt")
        if not os.path.exists(eula_path):
            with open(eula_path, "w", encoding="utf-8") as f:
                f.write("eula=true\n")


@app.route("/servers")
def servers():
    return jsonify(load_servers())


@app.route("/installers")
def installers():
    return jsonify(load_installers())


@app.route("/add_server", methods=["POST"])
def add_server():
    data = request.get_json(silent=True) or {}
    server_id = sanitize_server_id(data.get("id") or data.get("name"))
    if not server_id:
        return jsonify(success=False, error="Server ID missing"), 400

    servers = load_servers()
    if server_id in servers:
        return jsonify(success=False, error="Server ID already exists"), 409

    server = {
        "name": (data.get("name") or server_id).strip(),
        "path": data.get("path") or os.path.join(BASE_PATH, data.get("name") or server_id),
        "start_bat": data.get("start_bat") or "start.bat",
        "rcon_port": int(data.get("rcon_port") or 25575),
        "rcon_password": data.get("rcon_password") or "change-me",
        "minecraft_port": int(data.get("minecraft_port") or 25565),
        "minecraft_host": data.get("minecraft_host") or "127.0.0.1",
        "rcon_host": data.get("rcon_host") or "127.0.0.1",
        "rcon_name": data.get("rcon_name") or server_id,
        "installer_id": data.get("installer_id") or "",
        "type": data.get("type") or "paper",
        "remote": False,
    }

    if os.path.exists(server["path"]):
        return jsonify(success=False, error="Path already exists"), 409

    try:
        create_server_files(server)
        servers[server_id] = server
        save_servers(servers)
        return jsonify(success=True, id=server_id, server=server)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route("/action/<server_id>", methods=["POST"])
def action(server_id):
    servers = load_servers()
    if server_id not in servers:
        return jsonify(success=False, error="Server not found"), 404

    server = servers[server_id]
    cmd = (request.json or {}).get("action", "")
    full_bat_path = os.path.join(server["path"], server.get("start_bat", "start.bat"))

    if cmd == "start":
        if not os.path.isfile(full_bat_path):
            return jsonify(success=False, error="start.bat not found"), 404
        subprocess.Popen(f'cmd.exe /c start "" "{full_bat_path}"', cwd=server["path"], shell=True)
        return jsonify(success=True)

    if cmd == "stop":
        try:
            send_rcon_command(server, "stop")
            time.sleep(4)
            return jsonify(success=True)
        except Exception as e:
            return jsonify(success=False, error=str(e))

    if cmd == "restart":
        try:
            send_rcon_command(server, "stop")
            time.sleep(4)
            if not os.path.isfile(full_bat_path):
                return jsonify(success=False, error="start.bat not found"), 404
            subprocess.Popen(f'cmd.exe /c start "" "{full_bat_path}"', cwd=server["path"], shell=True)
            return jsonify(success=True)
        except Exception as e:
            return jsonify(success=False, error=str(e))

    return jsonify(success=False, error="Unknown action"), 400


@app.route("/send/<server_id>", methods=["POST"])
def send_command(server_id):
    servers = load_servers()
    if server_id not in servers:
        return jsonify(success=False, error="Server not found"), 404

    cmd = (request.json or {}).get("cmd", "").strip()
    if not cmd:
        return jsonify(success=False, error="Empty command"), 400

    try:
        result = send_rcon_command(servers[server_id], cmd)
        return jsonify(success=True, response=result)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@app.route("/properties/<server_id>", methods=["GET", "POST"])
def properties(server_id):
    servers = load_servers()
    if server_id not in servers:
        return jsonify({"content": "Not found"}), 404

    server = servers[server_id]
    config_path = get_config_path(server_id, server)

    if request.method == "GET":
        if not os.path.exists(config_path):
            return jsonify({"content": "--- config file not found ---"})
        with open(config_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        if server_id == "proxy":
            content = "".join(lines)
        else:
            content = "".join(line for line in lines if not any(line.strip().startswith(key) for key in FILTERED_KEYS))
        return jsonify({"content": content})

    content = (request.json or {}).get("content", "")
    with open(config_path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(content)
    return jsonify({"success": True})


@app.route("/console/<server_id>")
def console(server_id):
    servers = load_servers()
    if server_id not in servers:
        return jsonify({"log": "Server not found"}), 404

    log_file = get_log_path(servers[server_id])
    if not os.path.exists(log_file):
        return jsonify({"log": "latest.log not found"})

    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    output = []
    for line in lines:
        if any(filter_text in line for filter_text in CONSOLE_FILTERS):
            continue
        output.append(re.sub(r"§.", "", line))
    return jsonify({"log": "".join(output)})


if __name__ == "__main__":
    write_pid_file()
    atexit.register(remove_pid_file)
    app.run(host="0.0.0.0", port=int(os.getenv("WOX_AGENT_PORT", "8002")), debug=False)
