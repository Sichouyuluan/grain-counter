"""Grain Counter CLI — command-line interface for wheat grain detection.

Usage:
    cli-anything-graincounter detect photo.jpg
    cli-anything-graincounter server start
    cli-anything-graincounter config show
    cli-anything-graincounter                    # REPL mode
"""
import os
import sys
import json
import cmd
import shlex
from pathlib import Path

import click

# Lazy imports to allow --help and server commands to work without project deps
_DetectorBackend = None
_ServerBackend = None
_ConfigBackend = None
_GrainAPIClient = None


def _get_detector_backend():
    global _DetectorBackend
    if _DetectorBackend is None:
        from .core.detector_backend import DetectorBackend as DB
        _DetectorBackend = DB
    return _DetectorBackend


def _get_server_backend():
    global _ServerBackend
    if _ServerBackend is None:
        from .core.server_backend import ServerBackend as SB
        _ServerBackend = SB
    return _ServerBackend


def _get_config_backend():
    global _ConfigBackend
    if _ConfigBackend is None:
        from .core.config_backend import ConfigBackend as CB
        _ConfigBackend = CB
    return _ConfigBackend


def _get_client():
    global _GrainAPIClient
    if _GrainAPIClient is None:
        from .utils.http_client import GrainAPIClient as GC
        _GrainAPIClient = GC
    api_key = os.environ.get("GRAIN_API_KEY")
    port = os.environ.get("GRAIN_PORT", "8000")
    return _GrainAPIClient(base_url=f"http://127.0.0.1:{port}", api_key=api_key)


def _print_json(data):
    click.echo(json.dumps(data, ensure_ascii=False, indent=2, default=str))


# ══════════════════════════════════════════════════════════════════════════════
# CLI Group
# ══════════════════════════════════════════════════════════════════════════════

@click.group(invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="Machine-readable JSON output")
@click.option("--api-key", default=None, help="API key for server authentication")
@click.option("--port", default=None, help="Server port (default: 8000)")
@click.pass_context
def cli(ctx, json_output, api_key, port):
    """Grain Counter CLI — 小麦籽粒检测命令行工具.

    Default (no subcommand) enters REPL interactive mode.
    """
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    if api_key:
        os.environ["GRAIN_API_KEY"] = api_key
        ctx.obj["api_key"] = api_key
    if port:
        os.environ["GRAIN_PORT"] = port
        ctx.obj["port"] = port

    if ctx.invoked_subcommand is None:
        # Enter REPL mode
        repl = GrainREPL(ctx)
        repl.cmdloop()


# ══════════════════════════════════════════════════════════════════════════════
# detect — Run detection on images (direct, no server needed)
# ══════════════════════════════════════════════════════════════════════════════

@cli.command()
@click.argument("images", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--conf", "-c", type=float, default=None, help="Confidence threshold (0.01-1.0)")
@click.option("--iou", "-i", type=float, default=None, help="IoU threshold (0.01-1.0)")
@click.option("--output", "-o", multiple=True, help="Save annotated image to path (one per input)")
@click.option("--model", "-m", default=None, help="Model name (e.g. grain_v8m_v11.onnx)")
@click.option("--json", "json_flag", is_flag=True, help="JSON output with base64 result image")
@click.option("--server", "use_server", is_flag=True, help="Use running server instead of direct detection")
@click.pass_context
def detect(ctx, images, conf, iou, output, model, json_flag, use_server):
    """Detect grains in one or more images.

    \b
    Examples:
      cli-anything-graincounter detect photo.jpg
      cli-anything-graincounter detect *.jpg --conf 0.5 --output results/
      cli-anything-graincounter detect a.jpg b.jpg -o a_out.jpg -o b_out.jpg
    """
    output_paths = list(output) if output else []

    if use_server:
        client = _get_client()
        for idx, img in enumerate(images):
            result = client.detect(img, conf=conf, iou=iou)
            if json_flag or ctx.obj.get("json"):
                _print_json(result)
            else:
                click.echo(f"{os.path.basename(img)}: {result['count']} grains ({result['elapsed_ms']}ms)")
            if output_paths and idx < len(output_paths):
                # Save base64 result image
                import base64
                b64 = result.get("result_image", "")
                if b64.startswith("data:"):
                    b64 = b64.split(",", 1)[1]
                with open(output_paths[idx], "wb") as f:
                    f.write(base64.b64decode(b64))
                click.echo(f"  -> {output_paths[idx]}")
        return

    backend = _get_detector_backend()()
    for idx, img in enumerate(images):
        out = output_paths[idx] if idx < len(output_paths) else None
        result = backend.detect(img, conf=conf, iou=iou, output=out, json_only=json_flag)
        if json_flag or ctx.obj.get("json"):
            _print_json(result)
        else:
            click.echo(f"{os.path.basename(img)}: {result['count']} grains ({result['elapsed_ms']}ms)")
            if out:
                click.echo(f"  -> {out}")


# ══════════════════════════════════════════════════════════════════════════════
# server — Manage the web server
# ══════════════════════════════════════════════════════════════════════════════

@cli.group()
def server():
    """Manage the Grain Counter web server."""


@server.command("start")
@click.option("--host", "-h", default=None, help="Bind host (default: 0.0.0.0)")
@click.option("--port", "-p", type=int, default=None, help="Bind port (default: 8000)")
@click.option("--model", "-m", default=None, help="Model file name")
@click.option("--no-auth", is_flag=True, help="Disable API key authentication")
@click.option("--api-key", default=None, help="Set custom API key")
@click.pass_context
def server_start(ctx, host, port, model, no_auth, api_key):
    """Start the web server."""
    backend = _get_server_backend()()
    result = backend.start(host=host, port=port, model=model, no_auth=no_auth, api_key=api_key)
    if ctx.obj.get("json"):
        _print_json(result)
    elif result.get("ok"):
        urls = result.get("urls", {})
        click.echo(f"Server started (PID: {result['pid']})")
        click.echo(f"  Local: {urls.get('local', 'N/A')}")
        if urls.get("lan"):
            click.echo(f"  LAN:   {urls.get('lan', 'N/A')}")
    else:
        click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)


