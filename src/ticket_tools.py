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

"""Ticket lifecycle tools (6 tools).

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
from schemas import Ticket, TicketNote, TicketStatus
from storage import (
    get_data_dir,
    next_ticket_number,
    read_chain,
    read_ticket,
    ticket_path,
    write_ticket,
)
from tool_inputs import (
    CloseTicketInput,
    CreateTicketInput,
    LinkTicketChainInput,
    ReadTicketInput,
    TagTicketInput,
    UpdateTicketInput,
)


def register_ticket_tools(mcp):
    """Register all 6 ticket lifecycle tools on the FastMCP instance."""

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

        return success_response({
            "ticket_id": ticket.ticket_id,
            "updated_fields": updated_fields,
        })

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

        return success_response({
            "ticket_id": ticket.ticket_id,
            "tags": ticket.tags,
            "added": added,
            "removed": removed,
        })

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
        """Associate a ticket with a chain. Usually automatic at chain creation."""
        data_dir = get_data_dir(ctx)
        try:
            ticket = read_ticket(data_dir, params.ticket_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Ticket '{params.ticket_id}' not found"
            )

        # Look up chain status for denormalized field
        chain_status = None
        try:
            chain = read_chain(data_dir, params.chain_id)
            chain_status = chain.status.value
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{params.chain_id}' not found"
            )

        ticket.chain_id = params.chain_id
        ticket.chain_status = chain_status
        write_ticket(data_dir, ticket)

        return success_response({
            "ticket_id": ticket.ticket_id,
            "chain_id": params.chain_id,
            "chain_status": chain_status,
        })
