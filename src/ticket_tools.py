# Lockstep Chain Protocol — ticket lifecycle tools
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

"""Ticket lifecycle tools (7 tools).

All tools return structured JSON, never prose.
Advisory checks per Design Principle 1 (flag, don't block).
"""

from __future__ import annotations

from datetime import date

from mcp.server.fastmcp import Context

from errors import (
    INVALID_STATE,
    IO_ERROR,
    NOT_FOUND,
    error_response,
    success_response,
)
from schemas import Chain, ChainLink, Ticket, TicketNote, TicketStatus, TicketType
from storage import (
    chain_path,
    get_data_dir,
    list_ticket_files,
    next_ticket_number,
    read_chain,
    read_ticket,
    ticket_path,
    to_kebab_case,
    write_chain,
    write_ticket,
)
from templates import get_sequence
from tool_inputs import (
    CloseTicketInput,
    CreateTicketInput,
    LinkTicketChainInput,
    PromoteTicketInput,
    ReadTicketInput,
    TagTicketInput,
    UpdateTicketInput,
)


# --- Ticket type → chain type (same mapping as commands.py) ---

_TICKET_TYPE_TO_CHAIN_TYPE = {
    TicketType.NEW_INITIATIVE: "full-funnel",
    TicketType.ENHANCEMENT: "enhancement",
    TicketType.REFACTOR: "refactor",
    TicketType.BUG_FIX: "bug-fix",
}

_CHAIN_TYPE_TO_FIRST_SESSION = {
    "full-funnel": "discovery",
    "enhancement": "planning",
    "refactor": "architecture",
    "bug-fix": "build",
}


def _promotion_nudge(ticket: Ticket, data_dir) -> dict | None:
    """Advisory nudge: suggest promotion when ticket shows chain-worthy signals.

    Triggers (Decision 1):
      - 3+ notes accumulated
      - Linked to 2+ other tickets (shares entity + overlapping tags)
    """
    if ticket.chain_id:
        return None  # Already in a chain

    if ticket.type == TicketType.MAINTENANCE:
        return None  # Maintenance tickets don't promote to chains

    reasons = []

    # Signal 1: note accumulation
    if len(ticket.notes) >= 3:
        reasons.append(f"Ticket has {len(ticket.notes)} notes — growing complexity")

    # Signal 2: related tickets (same entity + overlapping tags)
    if ticket.entity and ticket.tags:
        related_count = 0
        try:
            for path in list_ticket_files(data_dir):
                other = read_ticket(data_dir, path.stem)
                if other.ticket_id == ticket.ticket_id:
                    continue
                if other.entity == ticket.entity and set(other.tags) & set(ticket.tags):
                    related_count += 1
                    if related_count >= 2:
                        break
        except Exception:
            pass  # Best-effort scan

        if related_count >= 2:
            reasons.append(f"Linked to {related_count}+ tickets with shared entity+tags")

    if not reasons:
        return None

    chain_type = _TICKET_TYPE_TO_CHAIN_TYPE.get(ticket.type)
    return {
        "suggestion": "This ticket may benefit from Lockstep chain tracking.",
        "reasons": reasons,
        "suggested_chain_type": chain_type,
        "action": f"Use promote_ticket to create a chain from {ticket.ticket_id}",
    }