@server.command("stop")
@click.pass_context
def server_stop(ctx):
    """Stop the web server."""
    backend = _get_server_backend()()
    result = backend.stop()
    if ctx.obj.get("json"):
        _print_json(result)
    elif result.get("ok"):
        click.echo("Server stopped")
    else:
        click.echo(f"Error: {result.get('error')}", err=True)


@server.command("status")
@click.pass_context
def server_status(ctx):
    """Show server status."""
    backend = _get_server_backend()()
    result = backend.status()
    if ctx.obj.get("json"):
        _print_json(result)
    elif result["running"]:
        urls = result.get("urls", {})
        click.echo(f"Server RUNNING (PID: {result['pid']})")
        click.echo(f"  Model: {result['model']}  Auth: {'ON' if result['auth'] else 'OFF'}")
        click.echo(f"  Local: {urls.get('local', 'N/A')}")
        if urls.get("lan"):
            click.echo(f"  LAN:   {urls.get('lan')}")
    else:
        click.echo("Server STOPPED")


@server.command("restart")
@click.option("--host", "-h", default=None)
@click.option("--port", "-p", type=int, default=None)
@click.option("--model", "-m", default=None)
@click.option("--no-auth", is_flag=True)
@click.pass_context
def server_restart(ctx, host, port, model, no_auth):
    """Restart the web server."""
    backend = _get_server_backend()()
    result = backend.restart(host=host, port=port, model=model, no_auth=no_auth)
    if ctx.obj.get("json"):
        _print_json(result)
    elif result.get("ok"):
        click.echo(f"Server restarted (PID: {result['pid']})")
    else:
        click.echo(f"Error: {result.get('error')}", err=True)


@server.command("url")
@click.pass_context
def server_url(ctx):
    """Show server URLs."""
    backend = _get_server_backend()()
    result = backend.url()
    if ctx.obj.get("json"):
        _print_json(result)
    elif result.get("ok"):
        for label, url in result["urls"].items():
            if url:
                click.echo(f"{label}: {url}")
    else:
        click.echo(f"Error: {result.get('error')}", err=True)


# ══════════════════════════════════════════════════════════════════════════════
# config — Manage configuration
# ══════════════════════════════════════════════════════════════════════════════

@cli.group()
def config():
    """Manage Grain Counter configuration."""


@config.command("show")
@click.argument("key", required=False)
@click.pass_context
def config_show(ctx, key):
    """Show current configuration."""
    backend = _get_config_backend()()
    result = backend.show(key=key)
    if ctx.obj.get("json"):
        _print_json(result)
    elif "error" in result:
        click.echo(result["error"], err=True)
    elif key:
        click.echo(f"{key} = {result[key]}")
    else:
        for k, v in result["config"].items():
            default = result["defaults"].get(k)
            marker = " (*)" if v != default else ""
            click.echo(f"  {k} = {v}{marker}")


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.option("--no-persist", is_flag=True, help="Don't save to config.yaml")
@click.pass_context
def config_set(ctx, key, value, no_persist):
    """Set a configuration value."""
    backend = _get_config_backend()()
    result = backend.set(key, value, persist=not no_persist)
    if ctx.obj.get("json"):
        _print_json(result)
    elif result.get("ok"):
        click.echo(f"{key} = {result['value']}")


