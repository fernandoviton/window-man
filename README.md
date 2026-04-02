# window-man

A proof-of-concept CLI window manager for Windows. List visible windows, move/resize them, snap them to screen halves, and save/restore window layouts with named groups. Uses Python's `ctypes` to call Win32 APIs directly; only external dependency is PyYAML.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install pyyaml
```

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
4. Ensure a window (launch if needed)
5. Update layout
6. Load layout
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

# Launch an app if no matching window is found
python wman.py ensure <title> --path <executable>

# Update layout — diffs current windows against saved entries, shows
# a confirmation prompt, then writes changes.  Without --group: updates
# all entries (adds new windows, removes stale).  With --group: scoped
# to that group only (updates/removes, no additions).
python wman.py update [--file layout.yml] [--group NAME]

# Restore a saved layout (launch missing apps + reposition)
# Without --group: restores all entries. With --group: only that group.
python wman.py load [--file layout.yml] [--group NAME]
```

`<window>` can be:
- A title substring (case-insensitive): `"Notepad"`, `"calc"`
- A window handle (decimal or hex): `12345`, `0x3039`

## Layout file

Layouts are stored as a flat YAML list. Each entry has an optional `group` tag:

```yaml
- title: "Microsoft Teams"
  path: "C:\\...\\ms-teams.exe"
  x: 0
  y: 0
  width: 1920
  height: 1040
  group: always

- title: "Visual Studio Code"
  path: "C:\\...\\Code.exe"
  x: 0
  y: 0
  width: 960
  height: 1040
  group: dev

- title: "Untitled - Notepad"
  path: "C:\\Windows\\notepad.exe"
  x: 100
  y: 200
  width: 800
  height: 600
```

## Examples

```bash
# Snap Notepad to the left half of the screen
python wman.py snap "Notepad" --direction left

# Move a window by handle to a specific position
python wman.py move 0x3039 --x 100 --y 100 --width 800 --height 600

# Save all windows as the "dev" group
python wman.py update --group dev

# Restore the "dev" group (launches missing apps, repositions running ones)
python wman.py load --group dev
```

## Running tests

```
python -m unittest discover -s tests -p "*_test.py" -v
```

All Win32 APIs are mocked — tests run on any platform.

## Limitations

- Snapping targets the primary monitor only. Multi-monitor support would require `MonitorFromWindow` + `GetMonitorInfoW`.
- Title matching fails if multiple windows match, listing all candidates.

## Future: Windows 11 Snap Groups

Windows 11 Snap Groups let you snap windows side-by-side (Win+Left/Right, or drag-to-top layout picker) and the OS remembers them as a group — hovering the taskbar shows the whole group together.

### What we explored

We investigated three levels of programmatic access:

| Approach | Reads groups? | Creates groups? |
|----------|:---:|:---:|
| **AppUserModelID** (`SHGetPropertyStoreForWindow`, `GetApplicationUserModelId`) | ❌ Wrong abstraction — this is taskbar button grouping, not snap groups | N/A |
| **Window position heuristics** (compare rects against work-area halves/quarters) | ⚠️ Can infer snapped layout but not whether the OS considers them a "group" | ❌ `MoveWindow`/`SetWindowPos` positions windows but the OS does not register them as a Snap Group |
| **DWM attributes** (`DwmGetWindowAttribute` probed up to attr 60) | ❌ No snap-group attribute found | N/A |

**Bottom line:** there is no public Win32, COM, or Shell API to read or create Snap Groups. They are managed internally by explorer.exe with no documented interface. See [StackOverflow](https://stackoverflow.com/questions/77523400/is-there-an-api-to-programmatically-invoke-snap-layout) and [Microsoft Docs](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-snap-layout-menu) for context.

### Potential approach: simulated input

Since the Snap Assist UI is the only way to create a real Snap Group, we could automate it with `SendInput` (ctypes):

1. Focus window A → send `Win+Left` (snaps left, triggers Snap Assist picker)
2. Snap Assist shows remaining windows on the other half — send arrow keys + Enter to select window B
3. The OS now recognizes A+B as a Snap Group

This would create genuine OS-level Snap Groups without external dependencies. The challenges are timing (waiting for Snap Assist to appear) and reliably navigating the picker. A CUA (computer-use agent) with screenshot feedback would be more robust but heavier.

Exploration scripts from this investigation are in `explore_grouping.py`, `explore_grouping_v2.py`, and `explore_snap_groups.py`.