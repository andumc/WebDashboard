# WebDashboard

> A self-hosted control panel for managing a private Minecraft network.

---

## Overview

WebDashboard is a lightweight management panel built for private Minecraft infrastructure. It provides a central place to monitor server status, control local and remote instances, browse and edit files, and handle common operational tasks through a clean web interface.

The project focuses on practical day-to-day administration while staying flexible, efficient, and tailored to custom network environments.

---

## Important Note

> The installer may not be fully functional yet.  
> If setup fails, manual installation may still be required.

---

## Current Features

### Server Management
- Dashboard for monitoring multiple Minecraft servers
- Start, stop, and restart controls for local servers
- Per-server detail pages for management and monitoring
- Proxy aggregation for combined player counts across lobby servers
- Support for remote agents on external machines

### Administration Tools
- Web-based login system with session token handling
- RCON command execution for supported servers
- Console log viewing with optional filtering
- PID file handling for the web service process

### File Management
- File browser with separate dashboard and server roots
- Direct editing for common text-based formats
- Configuration and `server.properties` editing
- Integrated file downloads

---

## Planned Features

### Core Improvements
- Improved management page with dedicated lifecycle controls
- Better dashboard uptime display matching management pages
- Route fixes for editor and management views
- RCON stability and reliability improvements

### File Browser Upgrades
- ZIP creation and download support
- Quick links from servers to matching folders
- Enhanced file browser selection handling
- Integrated HTML editing improvements

### Server Configuration Tools
- Add, edit, and remove managed servers from the panel
- Visual settings editor inspired by hosting panels such as Aternos
- Toggle controls for boolean `server.properties` values
- Dedicated inputs for MOTD, max player count, and common settings
- Dropdowns and validated fields for frequent configuration values
- Cleaner save workflows and editing UX

### Monitoring
- Uptime tracking based on the first detected message in `latest.log`

---

## Project Goal

The goal of WebDashboard is to become a complete private control panel for Minecraft network operations — combining monitoring, lifecycle management, configuration access, and file administration in one self-hosted platform.

---

## Status

Actively developed and evolving.
