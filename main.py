# -*- coding: utf-8 -*-
import os
import atexit
import subprocess
import time
import socket
import random
import string
import re
from functools import wraps

import requests
from flask import (
    Flask,
    jsonify,
    request,
    render_template,
    redirect,
    url_for,
    make_response,
    send_from_directory,
    send_file,
    abort
)
from mcrcon import MCRcon

app = Flask(__name__, template_folder="HTMLs")

# ==========================================
# BASE CONFIG
# ==========================================
BASE_PATH = r"C:\Users\Administrator\Desktop\MC Server"

# ==========================================
# PID FILE CONFIG
# ==========================================
PID_FILE = r"C:\Web\Management\server.pid"

def write_pid_file():
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

def remove_pid_file():
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except:
        pass

# ==========================================
# REMOTE AGENTS
# ==========================================
REMOTE_AGENTS = [
    {
        "ip": "192.168.178.38",
        "port": 8002
    }
]

# ==========================================
# FILTERS
# ==========================================
CONSOLE_FILTERS = [
]

FILTERED_KEYS = [
]

EDITABLE_EXTENSIONS = [
    ".html", ".htm", ".css", ".js", ".json",
    ".py", ".toml", ".yml", ".yaml", ".properties", ".txt"
]

# ==========================================
# FILE BROWSER ROOTS
# ==========================================
FILE_BROWSER_ROOTS = {
    "dashboard": r"C:\Web\Management",
    "servers": r"C:\Users\Administrator\Desktop\MC Server"
}

# ==========================================
# USER / TOKEN CONFIG
# ==========================================
USER_FILE = "users.txt"
TOKENS = {}
TOKEN_TIMEOUT = 600

def load_users():
    users = {}
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if ":" not in line:
                    continue
                username, password = line.split(":", 1)
                users[username] = password
    return users

def generate_token(length=32):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("token")
        if not token or token not in TOKENS:
            return redirect(url_for("login"))
        if time.time() - TOKENS[token]["last_active"] > TOKEN_TIMEOUT:
            del TOKENS[token]
            return redirect(url_for("login"))
        TOKENS[token]["last_active"] = time.time()
        return f(*args, **kwargs)
    return decorated

# ==========================================
# LOCAL SERVER CONFIG
# ==========================================
LOCAL_SERVERS = {
    "proxy": {
        "name": "Proxy",
        "path": os.path.join(BASE_PATH, "Velocity"),
        "start_bat": "start.bat",
        "rcon_port": 25575,
        "rcon_password": "PROXY",
        "minecraft_port": 25565,
        "minecraft_host": "127.0.0.1",
        "rcon_host": "127.0.0.1",
        "remote": False
    },
    "lobby1": {
        "name": "Lobby 1",
        "path": os.path.join(BASE_PATH, "Lobby 1 Server"),
        "start_bat": "start.bat",
        "rcon_port": 25576,
        "rcon_password": "Lobby1",
        "minecraft_port": 25560,
        "minecraft_host": "127.0.0.1",
        "rcon_host": "127.0.0.1",
        "remote": False
    },
    "lobby2": {
        "name": "Lobby 2",
        "path": os.path.join(BASE_PATH, "Lobby 2 Server"),
        "start_bat": "start.bat",
        "rcon_port": 25577,
        "rcon_password": "Lobby2",
        "minecraft_port": 25561,
        "minecraft_host": "127.0.0.1",
        "rcon_host": "127.0.0.1",
        "remote": False
    }
}

# ==========================================
# HELPERS
# ==========================================
def safe_join(base, *paths):
    base = os.path.abspath(base)
    final_path = os.path.abspath(os.path.join(base, *paths))
    if not final_path.startswith(base):
        raise ValueError("Invalid path")
    return final_path

