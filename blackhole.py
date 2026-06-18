#!/usr/bin/env python3
"""
blackhole.py — Terminal Black Hole Break Enforcer
Tracks your ACTUAL keyboard/mouse activity (via pynput). Past 3 hrs of
real input nonstop → a black hole grows in your terminal and distorts
your code with gravitational lensing. Go idle 60+ sec → resting begins.
Rest 20+ min → it shrinks. No flags to fake — it watches real input.

Usage:
  python blackhole.py              # Start daemon + render loop (auto-detects idle)
  python blackhole.py --reset      # Hard reset work timer
  python blackhole.py --status     # Print current state and exit
  python blackhole.py --no-listen  # Fallback: manual mode, no pynput (always "working")

Install dependency (one-time, free):
  pip install pynput --break-system-packages
"""

import os, sys, time, math, random, json, argparse, signal, shutil, threading
from datetime import datetime
from pathlib import Path

try:
    from pynput import mouse, keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

IDLE_THRESHOLD_SEC = 60   # No input for this long = "resting" begins

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
WORK_THRESHOLD_HRS  = 3.0   # Black hole starts forming after this
MAX_GROW_HRS        = 6.0   # Full-size at this many hrs nonstop
REST_SHRINK_HRS     = 0.33  # ~20 min rest collapses it fully
STATE_FILE          = Path.home() / ".blackhole_state.json"
RENDER_INTERVAL_SEC = 2      # Redraw every N seconds
CANVAS_WIDTH        = 78
CANVAS_HEIGHT       = 22

# ──────────────────────────────────────────────
# ANSI HELPERS
# ──────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
CLEAR   = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

def rgb(r, g, b): return f"\033[38;2;{r};{g};{b}m"
def bg_rgb(r, g, b): return f"\033[48;2;{r};{g};{b}m"

BLACK_BG = bg_rgb(0, 0, 0)
DIM_CODE = rgb(100, 100, 140)
NORMAL_CODE = rgb(180, 180, 220)
HOT_CORE = rgb(255, 120, 20)
ACCRETION_MID = rgb(220, 60, 100)
ACCRETION_OUTER = rgb(140, 40, 200)

# ──────────────────────────────────────────────
# GLOBAL INPUT LISTENER — the actual idle detector
# ──────────────────────────────────────────────
class ActivityMonitor:
    """
    Runs keyboard + mouse listeners on background threads.
    Tracks `last_input_time`. Anything reading this from the main
    loop can compute idle_seconds = now - last_input_time.
    This is the piece that makes the tool unfakeable by the user —
    no flag to pass, it watches real input.
    """
    def __init__(self):
        self.last_input_time = time.time()
        self._lock = threading.Lock()
        self.active = False

    def _on_event(self, *args, **kwargs):
        with self._lock:
            self.last_input_time = time.time()

    def start(self):
        if not PYNPUT_AVAILABLE:
            return False
        try:
            self.kb_listener = keyboard.Listener(on_press=self._on_event)
            self.ms_listener = mouse.Listener(
                on_move=self._on_event, on_click=self._on_event, on_scroll=self._on_event
            )
            self.kb_listener.daemon = True
            self.ms_listener.daemon = True
            self.kb_listener.start()
            self.ms_listener.start()
            self.active = True
            return True
        except Exception as e:
            # Common on some Linux/Wayland setups or sandboxed envs without
            # input permissions — fall back gracefully to manual mode.
            sys.stderr.write(f"⚠️  Could not start input listener ({e}). "
                              f"Falling back to manual mode — pass --rest yourself.\n")
            self.active = False
            return False

    def idle_seconds(self):
        with self._lock:
            return time.time() - self.last_input_time

    def stop(self):
        if self.active:
            try:
                self.kb_listener.stop()
                self.ms_listener.stop()
            except Exception:
                pass

# ──────────────────────────────────────────────
# STATE PERSISTENCE
# ──────────────────────────────────────────────
def load_state():
    try:
        if STATE_FILE.exists():
            s = json.loads(STATE_FILE.read_text())
            return s
    except Exception:
        pass
    return {
        "session_start": time.time(),
        "work_seconds": 0,
        "rest_seconds": 0,
        "last_tick": time.time(),
        "resting": False,
        "peak_size": 0.0,
    }

def save_state(s):
    STATE_FILE.write_text(json.dumps(s, indent=2))

def reset_state():
    s = load_state()
    s["work_seconds"] = 0
    s["rest_seconds"] = s.get("rest_seconds", 0)
    s["resting"] = True
    s["last_tick"] = time.time()
    s["peak_size"] = 0.0
    save_state(s)
    print("✅  Work timer reset. Black hole collapsing. Go rest properly.")

# ──────────────────────────────────────────────
# PHYSICS — how big is the black hole?
# ──────────────────────────────────────────────
def compute_size(state):
    work_hrs = state["work_seconds"] / 3600
    rest_hrs = state["rest_seconds"] / 3600 if state["resting"] else 0

    # Growth: sigmoid past threshold
    excess = max(0, work_hrs - WORK_THRESHOLD_HRS)
    raw = excess / (MAX_GROW_HRS - WORK_THRESHOLD_HRS)
    raw = min(raw, 1.0)

    # Rest shrinks it (20 min full rest = full collapse)
    shrink = min(rest_hrs / REST_SHRINK_HRS, 1.0)
    size = raw * (1 - shrink)

    return max(0.0, min(1.0, size))

