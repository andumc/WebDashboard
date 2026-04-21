@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ==========================================
REM main_installer.bat
REM - Checks for Python
REM - Tries to install Python via winget if missing
REM - Generates main_ui_launcher.py
REM ==========================================

echo.
echo [1/4] Checking for Python...
set "PYTHON_CMD="

where py >nul 2>nul
if %errorlevel%==0 set "PYTHON_CMD=py"

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if %errorlevel%==0 set "PYTHON_CMD=python"
)

if defined PYTHON_CMD (
    echo Found Python launcher: %PYTHON_CMD%
    goto :write_ui
)

echo Python not found.
echo.
echo [2/4] Trying to install Python via winget...
where winget >nul 2>nul
if not %errorlevel%==0 (
    echo winget not available.
    echo Please install Python manually from https://www.python.org/downloads/
    pause
    exit /b 1
)

winget install -e --id Python.Python.3 --accept-source-agreements --accept-package-agreements
if not %errorlevel%==0 (
    echo Python installation failed.
    echo Please install Python manually from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo [3/4] Re-checking Python...
set "PYTHON_CMD="
where py >nul 2>nul
if %errorlevel%==0 set "PYTHON_CMD=py"
if not defined PYTHON_CMD (
    where python >nul 2>nul
    if %errorlevel%==0 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo Python still not found in PATH.
    echo A restart of the terminal or system may be required.
    pause
    exit /b 1
)

:write_ui
echo.
echo [4/4] Writing main_ui_launcher.py...

> main_ui_launcher.py (
    echo import json
    echo import os
    echo import subprocess
    echo import tkinter as tk
    echo from tkinter import filedialog, messagebox
    echo.
    echo CONFIG_FILE = "main_ui_config.json"
    echo DEFAULTS = {
    echo     "python_path": "py",
    echo     "script_path": "main.py",
    echo     "working_dir": os.getcwd(),
    echo     "args": ""
    echo }
    echo.
    echo def load_config():
    echo     if os.path.exists(CONFIG_FILE):
    echo         try:
    echo             with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    echo                 data = json.load(f)
    echo             merged = DEFAULTS.copy()
    echo             merged.update(data)
    echo             return merged
    echo         except Exception:
    echo             pass
    echo     return DEFAULTS.copy()
    echo.
    echo def save_config(data):
    echo     with open(CONFIG_FILE, "w", encoding="utf-8") as f:
    echo         json.dump(data, f, indent=2)
    echo.
    echo class App:
    echo     def __init__(self, root):
    echo         self.root = root
    echo         self.root.title("Main.py Launcher UI")
    echo         self.root.geometry("700x260")
    echo.
    echo         cfg = load_config()
    echo.
    echo         self.python_var = tk.StringVar(value=cfg["python_path"])
    echo         self.script_var = tk.StringVar(value=cfg["script_path"])
    echo         self.workdir_var = tk.StringVar(value=cfg["working_dir"])
    echo         self.args_var = tk.StringVar(value=cfg["args"])
    echo.
    echo         self.build_ui()
    echo.
    echo     def build_ui(self):
    echo         pad = {"padx": 8, "pady": 6}
    echo.
    echo         tk.Label(self.root, text="Python EXE / Launcher").grid(row=0, column=0, sticky="w", **pad)
    echo         tk.Entry(self.root, textvariable=self.python_var, width=65).grid(row=0, column=1, sticky="we", **pad)
    echo         tk.Button(self.root, text="Browse", command=self.pick_python).grid(row=0, column=2, **pad)
    echo.
    echo         tk.Label(self.root, text="Script Path").grid(row=1, column=0, sticky="w", **pad)
    echo         tk.Entry(self.root, textvariable=self.script_var, width=65).grid(row=1, column=1, sticky="we", **pad)
    echo         tk.Button(self.root, text="Browse", command=self.pick_script).grid(row=1, column=2, **pad)
    echo.
    echo         tk.Label(self.root, text="Working Directory").grid(row=2, column=0, sticky="w", **pad)
    echo         tk.Entry(self.root, textvariable=self.workdir_var, width=65).grid(row=2, column=1, sticky="we", **pad)
    echo         tk.Button(self.root, text="Browse", command=self.pick_workdir).grid(row=2, column=2, **pad)
    echo.
    echo         tk.Label(self.root, text="Extra Args").grid(row=3, column=0, sticky="w", **pad)
    echo         tk.Entry(self.root, textvariable=self.args_var, width=65).grid(row=3, column=1, sticky="we", **pad)
    echo.
    echo         btn_frame = tk.Frame(self.root)
    echo         btn_frame.grid(row=4, column=1, sticky="e", **pad)
    echo.
    echo         tk.Button(btn_frame, text="Save", width=14, command=self.on_save).pack(side="left", padx=5)
    echo         tk.Button(btn_frame, text="Run main.py", width=14, command=self.on_run).pack(side="left", padx=5)
    echo.
    echo         self.root.columnconfigure(1, weight=1)
    echo.
    echo     def pick_python(self):
    echo         path = filedialog.askopenfilename(title="Select python.exe")
    echo         if path:
    echo             self.python_var.set(path)
    echo.
    echo     def pick_script(self):
    echo         path = filedialog.askopenfilename(title="Select main.py", filetypes=[("Python files", "*.py"), ("All files", "*.*")])
    echo         if path:
    echo             self.script_var.set(path)
    echo.
    echo     def pick_workdir(self):
    echo         path = filedialog.askdirectory(title="Select Working Directory")
    echo         if path:
    echo             self.workdir_var.set(path)
    echo.
    echo     def get_data(self):
    echo         return {
    echo             "python_path": self.python_var.get().strip(),
    echo             "script_path": self.script_var.get().strip(),
    echo             "working_dir": self.workdir_var.get().strip(),
    echo             "args": self.args_var.get().strip(),
    echo         }
    echo.
    echo     def on_save(self):
    echo         data = self.get_data()
    echo         save_config(data)
    echo         messagebox.showinfo("Saved", "Configuration saved successfully.")
    echo.
    echo     def on_run(self):
    echo         data = self.get_data()
    echo         save_config(data)
    echo.
    echo         python_cmd = data["python_path"] or "py"
    echo         script = data["script_path"]
    echo         workdir = data["working_dir"] or os.getcwd()
    echo         extra_args = data["args"].split() if data["args"] else []
    echo.
    echo         if not os.path.exists(script):
    echo             messagebox.showerror("Error", f"Script not found:\n{script}")
    echo             return
    echo.
    echo         if not os.path.isdir(workdir):
    echo             messagebox.showerror("Error", f"Working directory not found:\n{workdir}")
    echo             return
    echo.
    echo         cmd = [python_cmd, script] + extra_args
    echo.
    echo         try:
    echo             subprocess.Popen(cmd, cwd=workdir)
    echo             messagebox.showinfo("Started", "main.py was started.")
    echo         except Exception as e:
    echo             messagebox.showerror("Launch failed", str(e))
    echo.
    echo if __name__ == "__main__":
    echo     root = tk.Tk()
    echo     App(root)
    echo     root.mainloop()
)

echo Done.
echo You can now run: %PYTHON_CMD% main_ui_launcher.py
echo.
pause
