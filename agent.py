# -*- coding: utf-8 -*-
import os
import re
import time
import socket
import subprocess
import threading
from functools import wraps

import psutil
from flask import Flask, jsonify, request
from mcrcon import MCRcon

app = Flask(__name__)

BASE_PATH = r"E:\\"
PUBLIC_IP = "192.168.178.38"
AGENT_PORT = 8002
ALLOWED_HOSTS = ["192.168.178.40", "192.168.178.26"]
AGENT_START_BAT = r"E:\Web Dashboard\agent\start_agent.bat"
AGENT_RESTART_DELAY_SECONDS = 2.0
EXCLUDED_NAMES = ["Web Dashboard", "forwarding secret.txt", "System Volume Information", "$RECYCLE.BIN"]
CONSOLE_FILTERS = ["[RCON", "issued server command:", "UUID of player", "Disconnecting"]
FILTERED_KEYS = ["enable-rcon", "broadcast-rcon", "rcon.password", "rcon.port", "online-mode", "server-port", "server-ip"]
MC_PORT_START = 25540
RCON_PORT_START = 25578
AUTO_RESTART_CRASHED_SERVERS = False
CRASH_RESTART_DELAY_SECONDS = 8
STATUS_REFRESH_SECONDS = 5
STATUS_CACHE = {}
LAST_START_ATTEMPT = {}
SERVER_META = {}
MANAGED_RUNNING = set()

