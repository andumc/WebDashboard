# WebDashboard

WebDashboard is a self-hosted management panel for a private Minecraft network. It is designed to provide a central place for monitoring server status, controlling local and remote servers, browsing and editing files, and managing common operational tasks through a web interface.

The project is primarily focused on simplifying day-to-day network administration for a custom Minecraft setup, while keeping the workflow lightweight, practical, and tailored to a personal infrastructure environment.

## Important Note

The installer may not be working yet. If setup fails, please assume the installer is still unfinished and may require manual setup for now.

## Current Features

- Web-based login system with session token handling
- Dashboard view for monitoring multiple Minecraft servers
- Start, stop, and restart actions for local servers
- Support for remote agents to integrate and control servers on other machines
- RCON-based command execution for supported servers
- Console log viewing with optional filtering
- Server property and configuration file editing
- File browser with separate dashboard and server roots
- Direct file editing for common text-based formats
- File download support from the integrated browser
- Proxy aggregation for combined player counts across lobby servers
- Per-server detail pages for management and monitoring
- PID file handling for the web service process

## Planned Features

- Improved management page with dedicated start, stop, and restart controls
- RCON stability and reliability improvements
- Uptime tracking based on the first detected message in `latest.log`
- Route fixes for the editor and management pages
- Enhanced file browser selection handling
- ZIP creation and download support in the file browser
- Quick links from servers to their corresponding folders
- Integrated HTML editing improvements
- Better dashboard uptime display matching the management page
- Server administration tools for adding, editing, and removing managed servers
- A visual server settings editor inspired by panels such as Aternos
- Toggle-based controls for boolean `server.properties` values
- Dedicated inputs for MOTD, max player count, and other common server settings
- Dropdowns and validated fields for frequently edited configuration options
- Save workflows with cleaner editing UX for common server configuration tasks

## Project Goal

The goal of this project is to evolve into a more complete private control panel for Minecraft network operations, combining practical monitoring, server lifecycle management, configuration access, and file-level administration in a single self-hosted interface.
