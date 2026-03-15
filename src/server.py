# Lockstep Chain Protocol — MCP server entry point
# Copyright (C) 2025-2026 Jack Daniel Williams / Dandelion Rose Group, LLC
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Lockstep Chain Protocol MCP Server — entry point.

FastMCP server for chain, ticket, capacity, and session telemetry
operations. 35 tools across 5 groups.
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from capacity_tools import register_capacity_tools
from chain_tools import register_chain_tools
from commands import register_commands
from query_tools import register_query_tools
from session_tools import register_session_tools
from templates import load_templates, validate_all_templates
from ticket_tools import register_ticket_tools


def _resolve_data_dir() -> Path:
    """Resolve the data directory for chain/ticket/capacity storage.

    Resolution order:
    1. LOCKSTEP_DATA_DIR environment variable (set by MCPB user_config)
    2. config.json adjacent to server.py (for local development)
    3. Default: ~/.lockstep/data
    """
    # 1. Environment variable override (MCPB bundle sets this)
    env_dir = os.environ.get("LOCKSTEP_DATA_DIR")
    if env_dir:
        return Path(os.path.expanduser(env_dir))

    # 2. Config file (local development convenience)
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
        if "data_dir" in config:
            data_dir = config["data_dir"]
            if not os.path.isabs(data_dir):
                return Path(__file__).parent / data_dir
            return Path(os.path.expanduser(data_dir))

    # 3. Default
    return Path.home() / ".lockstep" / "data"


@asynccontextmanager
async def app_lifespan(server):
    """Initialize data directories and yield shared state."""
    data_dir = _resolve_data_dir()

    # Ensure directory structure exists
    subdirs = [
        "chains",
        "tickets",
        "capacity",
        "declarations",
        "handoffs",
        "catches",
        Path("archive") / "chains",
        Path("archive") / "tickets",
    ]
    for subdir in subdirs:
        (data_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Load and validate chain type templates
    templates = load_templates()
    failures = validate_all_templates()
    if failures:
        import sys
        for chain_type, errs in failures.items():
            print(f"Template validation error [{chain_type}]: {errs}", file=sys.stderr)

    yield {
        "data_dir": data_dir,
        "templates": templates,
    }


# --- Server initialization ---

mcp = FastMCP("lockstep-chain-protocol", lifespan=app_lifespan)

# Chain + Ticket lifecycle
register_chain_tools(mcp)
register_ticket_tools(mcp)

# Capacity, Query, Session, Commands
register_capacity_tools(mcp)
register_query_tools(mcp)
register_session_tools(mcp)
register_commands(mcp)


def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
