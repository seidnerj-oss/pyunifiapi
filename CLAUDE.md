# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

py-unifiapi is a Python client for UniFi Network controller and cloud API over WebRTC. The primary use case is SSH access to UniFi devices through the controller's WebRTC debug terminal protocol, enabling programmatic shell access to devices that don't expose SSH directly. Also provides a full REST API client and cloud API access via WebRTC data channels. Supports TOTP-based 2FA.

## Quick Setup

```bash
uv sync --group dev
uv run pre-commit install
```

## Architecture

```
src/pyunifiapi/
  __init__.py            # Public API exports
  _constants.py          # URLs, timeouts, API paths
  _types.py              # Dataclasses (ControllerConfig, SSHConfig, TurnCredentials, etc.)
  _exceptions.py         # Exception hierarchy
  client.py              # UnifiClient - local controller REST API (~40 methods)
  cloud.py               # CloudClient - REST via WebRTC data channel through cloud
  controller.py          # Controller connection management
  websocket.py           # WebSocket event streaming
  handlers/              # API handler methods
  models/                # Data models
  http/
    _local.py            # LocalHttpTransport - httpx with cookie auth, CSRF, auto-reauth
    _cloud.py            # CloudHttpTransport - httpx for Ubiquiti SSO (sso.ubnt.com)
  webrtc/
    _peer.py             # PeerConnection - aiortc wrapper (accept_offer/create_offer)
    _framing.py          # Binary message framing for cloud API data channel
  signaling/
    _local.py            # LocalSignaling - SDP exchange via controller REST API
    _cloud.py            # CloudSignaling - SDP exchange via cloud WebSocket
  ssh/
    session.py           # SSHSession - SSH-over-WebRTC orchestrator
  cli/
    __main__.py          # CLI entry point (pyunifiapi ssh ...)
```

## Code Provenance Policy

**All code must be written independently.** Never directly copy or adapt code from any external source - always study the concept and implement it yourself from scratch. Specifically:

- **Never copy or adapt code from AGPL, GPL, SSPL, or other copyleft-licensed projects.** These licenses are incompatible with MIT.
- **Never copy or adapt code from proprietary or commercially-licensed sources.**
- **In rare cases** where direct reuse of code from MIT, BSD, Apache 2.0 projects is genuinely necessary, preserve their license/copyright notices. Prefer independent implementation.

## Code Style Guidelines

- **Formatting**: Enforced by ruff (line-length=150, single quotes, py313 target)
- **Naming**: Constants in ALL_CAPS, classes in CamelCase, variables/functions in snake_case
- **Import ordering**: ALL imports at the top of the file, never mid-file
  - Standard library first, then third-party, then local modules
- **Type hints**: Use for function parameters and return values
- **Deduplication**: Extract shared logic into helper functions. Single source of truth

## CRITICAL: FORMATTING RULES

- **NEVER use em dashes anywhere** - not in console output, code, commit messages, PR descriptions, comments, user messages, API calls, or any other output
- **ALWAYS use regular hyphens/dashes (-) instead of em dashes**

## CRITICAL: TESTING REQUIREMENTS

**MANDATORY**: Every feature addition or code change MUST include corresponding tests:
- **ALWAYS add tests for new features** - every new feature must include corresponding test coverage
- **ALWAYS update existing tests** when modifying behavior - if a change breaks or alters existing functionality, update the relevant tests to match
- When fixing a bug, add a test that reproduces the bug and verifies the fix
- **Test coverage is not optional** - do not consider a feature or change complete until tests are in place
- **Match existing test patterns** - follow the conventions and frameworks already used in the codebase
- **Include edge cases** - tests should cover happy paths, error cases, and boundary conditions where relevant
- Tests should be placed in the appropriate `tests/` directory mirroring the source structure

## CRITICAL: COMMIT AND PUSH RULES

**When creating git commits, Claude MUST follow these rules without exception:**
- **NEVER COMMIT WITHOUT EXPLICIT USER CONSENT** - user must explicitly say "commit" or "commit this" or similar
- **NEVER note Claude as a user on any commit** - no author, co-author, or attribution to Claude
- NEVER include "Generated with [Claude Code]" or "Co-Authored-By: Claude" in commit messages
- NEVER execute `git add` without explicit user permission
- NEVER execute `git commit` without explicit user permission (e.g. "commit this", "commit and push")
- NEVER execute `git push` unless explicitly instructed by the user
- NEVER use `git commit --no-verify` or `git commit -n` to bypass pre-commit hooks without EXPLICIT user confirmation
- ALWAYS show the complete commit message to user and ask for confirmation before executing `git commit`
- ALWAYS ask for explicit permission before pushing changes to remote repository
- ALWAYS let pre-commit hooks run - if they fail, fix the issues rather than bypassing
- Keep commit messages clean and professional without AI-generated footers
- Do NOT auto-commit after making code changes - wait for explicit user instruction

## Git Guidelines

**File Operations:**
- **ALWAYS use `git mv` instead of `mv`** when moving or renaming files in the repository
- This preserves git history and makes it easier to track file evolution

**Commit Guidelines:**
- Never commit OR push without explicit user permission
- Do NOT add ANY AI attribution messages or tool references to commit messages
- **ALWAYS split unrelated changes into separate commits** - group files by logical change (e.g., a config file change in one commit, a code refactor in another). Do not glob everything into a single commit unless all changes are part of the same logical unit of work

## Key Design Decisions

- **Two WebRTC modes**: SSH mode (device creates offer, we answer) vs Cloud mode (we create offer with 'api' channel)
- **Separate HTTP transports**: Local (cookie auth) vs Cloud (SSO tokens) have different auth flows
- **Signaling layer**: Decoupled from WebRTC - local uses REST API polling, cloud uses WebSocket
- **Binary framing**: Cloud API multiplexes REST requests over a single data channel using a 16-byte header protocol
