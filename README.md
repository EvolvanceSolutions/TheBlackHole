# TheBlackHole
I built a black hole that punishes workaholics — 
# ☠️ Terminal Black Hole — Break Enforcer

A Python daemon that renders a growing black hole in your terminal.
The longer you work nonstop, the bigger it gets — and the more it
warps and corrupts your code backdrop with real gravitational lensing math.

**v2: real idle detection.** No more flags to fake. It watches your
actual keyboard and mouse via `pynput`. Stop typing for 60+ seconds and
it starts counting as rest. No input at all = no excuse.

## Install (one dependency, still free)

```bash
pip install pynput --break-system-packages
```

## Run

```bash
python3 blackhole.py           # Auto-detects idle/active via real input
python3 blackhole.py --status  # Check current gravity level
python3 blackhole.py --reset   # Hard reset after a proper break
python3 blackhole.py --no-listen --rest  # Manual fallback if pynput can't grab input
```

You do not need to tell it when you're resting — it watches for itself.
Idle 60+ seconds = resting begins. Idle 20+ minutes = full collapse.

## Auto-launch in a tmux split (recommended)

Add to your ~/.zshrc or ~/.bashrc:
```bash
bhstart() {
  tmux split-window -h -l 85 "python3 ~/blackhole/blackhole.py"
}
```
Then call `bhstart` when you start a coding session.

## Physics

| Event | Effect |
|---|---|
| Working < 3h | No black hole, code shows normally |
| Working 3–4.5h | Micro singularity + accretion disk forms |
| Working 4.5–6h | Full lensing, code distorts |
| Idle 60s+ | Counts as "resting" automatically |
| Resting 10 min | Hole shrinks 50% |
| Resting 20 min | Full collapse |

## Permissions note (important)

- **macOS**: pynput needs Accessibility permission. First run will likely
  prompt you, or you may need to manually add your terminal app under
  System Settings → Privacy & Security → Accessibility.
- **Linux (X11)**: works out of the box in most cases.
- **Linux (Wayland)**: global input listening is restricted by design —
  pynput may silently fail to capture events. The script falls back to
  manual mode automatically (`--rest` flag) if this happens, and prints
  a warning to stderr so you know it happened.
- **WSL**: no access to Windows-side input — same fallback applies.

If you see "⚠️ manual mode" in the terminal output, idle detection
isn't working on your system — you're back to the honor system via
`--rest`.

## Customisation (top of blackhole.py)

```python
WORK_THRESHOLD_HRS  = 3.0   # When the hole starts forming
MAX_GROW_HRS        = 6.0   # Full size at this point
REST_SHRINK_HRS     = 0.33  # 20 min rest = full collapse
IDLE_THRESHOLD_SEC  = 60    # Seconds of no input before "resting" starts
RENDER_INTERVAL_SEC = 2     # Redraw rate
```

