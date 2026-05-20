# Changelog

All notable changes to the Grain Counter project.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [4.1.0] — 2026-05-19

### Added
- Cross-platform CLI tools: `grain`, `grainon`, `grainoff`, `grainkey`
- `config.local.yaml` support for local overrides without modifying base config
- Cloudflared tunnel URL auto-detection from `~/.cloudflared/config.yml`
- Comprehensive `TEST_PLAN.md` for structured testing
- Agent-harness test suite (unit + E2E)

### Changed
- Full README rewrite for GitHub public release
- Agent-harness CLI with cross-platform explorer support
- `tunnel_url` added to DEFAULT_CONFIG

### Fixed
- Auth config persistence (`--no-auth` overriding config.yaml)
- CLI import path resolution in agent-harness backends
- Cross-platform explorer indentation in `pages.py`
- `config.local.yaml` support in `lifecycle.py`

---

## [4.0.0] — 2026-05-19

### Added
- **Agent-Harness CLI**: pip-installable package (`grain`, `grainon`, `grainoff`, `grainkey`)
- Core backends: detector, server, config, HTTP client
- Cross-platform `start_panel.sh` shell script
- `models/.gitkeep` for preserving models directory

### Changed
- `.gitignore` expanded with 12 new exclusion patterns
- `config.yaml` model detection adjustments

### Removed
- Legacy `harness.ps1` and `run.ps1` (superseded by agent-harness)

---

## [3.1.0] — 2026-05-18

### Added
- Auto-start mode with PID file management
- Cloudflared auto-cleanup on graceful shutdown
- YOLO `max_det` raised from 300 to 1000
- Responsive UI polish

---

## [3.0.0] — 2026-05-17

### Added
- **Cloudflared Tunnel** integration for secure public access
- Multi-model warmup on startup
- Scan configuration UI in management panel
- Application state tracking (`state.py`)

---

## [2.1.0] — 2026-05-16

### Added
- **Security hardening**: 7 vulnerability fixes
- ScanGuard dual-detection mechanism
- Attack log for security event recording
- Inline CSS (Tailwind CDN replaced)
- `SECURITY_TEST_REPORT.md`

### Fixed
- Path traversal in model file serving
- API key brute-force via rate limiting
- CORS origin validation

---

## [2.0.0] — 2026-05-15

### Added
- **Modular refactoring**: `graincounter/` package with separate modules
- Route modules: admin, detect, devices, models, pages
- Graceful shutdown handler
- Config hot-reload support

---

## [1.1.0] — 2026-05-14

### Added
- **ScanGuard v1**: UvicornSafeFilter + anti-scan protection
- Runtime statistics (`stats.py`)
- Model folder shortcut in panel
- `test_verification.py` automated tests

---

## [1.0.0] — 2026-05-13

### Added
- Config persistence across restarts
- Model selection dropdown
- Image zoom up to 1000%
- Panel UI/Controls/Theme modules

---

## [0.9.0] — 2026-05-12

### Added
- Auth checkbox toggle in panel
- Mobile responsive design
- Confidence distribution bar chart

---

## [0.8.0] — 2026-05-11

### Added
- Project refactoring: modular architecture
- FastAPI entry point with startup/shutdown events
- Initial route system
- Centralized config, logger, middleware modules

---

## [0.7.0] — 2026-05-03

### Added
- Low-bandwidth optimization
- Skeleton loading screens
- Keyboard shortcuts (Enter to detect)
- Mobile adaptation

---

## [0.6.0] — 2026-05-02

### Added
- Tailscale integration
- Response compression (gzip/brotli)
- Heartbeat detection for device liveness

---

## [0.5.0] — 2026-05-01

### Added
- Online device management
- Confidence/IoU threshold controls
- Real-time parameter adjustment

---

## [0.4.0] — 2026-04-30

### Added
- Valuable photo filtering
- Tailwind CSS frontend redesign

---

## [0.3.0] — 2026-04-29

### Added
- API Key authentication
- Device tracking with unique IDs
- Rate limiting for API protection

---

## [0.2.0] — 2026-04-28

### Added
- Management panel
- Port configuration UI
- Auth toggle (enable/disable)
- Real-time server logs

---

## [0.1.0] — 2026-04-27

### Added
- Initial prototype
- FastAPI web server with async handling
- YOLO ONNX grain detection
- Basic Web UI