@config.command("reset")
@click.argument("key", required=False)
@click.pass_context
def config_reset(ctx, key):
    """Reset config to defaults."""
    backend = _get_config_backend()()
    result = backend.reset(key=key)
    if ctx.obj.get("json"):
        _print_json(result)
    elif result.get("ok"):
        click.echo(result.get("message", "Reset complete"))


@config.command("list")
@click.pass_context
def config_list(ctx):
    """List all config keys."""
    backend = _get_config_backend()()
    items = backend.list_keys()
    if ctx.obj.get("json"):
        _print_json(items)
    else:
        for item in items:
            diff = "" if item["value"] == item["default"] else " *"
            click.echo(f"  {item['key']} = {item['value']}{diff}")


# ══════════════════════════════════════════════════════════════════════════════
# model — Manage detection models
# ══════════════════════════════════════════════════════════════════════════════

@cli.group()
def model():
    """Manage YOLO detection models."""


@model.command("list")
@click.option("--server", "use_server", is_flag=True, help="Query running server")
@click.pass_context
def model_list(ctx, use_server):
    """List available ONNX models."""
    if use_server:
        client = _get_client()
        result = client.list_models()
    else:
        backend = _get_detector_backend()()
        result = {"models": backend.list_models()}

    if ctx.obj.get("json"):
        _print_json(result)
    else:
        models = result.get("models", [])
        current = result.get("current", "")
        for m in models:
            marker = " [active]" if m.get("active") else ""
            click.echo(f"  {m['name']} ({m['size_mb']} MB){marker}")


@model.command("info")
@click.argument("name")
@click.option("--server", "use_server", is_flag=True, help="Query running server")
@click.pass_context
def model_info(ctx, name, use_server):
    """Show model details."""
    import os as _os
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    model_path = _os.path.join(project_root, "models", name)
    if not _os.path.exists(model_path):
        click.echo(f"Model not found: {name}", err=True)
        return
    info = {
        "name": name,
        "path": model_path,
        "size_mb": round(_os.path.getsize(model_path) / 1024 / 1024, 1),
        "active": _os.path.basename(_get_config_val("model_path", "")) == name,
    }
    if ctx.obj.get("json"):
        _print_json(info)
    else:
        click.echo(f"  Name:   {info['name']}")
        click.echo(f"  Size:   {info['size_mb']} MB")
        click.echo(f"  Active: {info['active']}")
        click.echo(f"  Path:   {info['path']}")