def register_ticket_tools(mcp):
    """Register all 7 ticket lifecycle tools on the FastMCP instance."""

    @mcp.tool(
        name="create_ticket",
        annotations={
            "title": "Create Ticket",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def create_ticket(params: CreateTicketInput, ctx: Context) -> str:
        """Create a new ticket with auto-assigned sequential ID."""
        data_dir = get_data_dir(ctx)

        ticket_id = next_ticket_number(data_dir)
        today = date.today()

        ticket = Ticket(
            ticket_id=ticket_id,
            title=params.title,
            type=params.type,
            created=today,
            entity=params.entity,
            priority=params.priority,
            tags=params.tags,
            description=params.description,
        )

        try:
            write_ticket(data_dir, ticket)
        except OSError as e:
            return error_response(IO_ERROR, f"Failed to write ticket: {e}")

        return success_response(ticket.model_dump(mode="json", exclude_none=True))

    @mcp.tool(
        name="read_ticket",
        annotations={
            "title": "Read Ticket",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def read_ticket_tool(params: ReadTicketInput, ctx: Context) -> str:
        """Read full ticket state."""
        data_dir = get_data_dir(ctx)
        try:
            ticket = read_ticket(data_dir, params.ticket_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Ticket '{params.ticket_id}' not found"
            )
        return success_response(ticket.model_dump(mode="json", exclude_none=True))

    @mcp.tool(
        name="update_ticket",
        annotations={
            "title": "Update Ticket",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def update_ticket(params: UpdateTicketInput, ctx: Context) -> str:
        """Update ticket metadata and/or append a note."""
        data_dir = get_data_dir(ctx)
        try:
            ticket = read_ticket(data_dir, params.ticket_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Ticket '{params.ticket_id}' not found"
            )

        updated_fields = []
        if params.priority is not None:
            ticket.priority = params.priority
            updated_fields.append("priority")
        if params.entity is not None:
            ticket.entity = params.entity
            updated_fields.append("entity")
        if params.description is not None:
            ticket.description = params.description
            updated_fields.append("description")

        if params.note:
            ticket.notes.append(
                TicketNote(timestamp=date.today(), content=params.note)
            )
            updated_fields.append("notes")

        write_ticket(data_dir, ticket)

        result = {
            "ticket_id": ticket.ticket_id,
            "updated_fields": updated_fields,
        }

        # Advisory nudge (Task 2b)
        nudge = _promotion_nudge(ticket, data_dir)
        if nudge:
            result["promotion_nudge"] = nudge

        return success_response(result)

    @mcp.tool(
        name="close_ticket",
        annotations={
            "title": "Close Ticket",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def close_ticket(params: CloseTicketInput, ctx: Context) -> str:
        """Close ticket. Advisory: flags if associated chain is incomplete."""
        data_dir = get_data_dir(ctx)
        try:
            ticket = read_ticket(data_dir, params.ticket_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Ticket '{params.ticket_id}' not found"
            )

        # Idempotent
        if ticket.status == TicketStatus.CLOSED:
            return success_response({
                "ticket_id": ticket.ticket_id,
                "status": "closed",
                "changed": False,
            })

        # Advisory check: chain status (Design Principle 1)
        advisories = []
        if ticket.chain_id:
            try:
                chain = read_chain(data_dir, ticket.chain_id)
                from schemas import ChainStatus

                if chain.status not in (ChainStatus.COMPLETE, ChainStatus.ARCHIVED):
                    advisories.append(
                        f"Associated chain '{ticket.chain_id}' is still {chain.status.value}"
                    )
            except FileNotFoundError:
                advisories.append(
                    f"Associated chain '{ticket.chain_id}' not found"
                )

        ticket.status = TicketStatus.CLOSED
        ticket.closed = date.today()
        write_ticket(data_dir, ticket)

        result = {
            "ticket_id": ticket.ticket_id,
            "status": "closed",
            "changed": True,
        }
        if advisories:
            result["advisories"] = advisories

        return success_response(result)

    @mcp.tool(
        name="tag_ticket",
        annotations={
            "title": "Tag Ticket",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def tag_ticket(params: TagTicketInput, ctx: Context) -> str:
        """Add or remove tags on a ticket."""
        data_dir = get_data_dir(ctx)
        try:
            ticket = read_ticket(data_dir, params.ticket_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Ticket '{params.ticket_id}' not found"
            )

        added = []
        removed = []

        for tag in params.add:
            if tag not in ticket.tags:
                ticket.tags.append(tag)
                added.append(tag)

        for tag in params.remove:
            if tag in ticket.tags:
                ticket.tags.remove(tag)
                removed.append(tag)

        if added or removed:
            write_ticket(data_dir, ticket)

        result = {
            "ticket_id": ticket.ticket_id,
            "tags": ticket.tags,
            "added": added,
            "removed": removed,
        }

        # Advisory nudge (Task 2b)
        nudge = _promotion_nudge(ticket, data_dir)
        if nudge:
            result["promotion_nudge"] = nudge

        return success_response(result)

    @mcp.tool(
        name="link_ticket_chain",
        annotations={
            "title": "Link Ticket to Chain",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def link_ticket_chain(
        params: LinkTicketChainInput, ctx: Context
    ) -> str:
        """Associate a ticket with a chain.

        If the chain already has an origin ticket (ticket_id) and the linked
        ticket is different, the ticket is added as a child_ticket (Decision 2).
        """
        data_dir = get_data_dir(ctx)
        try:
            ticket = read_ticket(data_dir, params.ticket_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Ticket '{params.ticket_id}' not found"
            )

        try:
            chain = read_chain(data_dir, params.chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{params.chain_id}' not found"
            )

        ticket.chain_id = params.chain_id
        ticket.chain_status = chain.status.value
        write_ticket(data_dir, ticket)

        # Child ticket management (Task 2c): if this isn't the origin ticket,
        # add to child_tickets list
        is_child = ticket.ticket_id != chain.ticket_id
        if is_child and ticket.ticket_id not in chain.child_tickets:
            chain.child_tickets.append(ticket.ticket_id)
            chain.updated = date.today()
            write_chain(data_dir, chain)

        return success_response({
            "ticket_id": ticket.ticket_id,
            "chain_id": params.chain_id,
            "chain_status": chain.status.value,
            "is_child_ticket": is_child,
        })

    @mcp.tool(
        name="promote_ticket",
        annotations={
            "title": "Promote Ticket to Chain",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def promote_ticket(params: PromoteTicketInput, ctx: Context) -> str:
        """Promote a standalone ticket into a chain (Decision 1).

        Creates a chain from the ticket, scans for related tickets
        (same entity + overlapping tags), and returns candidates for
        nesting. Optionally nests specified tickets immediately.
        """
        from errors import ALREADY_EXISTS

        data_dir = get_data_dir(ctx)

        # 1. Read and validate ticket
        try:
            ticket = read_ticket(data_dir, params.ticket_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Ticket '{params.ticket_id}' not found"
            )

        if ticket.chain_id:
            return error_response(
                ALREADY_EXISTS,
                f"Ticket '{params.ticket_id}' is already linked to chain '{ticket.chain_id}'",
                "Read the existing chain or create a new ticket for a separate chain",
            )

        if ticket.status == TicketStatus.CLOSED:
            return error_response(
                INVALID_STATE,
                f"Cannot promote closed ticket '{params.ticket_id}'",
            )

        # 2. Determine chain type
        chain_type = params.chain_type or _TICKET_TYPE_TO_CHAIN_TYPE.get(ticket.type)
        if not chain_type:
            return error_response(
                INVALID_STATE,
                f"No chain type mapping for ticket type '{ticket.type.value}'. Provide chain_type explicitly.",
            )

        sequence = get_sequence(chain_type) or []
        first_session = _CHAIN_TYPE_TO_FIRST_SESSION.get(chain_type, sequence[0] if sequence else "build")

        # 3. Create chain
        chain_id = to_kebab_case(ticket.title)
        if chain_path(data_dir, chain_id).exists():
            return error_response(
                ALREADY_EXISTS,
                f"Chain '{chain_id}' already exists",
                "Use a different ticket title or rename the existing chain",
            )

        today = date.today()
        chain = Chain(
            chain_id=chain_id,
            title=ticket.title,
            ticket_id=params.ticket_id,
            created=today,
            updated=today,
            completion_vision=params.completion_vision,
            chain_type=chain_type,
            expected_sequence=sequence,
            entity=ticket.entity,
            links=[ChainLink(
                link_number=1,
                session_type=first_session,
                started=today,
            )],
        )

        # 4. Link origin ticket
        ticket.chain_id = chain_id
        ticket.chain_status = chain.status.value
        if ticket.status == TicketStatus.OPEN:
            ticket.status = TicketStatus.ACTIVE

        # 5. Nest requested tickets immediately
        nested = []
        nest_errors = []
        for nest_id in params.nest_tickets:
            try:
                child = read_ticket(data_dir, nest_id)
                if child.chain_id:
                    nest_errors.append(f"{nest_id}: already linked to {child.chain_id}")
                    continue
                child.chain_id = chain_id
                child.chain_status = chain.status.value
                write_ticket(data_dir, child)
                chain.child_tickets.append(nest_id)
                nested.append(nest_id)
            except FileNotFoundError:
                nest_errors.append(f"{nest_id}: not found")

        # 6. Write chain and origin ticket
        try:
            write_chain(data_dir, chain)
            write_ticket(data_dir, ticket)
        except OSError as e:
            return error_response(IO_ERROR, f"Failed to write: {e}")

        # 7. Scan for candidates (same entity + overlapping tags)
        candidates = []
        already_nested = {params.ticket_id} | set(params.nest_tickets)
        if ticket.entity or ticket.tags:
            for path in list_ticket_files(data_dir):
                try:
                    other = read_ticket(data_dir, path.stem)
                except Exception:
                    continue

                if other.ticket_id in already_nested:
                    continue
                if other.chain_id:
                    continue
                if other.status == TicketStatus.CLOSED:
                    continue

                # Match: same entity AND overlapping tags
                entity_match = ticket.entity and other.entity == ticket.entity
                tag_overlap = bool(set(ticket.tags) & set(other.tags)) if ticket.tags else False

                if entity_match and tag_overlap:
                    candidates.append({
                        "ticket_id": other.ticket_id,
                        "title": other.title,
                        "type": other.type.value,
                        "tags": other.tags,
                        "shared_tags": sorted(set(ticket.tags) & set(other.tags)),
                    })

        result = {
            "promoted": True,
            "ticket_id": params.ticket_id,
            "chain_id": chain_id,
            "chain_type": chain_type,
            "first_session": first_session,
            "link_number": 1,
        }

        if nested:
            result["nested_tickets"] = nested
        if nest_errors:
            result["nest_errors"] = nest_errors
        if candidates:
            result["nesting_candidates"] = candidates
            result["candidate_message"] = (
                f"Found {len(candidates)} related ticket(s) that could be nested. "
                "Call promote_ticket again with nest_tickets to confirm, "
                "or use link_ticket_chain for individual tickets."
            )

        result["message"] = (
            f"Ticket promoted to chain '{chain_id}'. "
            f"{first_session.title()} session is active."
        )

        return success_response(result)
