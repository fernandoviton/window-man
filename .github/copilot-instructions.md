# Copilot Instructions for window-man

## Project Overview

A proof-of-concept CLI window manager for Windows. Uses Python `ctypes` to call Win32 APIs directly — zero external dependencies.

## Conventions

- Python standard library only — no external dependencies
- Win32 API access via `ctypes` (not `pywin32`)
- Tests use `unittest` with mocked Win32 calls
- Run tests with: `python -m unittest test_wman test_ensure -v`

## Custom Agents

This repo defines custom agents and skills in `.claude/`. See `agents.md` for a summary and links. When asked to review a plan, read the full definitions from `.claude/` and follow those instructions.