# ──────────────────────────────────────────────
# FAKE CODE BACKDROP — what gets "distorted"
# ──────────────────────────────────────────────
CODE_LINES = [
    "import { useState, useEffect } from 'react';           ",
    "import axios from 'axios';                              ",
    "                                                        ",
    "const API_URL = process.env.REACT_APP_API_URL;         ",
    "                                                        ",
    "async function fetchUserData(userId) {                  ",
    "  try {                                                 ",
    "    const resp = await axios.get(`${API_URL}/${userId}`);",
    "    return resp.data;                                   ",
    "  } catch (err) {                                       ",
    "    console.error('fetch failed:', err.message);        ",
    "    throw err;                                          ",
    "  }                                                     ",
    "}                                                       ",
    "                                                        ",
    "export default function Dashboard({ userId }) {         ",
    "  const [data, setData] = useState(null);              ",
    "  useEffect(() => {                                     ",
    "    fetchUserData(userId).then(setData);                ",
    "  }, [userId]);                                         ",
    "  return <div>{data ? data.name : 'Loading...'}</div>; ",
    "  // TODO: add error boundary and suspense             ",
]

GLITCH_CHARS = list("█▓▒░@#$%&*!?~^<>{}[]|∞≈≡∮∇⊗⊕ΨΩΔ")
ACCRETION_CHARS = list("·∘○◦●◉⊙*+")

def lerp_color(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))

# ──────────────────────────────────────────────
# RENDERER
# ──────────────────────────────────────────────
def render_frame(state, size, tick):
    W, H = CANVAS_WIDTH, CANVAS_HEIGHT
    cx, cy = W // 2, H // 2

    # Radii (in "screen units" — chars are ~2x taller than wide)
    bh_r   = size * 8          # event horizon (hard black)
    acc_r  = bh_r + 2 + size * 4   # accretion disk edge
    dist_r = acc_r + size * 12     # gravitational distortion field

    lines = []
    for y in range(H):
        row_chars = []
        src_line = CODE_LINES[y % len(CODE_LINES)]
        for x in range(W):
            # Aspect-correct distance (chars are ~0.5 aspect)
            dx = (x - cx) * 0.55
            dy = (y - cy)
            dist = math.sqrt(dx*dx + dy*dy)

            ch = src_line[x] if x < len(src_line) else ' '
            fg = NORMAL_CODE

            if size < 0.01:
                # No black hole — just show code normally
                pass
            elif dist < bh_r:
                # Event horizon — pure darkness
                ch = ' '
                fg = BLACK_BG + rgb(0, 0, 0)
            elif dist < acc_r:
                # Accretion disk — hot plasma
                t = (dist - bh_r) / max(acc_r - bh_r, 0.01)
                hot = lerp_color((255, 200, 20), (180, 20, 200), t)
                fg = rgb(*hot)
                idx = int((1 - t) * len(ACCRETION_CHARS))
                ch = ACCRETION_CHARS[min(idx, len(ACCRETION_CHARS)-1)]
                # Rotation animation
                angle = math.atan2(dy, dx) + tick * 0.3
                if abs(math.sin(angle * 3)) < 0.3:
                    ch = '~' if t < 0.5 else '·'
            elif dist < dist_r:
                # Gravitational lensing — code gets bent and glitched
                t = (dist - acc_r) / max(dist_r - acc_r, 0.01)
                glitch_prob = (1 - t) * size * 0.85

                if random.random() < glitch_prob:
                    # Full glitch
                    ch = random.choice(GLITCH_CHARS)
                    hue = random.randint(200, 280)
                    sat = random.randint(60, 100)
                    val = random.randint(100, 200)
                    # approximate HSV→RGB for purplish glitch
                    r = val if hue > 240 else int(val * sat / 100)
                    g = int(val * (1 - sat/100) * 0.5)
                    b = val if hue <= 240 else int(val * sat / 100)
                    fg = rgb(min(r,255), min(g,255), min(b,255))
                else:
                    # Gravitational lensing — sample displaced position
                    pull_strength = (1 - t) * size * 1.5
                    angle = math.atan2(dy, dx)
                    # Bend chars toward the hole
                    bent_x = int(x - math.cos(angle) * pull_strength * 2)
                    bent_y = int(y - math.sin(angle) * pull_strength * 1)
                    bent_x = max(0, min(W-1, bent_x))
                    bent_y = max(0, min(H-1, bent_y))
                    src = CODE_LINES[bent_y % len(CODE_LINES)]
                    ch = src[bent_x] if bent_x < len(src) else ' '
                    dim = int(lerp_color((180,180,220), (80,80,120), 1-t)[0])
                    fg = rgb(dim, dim, int(dim * 1.1))
            else:
                # Normal code zone
                fg = DIM_CODE

            row_chars.append(fg + ch + RESET)
        lines.append("".join(row_chars))
    return lines

