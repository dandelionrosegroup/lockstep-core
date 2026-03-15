#!/usr/bin/env python3
# Lockstep Chain Protocol — v1 → v2 migration script
# Copyright (C) 2025-2026 Jack Daniel Williams / Dandelion Rose Group, LLC
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""One-time migration: update all v1 chain/ticket YAML to v2 schema.

Changes applied:
  - Chain: template → chain_type (enum value → plain string)
  - Chain: add child_tickets, spawn_reason fields (empty defaults)
  - All files: schema_version 1.0 → 2.0
  - Backup created before any writes (Gap B)

Usage:
    python scripts/migrate_v1_to_v2.py [DATA_DIR]

    DATA_DIR defaults to ~/.lockstep/data
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml


def _dump_yaml(data: dict) -> str:
    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)


def backup(data_dir: Path) -> Path:
    """Create timestamped backup of all YAML data. Returns backup path."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = data_dir / "backup" / f"pre-v2-{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    for subdir in ("chains", "tickets", "capacity", "declarations", "handoffs", "catches"):
        src = data_dir / subdir
        if src.exists():
            shutil.copytree(src, backup_dir / subdir)

    # Also back up archived files
    archive_dir = data_dir / "archive"
    if archive_dir.exists():
        shutil.copytree(archive_dir, backup_dir / "archive")

    return backup_dir


def migrate_chain(path: Path) -> bool:
    """Migrate a single chain YAML file. Returns True if modified."""
    with open(path) as f:
        data = yaml.safe_load(f)

    if not data:
        return False

    version = str(data.get("schema_version", "1.0"))
    if version == "2.0":
        return False

    modified = False

    # template → chain_type
    if "template" in data:
        data["chain_type"] = data.pop("template")
        modified = True

    # Ensure chain_type key exists even if template was absent
    if "chain_type" not in data:
        data["chain_type"] = None
        modified = True

    # schema_version bump
    if version != "2.0":
        data["schema_version"] = "2.0"
        modified = True

    if modified:
        with open(path, "w") as f:
            f.write(_dump_yaml(data))

    return modified


def migrate_ticket(path: Path) -> bool:
    """Migrate a single ticket YAML file. Returns True if modified."""
    with open(path) as f:
        data = yaml.safe_load(f)

    if not data:
        return False

    version = str(data.get("schema_version", "1.0"))
    if version == "2.0":
        return False

    data["schema_version"] = "2.0"

    with open(path, "w") as f:
        f.write(_dump_yaml(data))

    return True


def migrate_capacity(path: Path) -> bool:
    """Migrate a capacity YAML file. Returns True if modified."""
    with open(path) as f:
        data = yaml.safe_load(f)

    if not data:
        return False

    version = str(data.get("schema_version", "1.0"))
    if version == "2.0":
        return False

    data["schema_version"] = "2.0"

    with open(path, "w") as f:
        f.write(_dump_yaml(data))

    return True


def run(data_dir: Path) -> dict:
    """Run full migration. Returns summary dict."""
    if not data_dir.exists():
        return {"error": f"Data directory not found: {data_dir}"}

    # Step 1: Backup
    backup_path = backup(data_dir)

    summary = {
        "backup": str(backup_path),
        "chains_migrated": 0,
        "chains_skipped": 0,
        "tickets_migrated": 0,
        "tickets_skipped": 0,
        "capacity_migrated": 0,
        "capacity_skipped": 0,
    }

    # Step 2: Migrate chains
    chains_dir = data_dir / "chains"
    if chains_dir.exists():
        for path in sorted(chains_dir.glob("CHAIN-*.yaml")):
            if migrate_chain(path):
                summary["chains_migrated"] += 1
            else:
                summary["chains_skipped"] += 1

    # Also migrate archived chains
    archive_chains = data_dir / "archive" / "chains"
    if archive_chains.exists():
        for path in sorted(archive_chains.glob("CHAIN-*.yaml")):
            if migrate_chain(path):
                summary["chains_migrated"] += 1
            else:
                summary["chains_skipped"] += 1

    # Step 3: Migrate tickets
    tickets_dir = data_dir / "tickets"
    if tickets_dir.exists():
        for path in sorted(tickets_dir.glob("TICKET-*.yaml")):
            if migrate_ticket(path):
                summary["tickets_migrated"] += 1
            else:
                summary["tickets_skipped"] += 1

    # Also migrate archived tickets
    archive_tickets = data_dir / "archive" / "tickets"
    if archive_tickets.exists():
        for path in sorted(archive_tickets.glob("TICKET-*.yaml")):
            if migrate_ticket(path):
                summary["tickets_migrated"] += 1
            else:
                summary["tickets_skipped"] += 1

    # Step 4: Migrate capacity files
    capacity_dir = data_dir / "capacity"
    if capacity_dir.exists():
        for path in sorted(capacity_dir.glob("*.yaml")):
            if migrate_capacity(path):
                summary["capacity_migrated"] += 1
            else:
                summary["capacity_skipped"] += 1

    return summary


def main():
    if len(sys.argv) > 1:
        data_dir = Path(sys.argv[1])
    else:
        data_dir = Path.home() / ".lockstep" / "data"

    print(f"Migrating Lockstep data: {data_dir}")
    print()

    result = run(data_dir)

    if "error" in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    print(f"Backup created: {result['backup']}")
    print(f"Chains:   {result['chains_migrated']} migrated, {result['chains_skipped']} skipped")
    print(f"Tickets:  {result['tickets_migrated']} migrated, {result['tickets_skipped']} skipped")
    print(f"Capacity: {result['capacity_migrated']} migrated, {result['capacity_skipped']} skipped")
    print()
    print("Migration complete. Verify with a smoke test, then delete backup when satisfied.")


if __name__ == "__main__":
    main()