def require_allowed_host(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.remote_addr not in ALLOWED_HOSTS:
            return "Unauthorized IP", 403
        return f(*args, **kwargs)
    return decorated

def normalize_id(name):
    return re.sub(r"[^a-zA-Z0-9_-]", "", name.lower())

def generate_password(name):
    return re.sub(r"\W+", "", name) or "Pass123"

def get_next_free_port(used_ports, start_port):
    port = start_port
    while port in used_ports:
        port += 1
    used_ports.add(port)
    return port

def is_port_open(host, port):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except:
        return False

def send_rcon(server, command):
    cmd = command.strip()
    if cmd.startswith("/"):
        cmd = cmd[1:]
    with MCRcon("127.0.0.1", server["rcon_password"], port=server["rcon_port"]) as mcr:
        return mcr.command(cmd)

def ensure_start_bat(folder_path, files):
    bat_path = os.path.join(folder_path, "start.bat")
    if os.path.exists(bat_path):
        return bat_path
    jar_file = None
    for f in files:
        if f.lower().endswith(".jar"):
            jar_file = f
            break
    if not jar_file:
        return None
    with open(bat_path, "w", encoding="utf-8", errors="ignore", newline="") as f:
        f.write(f'cd /d "{folder_path}"\r\n')
        f.write(f'java -Xms4G -Xmx4G -jar "{jar_file}" nogui\r\n')
    return bat_path

def read_prop_dict(prop_path):
    data = {}
    if not os.path.exists(prop_path):
        return data
    with open(prop_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            stripped = line.strip()
            if "=" in stripped and not stripped.startswith("#"):
                key, value = stripped.split("=", 1)
                data[key] = value
    return data

def write_prop_dict(prop_path, original_lines, values):
    existing_keys = set()
    new_lines = []
    for line in original_lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key, _ = stripped.split("=", 1)
            if key in values:
                new_lines.append(f"{key}={values[key]}\n")
                existing_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    for key, value in values.items():
        if key not in existing_keys:
            new_lines.append(f"{key}={value}\n")
    with open(prop_path, "w", encoding="utf-8", errors="ignore", newline="") as f:
        f.writelines(new_lines)

def ensure_server_properties(folder_path, folder_name, used_ports):
    prop_path = os.path.join(folder_path, "server.properties")
    original_lines = []
    if os.path.exists(prop_path):
        with open(prop_path, "r", encoding="utf-8", errors="ignore") as f:
            original_lines = f.readlines()
    values = read_prop_dict(prop_path)
    mc_port = values.get("server-port", "").strip()
    rcon_port = values.get("rcon.port", "").strip()
    rcon_password = values.get("rcon.password", "").strip()
    enable_rcon = values.get("enable-rcon", "").strip()
    if not mc_port.isdigit() or int(mc_port) in used_ports:
        mc_port = str(get_next_free_port(used_ports, MC_PORT_START))
    else:
        used_ports.add(int(mc_port))
    if not rcon_port.isdigit() or int(rcon_port) in used_ports:
        rcon_port = str(get_next_free_port(used_ports, RCON_PORT_START))
    else:
        used_ports.add(int(rcon_port))
    if not rcon_password:
        rcon_password = generate_password(folder_name)
    if enable_rcon.lower() != "true":
        enable_rcon = "true"
    write_prop_dict(prop_path, original_lines, {
        "server-port": mc_port,
        "rcon.port": rcon_port,
        "rcon.password": rcon_password,
        "enable-rcon": enable_rcon
    })
    return {
        "config_path": prop_path,
        "minecraft_port": int(mc_port),
        "rcon_port": int(rcon_port),
        "rcon_password": rcon_password
    }

def find_listening_pid(port):
    try:
        for conn in psutil.net_connections(kind="tcp"):
            if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                return conn.pid
    except:
        pass
    return None

def get_process_stats_by_pid(pid):
    if not pid:
        return None
    try:
        proc = psutil.Process(pid)
        cpu = proc.cpu_percent(interval=0.15)
        ram_mb = proc.memory_info().rss / (1024 * 1024)
        return {"pid": pid, "cpu_percent": round(cpu, 1), "ram_mb": round(ram_mb, 1)}
    except:
        return None

def get_log_path(server):
    return os.path.join(server["path"], "logs", "latest.log")

def read_console_text(server):
    log_file = get_log_path(server)
    if not os.path.exists(log_file):
        return "latest.log not found"
    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    output_lines = []
    for line in lines:
        if any(filter_text in line for filter_text in CONSOLE_FILTERS):
            continue
        clean = re.sub(r"§.", "", line)
        output_lines.append(clean)
    return "".join(output_lines)

def get_properties_content(server):
    config_path = os.path.join(server["path"], "server.properties")
    if not os.path.exists(config_path):
        return "--- config file not found ---"
    with open(config_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    filtered_lines = []
    for line in lines:
        if any(line.strip().startswith(key) for key in FILTERED_KEYS):
            continue
        filtered_lines.append(line)
    return "".join(filtered_lines)

def write_properties_content(server, content):
    config_path = os.path.join(server["path"], "server.properties")
    with open(config_path, "w", encoding="utf-8", errors="ignore", newline="") as f:
        f.write(content)

def find_servers():
    servers = {}
    used_ports = set()
    for entry in os.listdir(BASE_PATH):
        full_path = os.path.join(BASE_PATH, entry)
        if entry in EXCLUDED_NAMES:
            continue
        if not os.path.isdir(full_path):
            continue
        try:
            files = os.listdir(full_path)
        except PermissionError:
            continue
        bat_file = ensure_start_bat(full_path, files)
        if not bat_file:
            continue
        props = ensure_server_properties(full_path, entry, used_ports)
        server_id = normalize_id(entry)
        servers[server_id] = {
            "id": server_id,
            "name": entry,
            "path": full_path,
            "start_bat": os.path.basename(bat_file),
            "minecraft_port": props["minecraft_port"],
            "rcon_port": props["rcon_port"],
            "rcon_password": props["rcon_password"],
            "minecraft_host": PUBLIC_IP,
            "rcon_host": PUBLIC_IP
        }
    return servers

def start_server(server):
    full_bat_path = os.path.join(server["path"], server["start_bat"])
    subprocess.Popen(f'cmd.exe /c start "" "{full_bat_path}"', cwd=server["path"], shell=True)
    LAST_START_ATTEMPT[server["id"]] = time.time()
    MANAGED_RUNNING.add(server["id"])

def stop_tracking_server(server_id):
    MANAGED_RUNNING.discard(server_id)

def restart_agent_later():
    def worker():
        time.sleep(AGENT_RESTART_DELAY_SECONDS)
        bat_dir = os.path.dirname(AGENT_START_BAT)
        subprocess.Popen(f'cmd.exe /c start "" "{AGENT_START_BAT}"', cwd=bat_dir, shell=True)
        time.sleep(1)
        os._exit(0)
    threading.Thread(target=worker, daemon=True).start()

def refresh_status_loop():
    global STATUS_CACHE, SERVER_META
    while True:
        try:
            SERVER_META = find_servers()
            new_status = {}
            valid_ids = set(SERVER_META.keys())
            for sid in list(MANAGED_RUNNING):
                if sid not in valid_ids:
                    MANAGED_RUNNING.discard(sid)
            for server_id, server in SERVER_META.items():
                online = is_port_open("127.0.0.1", server["minecraft_port"])
                info = {
                    "name": server["name"],
                    "status": "online" if online else "offline",
                    "players": "N/A",
                    "max_players": "N/A",
                    "player_list": [],
                    "tps": "N/A",
                    "cpu_percent": "N/A",
                    "ram_mb": "N/A",
                    "pid": None
                }
                pid = find_listening_pid(server["minecraft_port"])
                stats = get_process_stats_by_pid(pid)
                if stats:
                    info["pid"] = stats["pid"]
                    info["cpu_percent"] = stats["cpu_percent"]
                    info["ram_mb"] = stats["ram_mb"]
                if online:
                    try:
                        player_list = send_rcon(server, "list")
                        if "There are" in player_list:
                            parts = player_list.split()
                            if len(parts) >= 6:
                                info["players"] = parts[2]
                                info["max_players"] = parts[5]
                            if ":" in player_list:
                                names = player_list.split(":", 1)[1].strip()
                                if names:
                                    info["player_list"] = [x.strip() for x in names.split(",") if x.strip()]
                        tps_raw = send_rcon(server, "tps")
                        tps_clean = re.sub(r"§.", "", tps_raw)
                        match = re.search(r"(\d+(\.\d+)?)", tps_clean)
                        if match:
                            info["tps"] = match.group(1)
                    except:
                        pass
                new_status[server_id] = info
            STATUS_CACHE = new_status
        except:
            pass
        time.sleep(STATUS_REFRESH_SECONDS)

@app.route("/servers", methods=["GET"])
@require_allowed_host
def get_servers():
    return jsonify(SERVER_META)

@app.route("/status", methods=["GET"])
@require_allowed_host
def get_status():
    return jsonify(STATUS_CACHE)

@app.route("/action/<server_id>", methods=["POST"])
@require_allowed_host
def action_server(server_id):
    server = SERVER_META.get(server_id)
    if not server:
        return "Server not found", 404
    cmd = request.json.get("action", "")
    if cmd == "start":
        try:
            start_server(server)
            return jsonify(success=True)
        except Exception as e:
            return jsonify(success=False, error=str(e)), 500
    if cmd == "stop":
        try:
            stop_tracking_server(server_id)
            send_rcon(server, "stop")
            return jsonify(success=True)
        except Exception as e:
            return jsonify(success=False, error=str(e)), 500
    if cmd == "restart":
        try:
            send_rcon(server, "stop")
            time.sleep(3)
            start_server(server)
            return jsonify(success=True)
        except Exception as e:
            return jsonify(success=False, error=str(e)), 500
    return jsonify(success=False, error="Unknown action"), 400

@app.route("/send/<server_id>", methods=["POST"])
@require_allowed_host
def send_command(server_id):
    server = SERVER_META.get(server_id)
    if not server:
        return "Server not found", 404
    cmd = request.json.get("cmd", "").strip()
    if not cmd:
        return jsonify(success=False, error="Empty command"), 400
    try:
        result = send_rcon(server, cmd)
        return jsonify(success=True, response=result)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route("/console/<server_id>", methods=["GET"])
@require_allowed_host
def console(server_id):
    server = SERVER_META.get(server_id)
    if not server:
        return jsonify(log="Server not found"), 404
    return jsonify(log=read_console_text(server))

@app.route("/properties/<server_id>", methods=["GET", "POST"])
@require_allowed_host
def properties(server_id):
    server = SERVER_META.get(server_id)
    if not server:
        return jsonify(content="Server not found"), 404
    if request.method == "GET":
        return jsonify(content=get_properties_content(server))
    content = request.json.get("content", "")
    write_properties_content(server, content)
    return jsonify(success=True)

@app.route("/restart-agent", methods=["POST"])
@require_allowed_host
def restart_agent():
    restart_agent_later()
    return jsonify(success=True)

if __name__ == "__main__":
    SERVER_META = find_servers()
    threading.Thread(target=refresh_status_loop, daemon=True).start()
    print(f"Agent running on {PUBLIC_IP}:{AGENT_PORT}")
    app.run(host="0.0.0.0", port=AGENT_PORT, debug=False)
