# Grain Counter CLI

CLI-Anything harness for **Grain Counter** (小麦籽粒检测) — a wheat grain detection and counting service using YOLOv8 ONNX models.

## Installation

```bash
cd agent-harness
pip install -e .
```

## Quick Start

```bash
# One-shot detection (no server needed)
grain detect photo.jpg
grain detect *.jpg --conf 0.5 -o results/

# Start the web server
grain server start
grain server start --port 8080 --model grain_v8m_v11.onnx

# Check server status
grain server status
grain health

# Manage configuration
grain config show
grain config set score_threshold 0.5

# List and switch models
grain model list
grain model switch grain_v8m_v11.onnx

# API key management
grain key show
grain key regenerate

# Detection statistics
grain stats

# JSON output for scripting
grain --json detect photo.jpg
```

## Commands

### `detect` — Run grain detection
Direct detection using YOLOv8 ONNX — no server required. Supports batch processing.

```
grain detect <images...> [--conf C] [--iou I] [--output PATH] [--model NAME]
```

### `server` — Web server management
Start/stop/restart the FastAPI web server, check status, get URLs.

```
grain server start [--host H] [--port P] [--model M] [--no-auth]
grain server stop
grain server status
grain server restart
grain server url
```

### `config` — Configuration management
Read/write config.yaml settings.

```
grain config show [KEY]
grain config set KEY VALUE [--no-persist]
grain config reset [KEY]
grain config list
```

### `model` — Model management
List, inspect, switch, and warm models.

```
grain model list [--server]
grain model info NAME
grain model switch NAME
grain model warm NAME
grain model warm-status
```

### `key` — API key management
Show or regenerate the server API key.

```
grain key show
grain key regenerate
```

### `stats` — Detection statistics
Show detection counts, averages, timing, and ScanGuard status.

```
grain stats
```

### `health` — Health check
Quick server health check.

```
grain health
```

## REPL Mode

Running `grain` with no arguments enters interactive REPL mode:

```
grain> detect photo.jpg
grain> server status
grain> config show score_threshold
grain> json on
grain> quit
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `GRAIN_API_KEY` | API key for server authentication |
| `GRAIN_PORT` | Server port (default: 8000) |
| `GRAIN_CONFIG_PATH` | Custom config.yaml path |
