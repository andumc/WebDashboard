# -*- coding: utf-8 -*-
import os
import subprocess
import time
import re
import json
import shutil
import atexit

from flask import Flask, jsonify, request
from mcrcon import MCRcon

app = Flask(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SERVER_SCAN_ROOTS = [
    "E:/",
    "C:/Users/Administrator/Desktop/MC Server",
]

SERVER_LIST_FILE = os.path.join(SCRIPT_DIR, "servers.txt")

DEFAULT_INSTALLERS = [
    {
        "id": "paper",
        "source": "C:/Web/Management/installers/paper.jar",
        "target": "server.jar",
        "start_content": "java -Xms1G -Xmx4G -jar server.jar nogui\r\npause\r\n",
    }
]


def norm_path(path):
    return os.path.normcase(os.path.abspath(path))


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def sanitize_id(name):
    return re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-")


def read_properties(path):
    props = {}
    if not os.path.exists(path):
        return props

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                props[k] = v
    return props


def ensure_start_bat(folder):
    bat = os.path.join(folder, "start.bat")

    if os.path.exists(bat):
        return "start.bat"

    jar = next((f for f in os.listdir(folder) if f.endswith(".jar")), None)
    if not jar:
        return "start.bat"

    with open(bat, "w") as f:
        f.write(f"java -Xms1G -Xmx4G -jar {jar} nogui\npause\n")

    return "start.bat"


def is_server_folder(folder):
    try:
        files = os.listdir(folder)
    except:
        return False

    files = [f.lower() for f in files]

    return (
        "server.properties" in files
        or "velocity.toml" in files
        or any(f.endswith(".jar") for f in files)
    )


def discover_servers():
    servers = {}
    seen_paths = set()

    for root in SERVER_SCAN_ROOTS:
        if not os.path.isdir(root):
            continue

        for name in os.listdir(root):
            path = os.path.join(root, name)

            if not os.path.isdir(path):
                continue

            if not is_server_folder(path):
                continue

            norm = norm_path(path)
            if norm in seen_paths:
                continue

            seen_paths.add(norm)

            sid = sanitize_id(name)
            props = read_properties(os.path.join(path, "server.properties"))

            servers[sid] = {
                "name": name,
                "path": path,
                "start_bat": ensure_start_bat(path),
                "minecraft_port": int(props.get("server-port", 25565)),
                "rcon_port": int(props.get("rcon.port", 25575)),
                "rcon_password": props.get("rcon.password", "change-me"),
                "rcon_host": "127.0.0.1",
                "minecraft_host": "127.0.0.1",
            }

    return servers


def load_servers():
    # 🔥 ALWAYS rebuild → no duplicates EVER
    servers = discover_servers()
    write_json(SERVER_LIST_FILE, servers)
    return servers


@app.route("/servers")
def servers():
    return jsonify(load_servers())


@app.route("/add_server", methods=["POST"])
def add_server():
    data = request.json

    name = data.get("name")
    sid = sanitize_id(name)

    path = os.path.join("E:/", name)

    if os.path.exists(path):
        return jsonify(success=False, error="Path exists")

    os.makedirs(path)

    jar_src = DEFAULT_INSTALLERS[0]["source"]
    shutil.copy2(jar_src, os.path.join(path, "server.jar"))

    with open(os.path.join(path, "start.bat"), "w") as f:
        f.write(DEFAULT_INSTALLERS[0]["start_content"])

    return jsonify(success=True)


@app.route("/action/<sid>", methods=["POST"])
def action(sid):
    servers = load_servers()

    if sid not in servers:
        return jsonify(success=False)

    s = servers[sid]
    bat = os.path.join(s["path"], s["start_bat"])

    act = request.json.get("action")

    if act == "start":
        subprocess.Popen(f'cmd /c start "" "{bat}"', cwd=s["path"], shell=True)

    return jsonify(success=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8002)