def get_all_servers():
    servers = dict(LOCAL_SERVERS)

    for agent in REMOTE_AGENTS:
        agent_base = f"http://{agent['ip']}:{agent['port']}"
        try:
            res = requests.get(f"{agent_base}/servers", timeout=4)
            if res.status_code != 200:
                continue

            remote_servers = res.json()
            for server_id, server in remote_servers.items():
                servers[server_id] = {
                    "name": server["name"],
                    "path": server["path"],
                    "start_bat": server.get("start_bat", "start.bat"),
                    "rcon_port": server["rcon_port"],
                    "rcon_password": server["rcon_password"],
                    "minecraft_port": server["minecraft_port"],
                    "minecraft_host": server.get("minecraft_host", agent["ip"]),
                    "rcon_host": server.get("rcon_host", agent["ip"]),
                    "remote": True,
                    "agent_ip": agent["ip"],
                    "agent_port": agent["port"]
                }
        except:
            pass

    return servers

def is_online(server):
    host = server.get("minecraft_host", "127.0.0.1")
    port = server.get("minecraft_port", 25565)
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except:
        return False

def get_config_path(server_id, server):
    if server_id == "proxy":
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
        port=server["rcon_port"]
    ) as mcr:
        return mcr.command(cmd)

# ==========================================
# FAVICON
# ==========================================
@app.route("/dashboard.ico")
def favicon():
    return send_from_directory(
        r"C:\Web\Management",
        "dashboard.ico",
        mimetype="image/vnd.microsoft.icon"
    )

# ==========================================
# LOGIN / LOGOUT
# ==========================================
@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        users = load_users()

        if username in users and users[username] == password:
            token = generate_token()
            TOKENS[token] = {
                "username": username,
                "last_active": time.time()
            }
            resp = make_response(redirect(url_for("dashboard")))
            resp.set_cookie("token", token)
            return resp

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html", error="")

@app.route("/logout")
def logout():
    token = request.cookies.get("token")
    if token in TOKENS:
        del TOKENS[token]

    resp = make_response(redirect(url_for("login")))
    resp.delete_cookie("token")
    return resp

# ==========================================
# DASHBOARD
# ==========================================
@app.route("/dashboard")
@token_required
def dashboard():
    return render_template("index.html", servers=get_all_servers())

# ==========================================
# SERVER PAGE
# ==========================================
@app.route("/server/<server_id>")
@token_required
def server_page(server_id):
    servers = get_all_servers()
    if server_id not in servers:
        return "Server not found", 404

    server = servers[server_id]
    return render_template("server.html", server=server, server_id=server_id)

# ==========================================
# ACTIONS
# ==========================================
@app.route("/action/<server_id>", methods=["POST"])
@token_required
def action(server_id):
    servers = get_all_servers()
    if server_id not in servers:
        return jsonify(success=False, error="Server not found"), 404

    server = servers[server_id]
    cmd = request.json.get("action", "")

    # Remote server action via agent
    if server.get("remote"):
        try:
            res = requests.post(
                f"http://{server['agent_ip']}:{server['agent_port']}/action/{server_id}",
                json={"action": cmd},
                timeout=5
            )
            if res.status_code == 200:
                return jsonify(res.json())
            return jsonify(success=False, error=res.text), res.status_code
        except Exception as e:
            return jsonify(success=False, error=str(e)), 500

    # Local server action
    full_bat_path = os.path.join(server["path"], server["start_bat"])

    if cmd == "start":
        if not os.path.isfile(full_bat_path):
            return jsonify(success=False, error="start.bat not found"), 404

        subprocess.Popen(
            f'cmd.exe /c start "" "{full_bat_path}"',
            cwd=server["path"],
            shell=True
        )
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

            subprocess.Popen(
                f'cmd.exe /c start "" "{full_bat_path}"',
                cwd=server["path"],
                shell=True
            )
            return jsonify(success=True)
        except Exception as e:
            return jsonify(success=False, error=str(e))

    return jsonify(success=False, error="Unknown action"), 400

# ==========================================
# SEND COMMAND
# ==========================================
@app.route("/send/<server_id>", methods=["POST"])
@token_required
def send_command(server_id):
    servers = get_all_servers()
    if server_id not in servers:
        return jsonify(success=False, error="Server not found"), 404

    server = servers[server_id]
    cmd = request.json.get("cmd", "").strip()
    if not cmd:
        return jsonify(success=False, error="Empty command"), 400

    if server.get("remote"):
        try:
            res = requests.post(
                f"http://{server['agent_ip']}:{server['agent_port']}/send/{server_id}",
                json={"cmd": cmd},
                timeout=5
            )
            if res.status_code == 200:
                return jsonify(res.json())
            return jsonify(success=False, error=res.text), res.status_code
        except Exception as e:
            return jsonify(success=False, error=str(e)), 500

    try:
        result = send_rcon_command(server, cmd)
        return jsonify(success=True, response=result)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

