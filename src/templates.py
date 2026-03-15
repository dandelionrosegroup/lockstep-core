# Lockstep Chain Protocol — chain type template system
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

"""Chain type template system — YAML-defined chain types.

Templates live in templates/ and define:
  - Phase sequences (what session types a chain walks through)
  - Autonomous eligibility (can AI work proceed without human review?)
  - Required/optional fields for chain creation
  - Progressive disclosure rules (which fields surface at each phase)

No code change required to add new chain types — just drop a YAML file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field


# --- Template Schema ---


class PhaseDisclosure(BaseModel):
    """Progressive disclosure config for a single phase."""
    show: list[str] = Field(default_factory=list)
    prompt: Optional[str] = None


class ChainTypeTemplate(BaseModel):
    """Schema for a chain type template YAML file."""
    chain_type: str
    display_name: str
    phases: list[str]
    autonomous_eligible: bool = False
    required_fields: list[str] = Field(default_factory=list)
    optional_fields: list[str] = Field(default_factory=list)
    progressive_disclosure: dict[str, PhaseDisclosure] = Field(default_factory=dict)


# --- Template Registry ---

# Module-level cache: populated by load_templates(), cleared by reload_templates()
_registry: dict[str, ChainTypeTemplate] = {}
_templates_dir: Optional[Path] = None


def _find_templates_dir() -> Path:
    """Locate the templates/ directory relative to the package root."""
    return Path(__file__).resolve().parent.parent / "templates"


def load_templates(templates_dir: Optional[Path] = None) -> dict[str, ChainTypeTemplate]:
    """Load all template YAML files into the registry.

    Called at server startup. Returns the populated registry.
    """
    global _registry, _templates_dir

    _templates_dir = templates_dir or _find_templates_dir()
    _registry.clear()

    if not _templates_dir.exists():
        return _registry

    for path in sorted(_templates_dir.glob("*.yaml")):
        template = _load_single(path)
        if template:
            _registry[template.chain_type] = template

    return _registry


def reload_templates() -> dict[str, ChainTypeTemplate]:
    """Reload templates from disk (e.g. after adding a new one)."""
    return load_templates(_templates_dir)


def _load_single(path: Path) -> Optional[ChainTypeTemplate]:
    """Load and validate a single template file."""
    with open(path) as f:
        data = yaml.safe_load(f)

    if not data:
        return None

    # Parse progressive_disclosure sub-objects
    pd_raw = data.get("progressive_disclosure", {})
    pd_parsed = {}
    for phase_name, phase_data in pd_raw.items():
        if isinstance(phase_data, dict):
            pd_parsed[phase_name] = PhaseDisclosure(**phase_data)

    data["progressive_disclosure"] = pd_parsed

    return ChainTypeTemplate(**data)


# --- Query Functions ---


def get_template(chain_type: str) -> Optional[ChainTypeTemplate]:
    """Get a loaded template by chain_type identifier."""
    return _registry.get(chain_type)


def list_templates() -> list[ChainTypeTemplate]:
    """List all loaded templates."""
    return list(_registry.values())


def get_sequence(chain_type: str) -> Optional[list[str]]:
    """Get the phase sequence for a chain type. Returns None if unknown."""
    template = _registry.get(chain_type)
    return template.phases if template else None


def is_autonomous_eligible(chain_type: str) -> bool:
    """Check if a chain type is autonomous-eligible."""
    template = _registry.get(chain_type)
    return template.autonomous_eligible if template else False


# --- Validation ---


def validate_template(data: dict[str, Any]) -> list[str]:
    """Validate a template dict. Returns list of error messages (empty = valid).

    Called at startup for each template and on any template CRUD operation.
    """
    errors = []

    if not data.get("chain_type"):
        errors.append("chain_type is required")

    if not data.get("display_name"):
        errors.append("display_name is required")

    phases = data.get("phases")
    if not phases or not isinstance(phases, list):
        errors.append("phases must be a non-empty list")
    elif len(phases) != len(set(phases)):
        errors.append("phases must not contain duplicates")

    # Progressive disclosure phases must be subset of defined phases
    pd = data.get("progressive_disclosure", {})
    if phases and isinstance(phases, list):
        for pd_phase in pd:
            if pd_phase not in phases:
                errors.append(
                    f"progressive_disclosure references unknown phase '{pd_phase}'"
                )

    # Validate show lists reference known field names
    known_fields = {
        "completion_vision", "entity", "tags", "capacity_role",
        "parent_chain", "child_chains", "child_tickets", "spawn_reason",
        "expected_sequence", "links", "gate_skips", "all",
    }
    for pd_phase, pd_config in pd.items():
        if isinstance(pd_config, dict):
            show = pd_config.get("show", [])
        elif isinstance(pd_config, PhaseDisclosure):
            show = pd_config.show
        else:
            continue

        for field in show:
            if field != "all" and field not in known_fields:
                errors.append(
                    f"progressive_disclosure.{pd_phase}.show references unknown field '{field}'"
                )

    return errors


def validate_all_templates() -> dict[str, list[str]]:
    """Validate all loaded templates. Returns {chain_type: [errors]} for any failures."""
    failures = {}
    for chain_type, template in _registry.items():
        errs = validate_template(template.model_dump())
        if errs:
            failures[chain_type] = errs
    return failures