@model.command("switch")
@click.argument("name")
@click.pass_context
def model_switch(ctx, name):
    """Switch active model (requires running server)."""
    client = _get_client()
    try:
        result = client.select_model(name)
        if ctx.obj.get("json"):
            _print_json(result)
        else:
            warm = " (from warm cache)" if result.get("from_warm") else ""
            click.echo(f"Switched to: {result['model']}{warm}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@model.command("warm")
@click.argument("name")
@click.pass_context
def model_warm(ctx, name):
    """Pre-load a model into warm cache (requires running server)."""
    client = _get_client()
    try:
        result = client.warm_model(name)
        if ctx.obj.get("json"):
            _print_json(result)
        else:
            click.echo(f"Model warmed: {result['model']} ({result['status']})")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@model.command("warm-status")
@click.pass_context
def model_warm_status(ctx):
    """Show warm model cache status (requires running server)."""
    client = _get_client()
    try:
        result = client.warm_status()
        if ctx.obj.get("json"):
            _print_json(result)
        else:
            click.echo(f"Main model: {result.get('main_model', 'N/A')}")
            click.echo(f"Warm count: {result.get('warm_count', 0)}")
            for name, status in result.get("models", {}).items():
                tag = " [MAIN]" if status.get("is_main") else f" (idle {status.get('idle_seconds', 0)}s)"
                click.echo(f"  {name}{tag}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


# ══════════════════════════════════════════════════════════════════════════════
# key — API key management (requires running server)
# ══════════════════════════════════════════════════════════════════════════════

@cli.group()
def key():
    """Manage API key (requires running server)."""


@key.command("show")
@click.pass_context
def key_show(ctx):
    """Show current API key (reads from file if server is not running)."""
    client = _get_client()
    try:
        result = client.get_key()
        if ctx.obj.get("json"):
            _print_json(result)
        else:
            click.echo(f"API Key: {result['key']}")
    except Exception:
        # Server not reachable — read from .api_key file directly
        _project = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        key_file = os.path.join(_project, ".api_key")
        if os.path.exists(key_file):
            with open(key_file, "r") as f:
                key = f.read().strip()
            if ctx.obj.get("json"):
                _print_json({"key": key, "source": "file"})
            else:
                click.echo(f"API Key: {key}")
                click.echo("(from .api_key file — server not running)")
        else:
            click.echo("No API key found (server not running, no .api_key file)", err=True)


@key.command("regenerate")
@click.pass_context
def key_regenerate(ctx):
    """Regenerate API key."""
    client = _get_client()
    try:
        result = client.regenerate_key()
        if ctx.obj.get("json"):
            _print_json(result)
        else:
            click.echo(f"New API Key: {result['key']}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


# ══════════════════════════════════════════════════════════════════════════════
# stats — Detection statistics (requires running server)
# ══════════════════════════════════════════════════════════════════════════════

@cli.command()
@click.pass_context
def stats(ctx):
    """Show detection statistics (requires running server)."""
    client = _get_client()
    try:
        result = client.stats()
        if ctx.obj.get("json"):
            _print_json(result)
        else:
            click.echo(f"Total detections: {result.get('total_detections', 0)}")
            click.echo(f"Average count:    {result.get('avg_count_per_image', 0):.1f}")
            click.echo(f"Average time:     {result.get('avg_time_ms', 0):.0f}ms")
            click.echo(f"Success: {result.get('success_count', 0)}  Errors: {result.get('error_count', 0)}")
            guard = result.get("guard", {})
            if guard:
                click.echo(f"ScanGuard: {guard.get('protection_count', 0)} protections")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


# ══════════════════════════════════════════════════════════════════════════════
# health — Quick health check
# ══════════════════════════════════════════════════════════════════════════════

@cli.command()
@click.pass_context
def health(ctx):
    """Check server health (requires running server)."""
    client = _get_client()
    try:
        result = client.health()
        if ctx.obj.get("json"):
            _print_json(result)
        else:
            click.echo(f"Status: {result['status']}")
            click.echo(f"Model:  {result['model']}")
            click.echo(f"Auth:   {'ON' if result['auth'] else 'OFF'}")
    except Exception as e:
        click.echo(f"Server unreachable: {e}", err=True)


# ══════════════════════════════════════════════════════════════════════════════
# REPL — Interactive shell
# ══════════════════════════════════════════════════════════════════════════════

def _get_config_val(key, default=None):
    """Lazy-load a single config value."""
    try:
        from graincounter.config import get_config
        return get_config(key, default)
    except Exception:
        return default


class GrainREPL(cmd.Cmd):
    """Interactive REPL for Grain Counter CLI."""

    intro = """
╔══════════════════════════════════════════╗
║   🌾 Grain Counter CLI — Interactive    ║
║   Type 'help' for commands, 'quit' to exit  ║
╚══════════════════════════════════════════╝
"""
    prompt = "grain> "

    def __init__(self, cli_ctx):
        super().__init__()
        self.cli_ctx = cli_ctx
        self._json = cli_ctx.obj.get("json", False)

    def _run_click(self, cmd_name, *args):
        """Invoke a Click command from the REPL."""
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(cli, [cmd_name] + list(args), obj=self.cli_ctx.obj)
        if result.output:
            click.echo(result.output.rstrip())
        if result.exit_code != 0 and result.exception:
            click.echo(f"Error: {result.exception}", err=True)

    def do_detect(self, arg):
        """detect <image...> [--conf C] [--iou I] [-o OUTPUT] [-m MODEL]: Run grain detection"""
        self._run_click("detect", *shlex.split(arg))

    def do_server(self, arg):
        """server <start|stop|status|restart|url> [opts]: Manage web server"""
        self._run_click("server", *shlex.split(arg))

    def do_config(self, arg):
        """config <show|set|reset|list> [args]: Manage configuration"""
        self._run_click("config", *shlex.split(arg))

    def do_model(self, arg):
        """model <list|info|switch|warm|warm-status> [args]: Manage models"""
        self._run_click("model", *shlex.split(arg))

    def do_key(self, arg):
        """key <show|regenerate>: Manage API key"""
        self._run_click("key", *shlex.split(arg))

    def do_stats(self, arg):
        """stats: Show detection statistics"""
        self._run_click("stats")

    def do_health(self, arg):
        """health: Check server health"""
        self._run_click("health")

    def do_json(self, arg):
        """json <on|off>: Toggle JSON output mode"""
        if arg.strip().lower() in ("on", "true", "1"):
            self._json = True
            self.cli_ctx.obj["json"] = True
            click.echo("JSON output: ON")
        else:
            self._json = False
            self.cli_ctx.obj["json"] = False
            click.echo("JSON output: OFF")

    def do_quit(self, arg):
        """quit: Exit REPL"""
        click.echo("Bye!")
        return True

    def do_exit(self, arg):
        """exit: Exit REPL"""
        return self.do_quit(arg)

    do_EOF = do_quit


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def main():
    cli()


if __name__ == "__main__":
    main()