# ==========================================
# STATUS
# ==========================================
@app.route("/status")
@token_required
def status():
    servers = get_all_servers()
    data = {}
    total_players = 0
    total_max = 0

    for sid, server in servers.items():
        online = is_online(server)
        info = {
            "status": "online" if online else "offline",
            "players": "N/A",
            "max_players": "N/A",
            "tps": "N/A",
            "cpu_percent": "N/A",
            "ram_mb": "N/A",
            "player_list": []
        }

        if online and sid != "proxy":
            try:
                player_list = send_rcon_command(server, "list")
                if "There are" in player_list:
                    parts = player_list.split()
                    if len(parts) >= 6:
                        info["players"] = parts[2]
                        info["max_players"] = parts[5]
                        try:
                            total_players += int(parts[2])
                            total_max += int(parts[5])
                        except:
                            pass

                    if ":" in player_list:
                        names = player_list.split(":", 1)[1].strip()
                        if names:
                            info["player_list"] = [x.strip() for x in names.split(",") if x.strip()]

                tps_raw = send_rcon_command(server, "tps")
                tps_clean = re.sub(r"§.", "", tps_raw)
                match = re.search(r"(\d+(\.\d+)?)", tps_clean)
                if match:
                    info["tps"] = match.group(1)
            except:
                pass

        data[sid] = info

    if "proxy" in servers:
        proxy_online = is_online(servers["proxy"])
        data["proxy"] = {
            "status": "online" if proxy_online else "offline",
            "players": str(total_players),
            "max_players": str(total_max) if total_max > 0 else "N/A",
            "tps": "N/A",
            "cpu_percent": "N/A",
            "ram_mb": "N/A",
            "player_list": []
        }

    return jsonify(data)

