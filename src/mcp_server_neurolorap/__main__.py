"""Entry point for the MCP server.

This module provides the main entry point for running the server
and handles configuration setup.
"""

import asyncio
import json
import logging
import signal
import sys
from pathlib import Path
from types import FrameType
from typing import Dict, TypedDict, cast

from mcp_server_neurolorap.server import create_server, run_dev_mode

# Global flag for graceful shutdown
shutdown_requested = False


def handle_shutdown(signum: int, frame: FrameType | None) -> None:
    """Handle shutdown signals.

    Args:
        signum: Signal number
        frame: Current stack frame
    """
    global shutdown_requested
    logger.info("Shutdown requested, cleaning up...")
    shutdown_requested = True


# Configure root logger for terminal output
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Create console handler for terminal output
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setFormatter(logging.Formatter("%(message)s"))
root_logger.addHandler(console_handler)

# Configure MCP logger
mcp_logger = logging.getLogger("mcp")
mcp_logger.setLevel(logging.WARNING)

# Get module logger
logger = logging.getLogger(__name__)

# Prevent propagation to avoid duplicate logs
logger.propagate = False


class ServerConfig(TypedDict):
    """MCP server configuration type."""

    command: str
    args: list[str]
    disabled: bool
    alwaysAllow: list[str]
    env: Dict[str, str]


class ClinesConfig(TypedDict):
    """Cline settings configuration type."""

    mcpServers: Dict[str, ServerConfig]


def get_config_path() -> Path:
    """Get the path to the Cline configuration file.

    Returns:
        Path: The path to the configuration file
    """
    home = Path.home()
    return (
        home
        / "Library"
        / "Application Support"
        / "Code"
        / "User"
        / "globalStorage"
        / "saoudrizwan.claude-dev"
        / "settings"
        / "cline_mcp_settings.json"
    )


def configure_cline(config_path: Path | None = None) -> None:
    """Configure integration with Cline.

    Automatically sets up the MCP server configuration in Cline's settings.
    Handles installation, updates, and environment configuration.

    Args:
        config_path: Optional path to the configuration file (for testing)
    """
    try:
        # Get Cline config path
        if config_path is None:
            config_path = get_config_path()

        config: ClinesConfig
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                raw_config = json.load(f)
                if "mcpServers" not in raw_config:
                    raw_config["mcpServers"] = {}
                config = cast(ClinesConfig, raw_config)
        else:
            logger.info("Cline config not found, creating new configuration")
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config = {"mcpServers": {}}

        # Get project root path
        project_root = Path(__file__).resolve().parent.parent.parent

        server_name = "aindreyway-mcp-neurolorap"
        server_config: ServerConfig = {
            "command": sys.executable,
            "args": ["-m", "mcp_server_neurolorap"],
            "disabled": False,
            "alwaysAllow": [],
            "env": {
                "PYTHONPATH": str(project_root),
                "PYTHONUNBUFFERED": "1",
                "MCP_PROJECT_ROOT": str(project_root),
            },
        }

        if server_name not in config["mcpServers"]:
            config["mcpServers"][server_name] = server_config
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            logger.info("Added server configuration to Cline")
        else:
            current_config = config["mcpServers"][server_name]
            if current_config != server_config:
                config["mcpServers"][server_name] = server_config
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
                logger.info("Updated server configuration in Cline")
            else:
                logger.info("Server already configured in Cline")

    except Exception as e:
        logger.warning(f"Failed to configure Cline: {e}")


def main() -> None:
    """Run the server with stdio transport or in developer mode."""
    # Check for developer mode
    if len(sys.argv) > 1 and sys.argv[1] == "--dev":
        asyncio.run(run_dev_mode())
        return

    try:
        # Configure Cline integration
        configure_cline()

        # Set up signal handlers
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)

        # Create and run server
        server = create_server()
        if server.run is None:
            raise RuntimeError("Server run method is not initialized")
        server.run()

    except Exception as e:
        error_msg = (
            f"Server startup failed: {e.__class__.__name__}\n"
            f"Details: {str(e)}\n"
            "Check the logs for more information."
        )
        logger.exception(error_msg)
        sys.exit(1)


def main_entry() -> None:
    """Entry point for the server.

    Supports two modes:
    - Normal mode: Run as MCP server with stdio transport
    - Developer mode: Run with JSON-RPC terminal (use --dev flag)
    """
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception:
        logger.exception("Server error")
        sys.exit(1)


if __name__ == "__main__":
    main_entry()
