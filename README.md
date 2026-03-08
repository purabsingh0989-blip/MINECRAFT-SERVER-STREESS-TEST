# ⚡ MC-STRIKE v3 — Minecraft Server Stress Test Tool
### Bypass Edition | Full Protocol Compliance | 8 Attack Modes

> ⚠️ **FOR AUTHORIZED TESTING ONLY** — Only use on servers you own or have written permission to test.

---

## 📋 Table of Contents
1. [Requirements](#requirements)
2. [Files Overview](#files-overview)
3. [Installation](#installation)
4. [How to Run](#how-to-run)
5. [Dashboard Guide](#dashboard-guide)
6. [Attack Modes](#attack-modes)
7. [Bypass Techniques](#bypass-techniques)
8. [VPS Setup Guide](#vps-setup-guide-recommended)
9. [Troubleshooting](#troubleshooting)

---

## Requirements

### ✅ Zero external packages needed
MC-STRIKE uses **only Python built-in modules** — nothing to pip install.

### System Requirements
| Item | Minimum | Recommended |
|------|---------|-------------|
| Python | 3.8+ | 3.10+ |
| RAM | 512 MB | 2 GB+ |
| CPU | 2 cores | 4+ cores |
| OS | Windows / Linux / macOS | Ubuntu 22.04 LTS |
| Network | Any | 1 Gbps VPS |
| Open files limit | 1024 | 65535 (Linux) |

### Check your Python version
```bash
python3 --version
# Must show Python 3.8 or higher
```

---

## Files Overview

```
mc-strike-v3/
├── engine.py        ← Bot engine (all attack modes + bypass logic)
├── dashboard.py     ← Web dashboard server
├── requirements.txt ← This file (no packages needed)
└── README.md        ← This guide
```

---

## Installation

### Windows
```cmd
:: 1. Install Python from https://python.org (check "Add to PATH")
:: 2. Download mc-strike-v3 folder
:: 3. Open Command Prompt in the folder
:: 4. You're ready — no pip install needed
python --version
```

### Linux / Ubuntu (VPS or local)
```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install Python (usually already installed)
sudo apt install python3 -y

# 3. Check version
python3 --version

# 4. (Recommended) Increase open file limit for maximum bots
ulimit -n 65535

# 5. To make the file limit permanent on Ubuntu:
echo "* soft nofile 65535" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65535" | sudo tee -a /etc/security/limits.conf

# 6. You're ready — no pip install needed
```

### macOS
```bash
# 1. Install Python from https://python.org or via Homebrew
brew install python3

# 2. Check version
python3 --version

# 3. You're ready
```

---

## How to Run

### Option 1 — Web Dashboard (Recommended)
```bash
# Navigate to the mc-strike-v3 folder
cd mc-strike-v3

# Start the dashboard
python3 dashboard.py

# Then open your browser at:
# http://localhost:8080
```

**Custom port:**
```bash
python3 dashboard.py --port 9090
# Then open: http://localhost:9090
```

**Access from another device on same network:**
```bash
python3 dashboard.py
# Open: http://YOUR_MACHINE_IP:8080
# Example: http://192.168.1.50:8080
```

---

## Dashboard Guide

Once you open `http://localhost:8080`, here is how to use every section:

### 1. TARGET (left sidebar, top)
| Field | What to enter |
|-------|--------------|
| HOST / IP | Your Minecraft server IP or domain |
| PORT | Default: `25565` |
| MC VERSION | Match your server version (or leave Auto) |
| TIMEOUT | How long to wait per connection (default: 10s) |

→ Click **◈ PING SERVER** first to verify the server is reachable.

---

### 2. ATTACK MODE
Click one of the 8 mode cards to select it (explained below).

---

### 3. BOT CONFIG
| Field | Description |
|-------|-------------|
| TOTAL BOTS | Total number of bots to send (e.g. `500`) |
| CONCURRENT | How many bots run at the same time (e.g. `200`) |
| SPAWN DELAY | Seconds between each bot spawn (e.g. `0.03`) |
| JITTER | Random delay variation — makes timing look human |
| STAY DURATION | How long each bot stays connected (seconds) |
| NAME MODE | `Realistic` = human names, `Random` = gibberish, `Prefix` = your custom prefix |
| PREFIX | Only used if Name Mode is set to Prefix |

**Recommended settings for 29k player capacity test:**
```
Total Bots:    1000
Concurrent:    300
Spawn Delay:   0.02
Jitter:        0.01
Stay Duration: 300
Name Mode:     Realistic
```

---

### 4. BYPASS OPTIONS (toggles)
| Toggle | What it does |
|--------|-------------|
| Player Movement | Bots move around like real players (prevents AFK kick) |
| Chat Spam | Bots send random chat messages |
| Auto Respawn | Bots respawn after death instead of disconnecting |
| Play-phase Brand | Sends `minecraft:brand` again in play phase (GrimAC bypass) |
| Move Interval | How often bots move in seconds (0.5 = twice per second) |

---

### 5. FLOOD SETTINGS (for non-login modes)
| Field | Description |
|-------|-------------|
| FLOOD CYCLES | How many TCP connections per bot (TCP FLOOD mode) |
| PING CYCLES | How many pings per bot (PING STORM mode) |
| RECONNECT CYCLES | How many connect/disconnects per bot (RECONNECT mode) |
| RECONNECT DELAY | Pause between reconnects |

---

### 6. LAUNCH CONTROLS
- **▶ LAUNCH ATTACK** — Starts the stress test
- **■ STOP** — Stops sending new bots (active bots finish naturally)
- **↺ RESET** — Stops everything and clears all stats

---

### 7. Server Status Banner (top of right panel)
Shows **live server info** that auto-refreshes every 4 seconds:
- Online/Offline status
- Current player count (online / max)
- Server version
- Server latency
- MOTD (server description)
- List of online player names

---

### 8. Live Charts
Three real-time animated charts update every 0.8 seconds:
- **Active Bots** — how many bots are currently connected
- **Connections/sec** — connection rate over time
- **Avg Latency ms** — server response time over time

---

### 9. Performance Metrics
Live progress bars showing:
- Connection Rate % (successful TCP connections)
- Login Success Rate % (bots that completed login)
- Deployment Progress % (how many of total bots have been sent)

Plus detail stats: packets sent, data sent, avg latency, total attempts, login failures, uptime.

---

### 10. Error Breakdown
Table of the most common errors with frequency bars.
Common errors and what they mean:
| Error | Meaning |
|-------|---------|
| `ConnectionRefusedError` | Server offline or wrong port |
| `TimeoutError` | Server not responding / firewall |
| `Online mode: encryption required` | Server has online-mode=true (requires Mojang auth) |
| `Login disconnect` | Server kicked the bot (anti-bot plugin active) |
| `Connection reset` | Server or protection closed the connection |

---

## Attack Modes

| Mode | Best For | Protocol |
|------|----------|---------|
| **🛡️ FULL BYPASS** | Anti-bot testing, realistic players | Full 1.20.2+ login→config→play |
| **🔗 LOGIN & STAY** | Player capacity testing | Full login, simpler flow |
| **⚡ PACKET SPAM** | CPU stress on server | Login + flood packets |
| **🌊 TCP FLOOD** | Raw connection handler | TCP only, no login |
| **🐌 SLOW LORIS** | Connection pool exhaustion | Extremely slow byte-by-byte |
| **🔄 RECONNECT STORM** | Session management stress | Rapid connect/disconnect |
| **📡 PING STORM** | Status handler stress | Status protocol only |
| **🎲 HYBRID MIX** | Unpredictable combined load | Random mix per bot |

---

## Bypass Techniques

FULL BYPASS mode sends every packet a real Minecraft client sends:

| # | Technique | Why It Matters |
|---|-----------|---------------|
| 1 | Complete handshake | Wrong sequence = instant kick |
| 2 | Login Acknowledged (0x03) | Required for 1.20.2+ — without it server hangs then kicks |
| 3 | Config phase packets | 1.20.2+ has an entire config phase before play |
| 4 | Client Information packet | Anti-bot plugins (GrimAC, NoCheatPlus) check this |
| 5 | `minecraft:brand = vanilla` | Anti-bot plugins check for brand packet |
| 6 | Brand in play phase too | GrimAC checks again in play state |
| 7 | Keep-Alive responses | Responds to all keep-alive packet IDs — bots never time out |
| 8 | Teleport confirmation | Confirms server-sent teleports — bots don't get stuck |
| 9 | Realistic movement | Brownian motion walk — prevents AFK/no-movement kick |
| 10 | Auto respawn | Bots re-enter world after death |
| 11 | Randomized timing + jitter | Human-like delays — bypasses rate-based detection |
| 12 | Realistic usernames | `BraveDragon1438` style — harder to pattern-filter |
| 13 | Random UUIDs | Fresh offline-mode UUID per bot |

---

## VPS Setup Guide (Recommended)

Running bots from a VPS means they come from datacenter IPs — exactly how real attacks look. This is the best way to test protection like TCP Shield.

### Recommended VPS providers (cheapest options)
| Provider | Cost | Link |
|----------|------|------|
| Hetzner | ~€4/mo | hetzner.com |
| DigitalOcean | $4/mo | digitalocean.com |
| Vultr | $2.50/mo | vultr.com |
| Contabo | ~€5/mo | contabo.com |

### Setup on a fresh Ubuntu 22.04 VPS
```bash
# Step 1: Connect to your VPS
ssh root@YOUR_VPS_IP

# Step 2: Update system
apt update && apt upgrade -y

# Step 3: Install Python3
apt install python3 -y
python3 --version

# Step 4: Increase file descriptor limit (very important for high bot counts)
ulimit -n 65535

# Step 5: Upload mc-strike files to VPS
# From your local machine (not on VPS):
scp -r mc-strike-v3/ root@YOUR_VPS_IP:/root/

# Step 6: On the VPS, run the dashboard
cd /root/mc-strike-v3
python3 dashboard.py --port 8080

# Step 7: Access dashboard from your browser
# http://YOUR_VPS_IP:8080
```

### Running multiple VPS instances at once
```bash
# VPS 1 (location: Germany)
python3 dashboard.py --port 8080   # → http://VPS1_IP:8080

# VPS 2 (location: USA)
python3 dashboard.py --port 8080   # → http://VPS2_IP:8080

# VPS 3 (location: Singapore)
python3 dashboard.py --port 8080   # → http://VPS3_IP:8080

# Configure each dashboard to attack your server
# Combined bot count = VPS1 + VPS2 + VPS3 bots
```

### Keep dashboard running after you disconnect from VPS
```bash
# Install screen (keeps process alive after SSH disconnect)
apt install screen -y

# Start a screen session
screen -S mcstrike

# Run the dashboard inside screen
python3 dashboard.py

# Detach from screen (keeps running): Press Ctrl+A then D

# Reattach later
screen -r mcstrike

# Or use nohup:
nohup python3 dashboard.py > output.log 2>&1 &
```

---

## Troubleshooting

### "python3 not found"
```bash
# Linux
sudo apt install python3 -y

# Try alternative commands
python --version
py --version
```

### "Address already in use"
```bash
# Port 8080 is taken, use a different port
python3 dashboard.py --port 8090
```

### Bots connecting but getting kicked instantly
- Server has online-mode=true → bots can't log in (requires real Mojang accounts)
- Anti-bot plugin is blocking → use FULL BYPASS mode
- Server version mismatch → select correct MC version in dashboard

### Very high failure rate
```bash
# Linux: increase file descriptor limit first
ulimit -n 65535

# Then reduce concurrent bots to match your machine
# Start with Concurrent: 50 and increase gradually
```

### Dashboard loads but no stats update
- Make sure you clicked **▶ LAUNCH ATTACK**
- Check that host/port are correct
- Click **◈ PING SERVER** first to verify connectivity

### Bots all show "Login disconnect"
- Server's anti-bot plugin is working (that's what you're testing)
- Try switching to **FULL BYPASS** mode
- Check Error Breakdown section for specific kick reason

### Want more bots / higher load
```bash
# Linux only — increase system limits
ulimit -n 65535

# Increase concurrent bots in dashboard to 300-500
# Use multiple VPS machines simultaneously
# Set spawn delay to 0.01-0.02 for fastest spawning
```

---

## Quick Reference Card

```
START:        python3 dashboard.py
OPEN:         http://localhost:8080

BEST MODE:    Full Bypass  (most realistic, bypasses anti-bot)
FAST MODE:    TCP Flood    (maximum raw connections)
POOL MODE:    Slow Loris   (exhausts connection pool)

RECOMMENDED FOR 29K PLAYER TEST:
  Mode:       Full Bypass
  Total:      1000 bots
  Concurrent: 300
  Delay:      0.02s
  Stay:       300s
  Names:      Realistic
  Movement:   ON
  Respawn:    ON
```
