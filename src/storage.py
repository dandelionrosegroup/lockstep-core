# Lockstep Chain Protocol — storage and persistence layer
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

"""Storage layer for Lockstep data (YAML I/O, naming conventions, archive).

Isolates all filesystem operations so tool modules stay pure logic.
"""

from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path
from typing import Optional

import yaml

from schemas import Chain, CapacityFile, Ticket


# --- Naming Conventions ---


def to_kebab_case(text: str) -> str:
    """Convert a title string to kebab-case for IDs and filenames."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def chain_filename(chain_id: str) -> str:
    """CHAIN-[kebab-title].yaml"""
    return f"CHAIN-{chain_id}.yaml"


def ticket_filename(ticket_id: str) -> str:
    """TICKET-[zero-padded-3].yaml"""
    return f"{ticket_id}.yaml"


def capacity_filename(role: str) -> str:
    """[role-name].yaml"""
    return f"{role}.yaml"


def archived_chain_filename(chain_id: str, archive_date: date) -> str:
    """CHAIN-[title]-ARCHIVED-[date].yaml"""
    return f"CHAIN-{chain_id}-ARCHIVED-{archive_date.isoformat()}.yaml"


def archived_ticket_filename(ticket_id: str, archive_date: date) -> str:
    """TICKET-[number]-ARCHIVED-[date].yaml"""
    return f"{ticket_id}-ARCHIVED-{archive_date.isoformat()}.yaml"


# --- Path Helpers ---


def chain_path(data_dir: Path, chain_id: str) -> Path:
    return data_dir / "chains" / chain_filename(chain_id)


def ticket_path(data_dir: Path, ticket_id: str) -> Path:
    return data_dir / "tickets" / ticket_filename(ticket_id)


def capacity_path(data_dir: Path, role: str) -> Path:
    return data_dir / "capacity" / capacity_filename(role)


def get_data_dir(ctx) -> Path:
    """Extract data_dir from FastMCP lifespan context."""
    return ctx.request_context.lifespan_context["data_dir"]


# --- YAML I/O ---


def _dump_yaml(data: dict) -> str:
    """Serialize dict to YAML string with consistent formatting."""
    return yaml.dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )


def _model_to_dict(model) -> dict:
    """Convert Pydantic model to dict suitable for YAML storage."""
    return model.model_dump(mode="json", exclude_none=True)


# -- Chain I/O --


def read_chain(data_dir: Path, chain_id: str) -> Chain:
    """Read a chain YAML file and return a validated Chain model."""
    path = chain_path(data_dir, chain_id)
    with open(path) as f:
        data = yaml.safe_load(f)
    return Chain(**data)


def write_chain(data_dir: Path, chain: Chain) -> Path:
    """Write a Chain model to YAML. Returns the file path."""
    path = chain_path(data_dir, chain.chain_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(_dump_yaml(_model_to_dict(chain)))
    return path


# -- Ticket I/O --


def read_ticket(data_dir: Path, ticket_id: str) -> Ticket:
    """Read a ticket YAML file and return a validated Ticket model."""
    path = ticket_path(data_dir, ticket_id)
    with open(path) as f:
        data = yaml.safe_load(f)
    return Ticket(**data)


def write_ticket(data_dir: Path, ticket: Ticket) -> Path:
    """Write a Ticket model to YAML. Returns the file path."""
    path = ticket_path(data_dir, ticket.ticket_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(_dump_yaml(_model_to_dict(ticket)))
    return path


# -- Capacity I/O --


def read_capacity(data_dir: Path, role: str) -> CapacityFile:
    """Read a capacity YAML file and return a validated CapacityFile model."""
    path = capacity_path(data_dir, role)
    with open(path) as f:
        data = yaml.safe_load(f)
    return CapacityFile(**data)


def write_capacity(data_dir: Path, capacity: CapacityFile) -> Path:
    """Write a CapacityFile model to YAML. Returns the file path."""
    path = capacity_path(data_dir, capacity.role)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(_dump_yaml(_model_to_dict(capacity)))
    return path


# --- Ticket Numbering ---


def next_ticket_number(data_dir: Path) -> str:
    """Determine the next sequential ticket ID by scanning existing files.

    Returns a zero-padded 3-digit ticket ID (e.g. 'TICKET-003').
    """
    tickets_dir = data_dir / "tickets"
    if not tickets_dir.exists():
        return "TICKET-001"

    max_num = 0
    for path in tickets_dir.glob("TICKET-*.yaml"):
        match = re.search(r"TICKET-(\d+)", path.stem)
        if match:
            num = int(match.group(1))
            max_num = max(max_num, num)

    return f"TICKET-{max_num + 1:03d}"


# --- Archive Operations ---


def archive_chain_file(data_dir: Path, chain_id: str, archive_date: date) -> Path:
    """Move a chain file to the archive directory.

    Returns the new archive path. Raises FileExistsError if destination exists.
    """
    src = chain_path(data_dir, chain_id)
    dest_dir = data_dir / "archive" / "chains"
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / archived_chain_filename(chain_id, archive_date)
    if dest.exists():
        raise FileExistsError(f"Archive destination already exists: {dest}")

    shutil.move(str(src), str(dest))
    return dest


def archive_ticket_file(
    data_dir: Path, ticket_id: str, archive_date: date
) -> Optional[Path]:
    """Move a ticket file to the archive directory.

    Returns the new archive path, or None if ticket file not found.
    """
    src = ticket_path(data_dir, ticket_id)
    if not src.exists():
        return None

    dest_dir = data_dir / "archive" / "tickets"
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / archived_ticket_filename(ticket_id, archive_date)
    if dest.exists():
        raise FileExistsError(f"Archive destination already exists: {dest}")

    shutil.move(str(src), str(dest))
    return dest


# --- Query Helpers ---


def list_chain_files(data_dir: Path) -> list[Path]:
    """List all active (non-archived) chain files."""
    chains_dir = data_dir / "chains"
    if not chains_dir.exists():
        return []
    return sorted(chains_dir.glob("CHAIN-*.yaml"))


def list_ticket_files(data_dir: Path) -> list[Path]:
    """List all active (non-archived) ticket files."""
    tickets_dir = data_dir / "tickets"
    if not tickets_dir.exists():
        return []
    return sorted(tickets_dir.glob("TICKET-*.yaml"))


def list_capacity_files(data_dir: Path) -> list[Path]:
    """List all capacity role files."""
    cap_dir = data_dir / "capacity"
    if not cap_dir.exists():
        return []
    return sorted(cap_dir.glob("*.yaml"))