# ──────────────────────────────────────────────
# HUD — status bar shown below the black hole
# ──────────────────────────────────────────────
def render_hud(state, size, idle_sec=None, listening=True):
    work_hrs = state["work_seconds"] / 3600
    rest_min = state["rest_seconds"] / 60 if state["resting"] else 0

    bar_width = 30
    filled = int(min(size, 1.0) * bar_width)
    bar = "█" * filled + "░" * (bar_width - filled)

    if size < 0.01:
        status_msg = f"{rgb(80,220,120)}✅  Working fine — {work_hrs:.1f}h / {WORK_THRESHOLD_HRS}h threshold{RESET}"
    elif size < 0.3:
        status_msg = f"{rgb(255,200,20)}🌀  Micro singularity — take a short break!{RESET}"
    elif size < 0.6:
        status_msg = f"{rgb(255,100,20)}⚠️   Black hole growing — your code warps!{RESET}"
    else:
        status_msg = f"{rgb(255,30,30)}{BOLD}☠️   CRITICAL MASS — TAKE A BREAK NOW{RESET}"

    resting_str = f"  💤 resting: {rest_min:.0f}m" if state.get("resting") else ""
    gravity_bar = f"  Gravity [{rgb(180,20,200)}{bar}{RESET}] {size*100:.0f}%"

    if listening and idle_sec is not None:
        sensor_line = f"  🖱️  idle: {idle_sec:.0f}s (auto-detected, no flags needed)"
    else:
        sensor_line = f"  ⚠️  manual mode — pynput unavailable, pass --rest yourself"

    lines = [
        "─" * CANVAS_WIDTH,
        status_msg,
        f"  Work: {work_hrs:.2f}h  |  {gravity_bar}{resting_str}",
        sensor_line,
        f"  Ctrl+C to pause • Run with --reset after a real break",
        "─" * CANVAS_WIDTH,
    ]
    return lines

# ──────────────────────────────────────────────
# TICK — update time counters
# ──────────────────────────────────────────────
def tick_state(state, is_resting=False):
    now = time.time()
    dt = now - state["last_tick"]
    state["last_tick"] = now

    if is_resting:
        state["rest_seconds"] = state.get("rest_seconds", 0) + dt
        state["resting"] = True
    else:
        state["work_seconds"] += dt
        # Reset rest counter when working
        if not state.get("resting", False):
            state["rest_seconds"] = 0
        state["resting"] = False

    return state

# ──────────────────────────────────────────────
# MAIN LOOP
# ──────────────────────────────────────────────
def main(args):
    if args.reset:
        reset_state(); return
    if args.status:
        s = load_state()
        sz = compute_size(s)
        print(f"Work: {s['work_seconds']/3600:.2f}h | Size: {sz*100:.1f}% | Resting: {s.get('resting')}")
        return

    state = load_state()
    tick_counter = 0

    # Start the real input listener unless explicitly disabled
    monitor = ActivityMonitor()
    listening = False
    if not args.no_listen:
        listening = monitor.start()
    if args.no_listen or not listening:
        sys.stderr.write("ℹ️  Running in manual mode — pass --rest yourself while on break.\n")
        time.sleep(1)

    def cleanup(sig=None, frame=None):
        monitor.stop()
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.write("\033[0m\n")
        save_state(state)
        print("\nBlack hole state saved. Run --reset after your break.")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    sys.stdout.write(HIDE_CURSOR)

    try:
        while True:
            if listening:
                idle_sec = monitor.idle_seconds()
                is_resting = idle_sec >= IDLE_THRESHOLD_SEC
            else:
                idle_sec = None
                is_resting = args.rest  # manual fallback

            state = tick_state(state, is_resting=is_resting)
            size = compute_size(state)

            # Only render if terminal is big enough
            cols, rows = shutil.get_terminal_size((80, 24))
            if cols < 60 or rows < 15:
                sys.stdout.write("\033[H")
                print("⚠️  Terminal too small. Resize to at least 60x15.")
                time.sleep(2)
                continue

            frame = render_frame(state, size, tick_counter)
            hud   = render_hud(state, size, idle_sec=idle_sec, listening=listening)

            # Move cursor to top, draw frame
            sys.stdout.write("\033[H")
            for line in frame:
                sys.stdout.write(line + "\n")
            for line in hud:
                sys.stdout.write(line + "\n")
            sys.stdout.flush()

            save_state(state)
            tick_counter += 1
            time.sleep(RENDER_INTERVAL_SEC)

    except Exception as e:
        cleanup()
        raise

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Terminal Black Hole Break Enforcer")
    p.add_argument("--reset", action="store_true", help="Reset work timer (you took a break)")
    p.add_argument("--rest",  action="store_true", help="Manual mode only: force resting state")
    p.add_argument("--status",action="store_true", help="Print current state and exit")
    p.add_argument("--no-listen", action="store_true", help="Disable pynput auto-detection, use manual --rest flag")
    main(p.parse_args())
