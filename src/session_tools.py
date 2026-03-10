# Lockstep Chain Protocol — session support tools
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

"""Session support tools (4 tools).

Protocol telemetry — creates the data trail that makes the advisory
model work. Catch events firing = system working, not failure.
"""

from __future__ import annotations

from datetime import date, datetime

import yaml
from mcp.server.fastmcp import Context

from errors import (
    INVALID_STATE,
    IO_ERROR,
    NOT_FOUND,
    error_response,
    success_response,
)
from schemas import (
    CatchEvent,
    ChainLinkStatus,
    ChainStatus,
    FileChange,
    GateSkip,
    Handoff,
    NextSession,
    SessionDeclaration,
)
from storage import get_data_dir, read_chain, write_chain
from tool_inputs import (
    RecordCatchEventInput,
    RecordGateSkipInput,
    RecordHandoffInput,
    RecordSessionDeclarationInput,
)


def _dump_yaml(data: dict) -> str:
    """Serialize dict to YAML string with consistent formatting."""
    return yaml.dump(
        data, default_flow_style=False, sort_keys=False, allow_unicode=True
    )


def register_session_tools(mcp):
    """Register all 4 session support tools on the FastMCP instance."""

    @mcp.tool(
        name="record_session_declaration",
        annotations={
            "title": "Record Session Declaration",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def record_session_declaration(
        params: RecordSessionDeclarationInput, ctx: Context
    ) -> str:
        """Write Session Declaration to current chain link.

        6 components: type, goal, deliverable, completion criteria,
        out of scope, partner confirm.
        """
        data_dir = get_data_dir(ctx)

        try:
            chain = read_chain(data_dir, params.chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{params.chain_id}' not found"
            )

        if chain.status == ChainStatus.ARCHIVED:
            return error_response(
                INVALID_STATE, "Cannot record declaration on archived chain"
            )

        # Find or create active link
        active_link = None
        for link in chain.links:
            if link.status == ChainLinkStatus.ACTIVE:
                active_link = link
                break

        link_number = active_link.link_number if active_link else len(chain.links) + 1

        declaration = SessionDeclaration(
            chain_id=params.chain_id,
            link_number=link_number,
            session_type=params.session_type,
            goal=params.goal,
            deliverable=params.deliverable,
            completion_criteria=params.completion_criteria,
            out_of_scope=params.out_of_scope,
            partner_confirmed=True,
            context_from_previous=params.context_from_previous,
            timestamp=datetime.now(),
        )

        # Write declaration file to data directory
        decl_dir = data_dir / "declarations"
        decl_dir.mkdir(parents=True, exist_ok=True)
        decl_path = decl_dir / f"{params.chain_id}-link-{link_number:02d}-declaration.yaml"

        try:
            with open(decl_path, "w") as f:
                f.write(_dump_yaml(
                    declaration.model_dump(mode="json", exclude_none=True)
                ))
        except OSError as e:
            return error_response(IO_ERROR, f"Failed to write declaration: {e}")

        return success_response({
            "chain_id": params.chain_id,
            "link_number": link_number,
            "session_type": params.session_type,
            "declaration_path": str(decl_path),
            "partner_confirmed": True,
        })

    @mcp.tool(
        name="record_handoff",
        annotations={
            "title": "Record Handoff",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def record_handoff(params: RecordHandoffInput, ctx: Context) -> str:
        """Write session-end handoff to chain link and data directory.

        Captures decisions, files changed, open threads, emotional context,
        and next-session recommendation.
        """
        data_dir = get_data_dir(ctx)

        try:
            chain = read_chain(data_dir, params.chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{params.chain_id}' not found"
            )

        # Determine link number from current active link
        active_link = None
        for link in chain.links:
            if link.status == ChainLinkStatus.ACTIVE:
                active_link = link
                break

        link_number = active_link.link_number if active_link else len(chain.links)

        # Build file_changes list from dicts
        file_changes = []
        for fc in params.files_changed:
            file_changes.append(FileChange(
                path=fc.get("path", ""),
                action=fc.get("action", "modified"),
            ))

        handoff = Handoff(
            chain_id=params.chain_id,
            link_number=link_number,
            session_type=params.session_type,
            status=params.status,
            date=date.today(),
            decisions_made=params.decisions_made,
            files_changed=file_changes,
            tickets_spawned=params.tickets_spawned,
            tickets_updated=params.tickets_updated,
            open_threads=params.open_threads,
            next_session=NextSession(
                recommended_type=params.recommended_next_type,
                quick_start=params.quick_start,
            ),
            context_for_next_partner=params.context_for_next_partner,
            emotional_context=params.emotional_context,
        )

        # Write handoff file
        handoff_dir = data_dir / "handoffs"
        handoff_dir.mkdir(parents=True, exist_ok=True)
        handoff_path = handoff_dir / f"{params.chain_id}-link-{link_number:02d}-handoff.yaml"

        try:
            with open(handoff_path, "w") as f:
                f.write(_dump_yaml(
                    handoff.model_dump(mode="json", exclude_none=True)
                ))
        except OSError as e:
            return error_response(IO_ERROR, f"Failed to write handoff: {e}")

        # Update chain link with handoff reference
        if active_link:
            active_link.handoff = str(handoff_path)
            chain.updated = date.today()
            write_chain(data_dir, chain)

        return success_response({
            "chain_id": params.chain_id,
            "link_number": link_number,
            "status": params.status.value,
            "handoff_path": str(handoff_path),
        })

    @mcp.tool(
        name="record_gate_skip",
        annotations={
            "title": "Record Gate Skip",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def record_gate_skip(
        params: RecordGateSkipInput, ctx: Context
    ) -> str:
        """Log session-type leapfrog in chain metadata (Design Principle 1).

        Partner flags, explains cost, asks — never refuses. The skip is
        recorded to enable pattern detection over time.
        """
        data_dir = get_data_dir(ctx)

        try:
            chain = read_chain(data_dir, params.chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{params.chain_id}' not found"
            )

        skip = GateSkip(
            timestamp=datetime.now(),
            skipped_from=params.skipped_from,
            skipped_to=params.skipped_to,
            reason=params.reason,
            partner_assessment=params.partner_assessment,
        )

        chain.gate_skips.append(skip)
        chain.updated = date.today()
        write_chain(data_dir, chain)

        return success_response({
            "chain_id": chain.chain_id,
            "skipped_from": params.skipped_from,
            "skipped_to": params.skipped_to,
            "total_skips": len(chain.gate_skips),
        })

    @mcp.tool(
        name="record_catch_event",
        annotations={
            "title": "Record Catch Event",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def record_catch_event(
        params: RecordCatchEventInput, ctx: Context
    ) -> str:
        """Log Catch firing with qualitative capture.

        Catch events firing = system working, not failure. The metric is
        whether catches lead to better decisions, not whether they stop.
        human_reasoning is optional but gold when present.
        """
        data_dir = get_data_dir(ctx)

        # Validate chain exists
        try:
            chain = read_chain(data_dir, params.chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{params.chain_id}' not found"
            )

        catch = CatchEvent(
            timestamp=datetime.now(),
            trigger=params.trigger,
            session_type=params.session_type,
            chain_id=params.chain_id,
            action_taken=params.action_taken,
            human_reasoning=params.human_reasoning,
            partner_assessment=params.partner_assessment,
            assessment_note=params.assessment_note,
        )

        # Write catch event to data directory (append-only log)
        catch_dir = data_dir / "catches"
        catch_dir.mkdir(parents=True, exist_ok=True)

        # Filename: chain-id-catch-YYYYMMDD-HHMMSS.yaml
        ts = catch.timestamp.strftime("%Y%m%d-%H%M%S")
        catch_path = catch_dir / f"{params.chain_id}-catch-{ts}.yaml"

        try:
            with open(catch_path, "w") as f:
                f.write(_dump_yaml(
                    catch.model_dump(mode="json", exclude_none=True)
                ))
        except OSError as e:
            return error_response(IO_ERROR, f"Failed to write catch event: {e}")

        return success_response({
            "chain_id": params.chain_id,
            "trigger": params.trigger.value,
            "action_taken": params.action_taken.value,
            "partner_assessment": params.partner_assessment.value,
            "catch_path": str(catch_path),
        })