# ==========================================
# PROPERTIES / CONFIG
# ==========================================
@app.route("/properties/<server_id>", methods=["GET", "POST"])
@token_required
def properties(server_id):
    servers = get_all_servers()
    if server_id not in servers:
        return jsonify({"content": "Not found"}), 404

    server = servers[server_id]

    if server.get("remote"):
        try:
            if request.method == "GET":
                res = requests.get(
                    f"http://{server['agent_ip']}:{server['agent_port']}/properties/{server_id}",
                    timeout=5
                )
            else:
                res = requests.post(
                    f"http://{server['agent_ip']}:{server['agent_port']}/properties/{server_id}",
                    json={"content": request.json.get("content", "")},
                    timeout=5
                )
            return jsonify(res.json()), res.status_code
        except Exception as e:
            return jsonify({"content": str(e)}), 500

    config_path = get_config_path(server_id, server)

    if request.method == "GET":
        if not os.path.exists(config_path):
            return jsonify({"content": "--- config file not found ---"})

        with open(config_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        if server_id == "proxy":
            content = "".join(lines)
        else:
            filtered_lines = []
            for line in lines:
                if any(line.strip().startswith(key) for key in FILTERED_KEYS):
                    continue
                filtered_lines.append(line)
            content = "".join(filtered_lines)

        return jsonify({"content": content})

    content = request.json.get("content", "")
    with open(config_path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(content)
    return jsonify({"success": True})

# ==========================================
# CONSOLE
# ==========================================
@app.route("/console/<server_id>")
@token_required
def console(server_id):
    servers = get_all_servers()
    if server_id not in servers:
        return jsonify({"log": "Server not found"}), 404

    server = servers[server_id]

    if server.get("remote"):
        try:
            res = requests.get(
                f"http://{server['agent_ip']}:{server['agent_port']}/console/{server_id}",
                timeout=5
            )
            return jsonify(res.json()), res.status_code
        except Exception as e:
            return jsonify({"log": str(e)}), 500

    log_file = get_log_path(server)

    if not os.path.exists(log_file):
        return jsonify({"log": "latest.log not found"})

    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    output_lines = []
    for line in lines:
        if any(filter_text in line for filter_text in CONSOLE_FILTERS):
            continue
        clean = re.sub(r"§.", "", line)
        output_lines.append(clean)

    return jsonify({"log": "".join(output_lines)})

# ==========================================
# FILE BROWSER ROOT PAGE
# ==========================================
@app.route("/files")
@token_required
def file_browser_root():
    return render_template("file_browser.html", roots=FILE_BROWSER_ROOTS)

# ==========================================
# FILE BROWSER
# ==========================================
@app.route("/files/<root_name>")
@app.route("/files/<root_name>/<path:subpath>")
@token_required
def file_browser(root_name, subpath=""):
    if root_name not in FILE_BROWSER_ROOTS:
        abort(404)

    base = FILE_BROWSER_ROOTS[root_name]

    try:
        current_path = safe_join(base, subpath)
    except ValueError:
        abort(403)

    if not os.path.exists(current_path):
        abort(404)

    if os.path.isfile(current_path):
        return send_file(current_path, as_attachment=False)

    items = []
    for name in sorted(
        os.listdir(current_path),
        key=lambda x: (not os.path.isdir(os.path.join(current_path, x)), x.lower())
    ):
        full = os.path.join(current_path, name)
        rel = os.path.relpath(full, base).replace("\\", "/")
        items.append({
            "name": name,
            "is_dir": os.path.isdir(full),
            "rel": rel
        })

    parent = None
    if os.path.abspath(current_path) != os.path.abspath(base):
        parent = os.path.relpath(os.path.dirname(current_path), base).replace("\\", "/")
        if parent == ".":
            parent = ""

    cur = os.path.relpath(current_path, base).replace("\\", "/")
    if cur == ".":
        cur = ""

    return render_template(
        "file_browser.html",
        items=items,
        parent=parent,
        cur=cur,
        root=root_name
    )

# ==========================================
# DOWNLOAD FILE
# ==========================================
@app.route("/download/<root_name>/<path:subpath>")
@token_required
def download_file(root_name, subpath):
    if root_name not in FILE_BROWSER_ROOTS:
        abort(404)

    base = FILE_BROWSER_ROOTS[root_name]
    try:
        full_path = safe_join(base, subpath)
    except ValueError:
        abort(403)

    if not os.path.isfile(full_path):
        abort(404)

    return send_file(full_path, as_attachment=True)

# ==========================================
# EDIT FILE
# ==========================================
@app.route("/edit/<root_name>/<path:subpath>")
@token_required
def edit_file(root_name, subpath):
    if root_name not in FILE_BROWSER_ROOTS:
        abort(404)

    base = FILE_BROWSER_ROOTS[root_name]
    try:
        full_path = safe_join(base, subpath)
    except ValueError:
        abort(403)

    if not os.path.isfile(full_path):
        abort(404)

    ext = os.path.splitext(full_path)[1].lower()
    if ext not in EDITABLE_EXTENSIONS:
        abort(403)

    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    return render_template(
        "file_editor.html",
        content=content,
        path=subpath,
        root=root_name
    )

# ==========================================
# SAVE FILE
# ==========================================
@app.route("/save/<root_name>/<path:subpath>", methods=["POST"])
@token_required
def save_file(root_name, subpath):
    if root_name not in FILE_BROWSER_ROOTS:
        abort(404)

    base = FILE_BROWSER_ROOTS[root_name]
    try:
        full_path = safe_join(base, subpath)
    except ValueError:
        abort(403)

    if not os.path.isfile(full_path):
        abort(404)

    ext = os.path.splitext(full_path)[1].lower()
    if ext not in EDITABLE_EXTENSIONS:
        abort(403)

    content = request.form.get("content", "")
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    content = content.replace("\n", "\r\n")

    with open(full_path, "w", encoding="utf-8", newline="") as f:
        f.write(content)

    return redirect(url_for("edit_file", root_name=root_name, subpath=subpath))

# ==========================================
# RUN
# ==========================================
if __name__ == "__main__":
    write_pid_file()
    atexit.register(remove_pid_file)
    app.run(host="0.0.0.0", port=8001, debug=False)
