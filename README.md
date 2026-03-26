# window-man

A proof-of-concept CLI window manager for Windows. List visible windows, move/resize them, and snap them to screen halves. Zero external dependencies — uses Python's `ctypes` to call Win32 APIs directly.

## Usage

### Interactive mode

```
python wman.py
```

Presents a menu:

```
Window Manager
==============
1. List windows
2. Move a window
3. Snap a window
q. Quit

Choose:
```

### Direct mode

```bash
# List visible windows
python wman.py list

# Move a window (all position args are optional)
python wman.py move <window> [--x X] [--y Y] [--width W] [--height H]

# Snap a window to left or right half of the screen
python wman.py snap <window> --direction left|right
```

`<window>` can be:
- A title substring (case-insensitive): `"Notepad"`, `"calc"`
- A window handle (decimal or hex): `12345`, `0x3039`

## Examples

```bash
# Snap Notepad to the left half of the screen
python wman.py snap "Notepad" --direction left

# Move a window by handle to a specific position
python wman.py move 0x3039 --x 100 --y 100 --width 800 --height 600

# Resize a window without changing its position
python wman.py move "Calculator" --width 400 --height 300
```

## Running tests

```
python -m unittest test_wman -v
```

All Win32 APIs are mocked — tests run on any platform.

## Limitations

- Snapping targets the primary monitor only. Multi-monitor support would require `MonitorFromWindow` + `GetMonitorInfoW`.
- Title matching returns the first match found.

## TODO
- Change title matching to fail and notify if multiple are found (and show the multiple it could be - bash like)
- Explore launching
- Do full persistence and rehydration