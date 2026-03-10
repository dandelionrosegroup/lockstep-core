# Lockstep Chain Protocol — command shortcuts
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

"""Lockstep commands (5) — thin routing layers.

Commands are shortcuts to MCP tool sequences with no independent logic.
The Partner IS the intelligence layer; commands are ergonomics.
An agent (Aule) never uses commands — it calls MCP tools directly.

Stage-adaptive parameter collection is a lockstep-core behavioral
instruction, not per-command logic. The command schema is identical
across stages; the interaction pattern changes.

A1 resolution: /new-ticket includes description parameter.
"""

from __future__ import annotations

from mcp.server.fastmcp import Context

from errors import IO_ERROR, NOT_FOUND, error_response, success_response
from schemas import ChainTemplate, TicketType
from storage import get_data_dir, read_chain, read_ticket


# --- Chain template mapping ---

TEMPLATE_SEQUENCES = {
    ChainTemplate.FULL_FUNNEL: [
        "discovery", "research", "planning", "architecture", "build", "review"
    ],
    ChainTemplate.ENHANCEMENT: ["planning", "architecture", "build", "review"],
    ChainTemplate.REFACTOR: ["architecture", "build", "review"],
    ChainTemplate.BUG_FIX: ["build", "review"],
}

TICKET_TYPE_TO_TEMPLATE = {
    TicketType.NEW_INITIATIVE: ChainTemplate.FULL_FUNNEL,
    TicketType.ENHANCEMENT: ChainTemplate.ENHANCEMENT,
    TicketType.REFACTOR: ChainTemplate.REFACTOR,
    TicketType.BUG_FIX: ChainTemplate.BUG_FIX,
    # maintenance: no template (no chain)
}

TICKET_TYPE_TO_FIRST_SESSION = {
    TicketType.NEW_INITIATIVE: "discovery",
    TicketType.ENHANCEMENT: "planning",
    TicketType.REFACTOR: "architecture",
    TicketType.BUG_FIX: "build",
}


def register_commands(mcp):
    """Register all 5 commands on the FastMCP instance.

    Commands are MCP tools that assemble tool sequences. They appear
    alongside regular tools but are documented as commands in the
    plugin manifest.
    """

    @mcp.tool(
        name="cmd_new_ticket",
        annotations={
            "title": "/new-ticket",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def cmd_new_ticket(
        title: str,
        type: str,
        entity: str | None = None,
        priority: str = "normal",
        tags: list[str] | None = None,
        description: str | None = None,
        ctx: Context = None,
    ) -> str:
        """Create a new ticket. Generic — human specifies everything.

        A1 resolution: includes description parameter.

        If the ticket type triggers Lockstep threshold (not maintenance),
        returns a prompt suggesting chain creation. The Partner handles
        the conversational follow-up.
        """
        from datetime import date

        from schemas import Ticket, TicketPriority, TicketStatus
        from storage import next_ticket_number, write_ticket

        data_dir = get_data_dir(ctx)

        # Resolve enums
        try:
            ticket_type = TicketType(type)
        except ValueError:
            return error_response(
                "validation_error",
                f"Invalid ticket type: {type}",
                "Valid types: new-initiative, enhancement, refactor, bug-fix, maintenance",
            )

        try:
            ticket_priority = TicketPriority(priority)
        except ValueError:
            ticket_priority = TicketPriority.NORMAL

        ticket_id = next_ticket_number(data_dir)
        today = date.today()

        ticket = Ticket(
            ticket_id=ticket_id,
            title=title,
            type=ticket_type,
            created=today,
            entity=entity,
            priority=ticket_priority,
            tags=tags or [],
            description=description,
        )

        try:
            write_ticket(data_dir, ticket)
        except OSError as e:
            return error_response(IO_ERROR, f"Failed to write ticket: {e}")

        result = ticket.model_dump(mode="json", exclude_none=True)

        # Lockstep threshold prompt (not maintenance)
        if ticket_type != TicketType.MAINTENANCE:
            template = TICKET_TYPE_TO_TEMPLATE.get(ticket_type)
            result["lockstep_prompt"] = {
                "message": "This ticket type supports Lockstep chain tracking. Create a chain?",
                "suggested_template": template.value if template else None,
                "suggested_first_session": TICKET_TYPE_TO_FIRST_SESSION.get(ticket_type),
            }

        return success_response(result)

    @mcp.tool(
        name="cmd_new_initiative",
        annotations={
            "title": "/new-initiative",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def cmd_new_initiative(
        title: str,
        vision: str,
        entity: str | None = None,
        ctx: Context = None,
    ) -> str:
        """Create initiative: ticket + full-funnel chain + discovery declaration.

        Pre-typed: full funnel (Discovery -> Research -> Planning ->
        Architecture -> Build -> Review). Starts in Discovery.
        """
        from datetime import date

        from schemas import (
            Chain,
            ChainLink,
            SessionDeclaration,
            Ticket,
            TicketStatus,
        )
        from storage import next_ticket_number, to_kebab_case, write_chain, write_ticket

        data_dir = get_data_dir(ctx)
        today = date.today()

        # 1. Create ticket
        ticket_id = next_ticket_number(data_dir)
        ticket = Ticket(
            ticket_id=ticket_id,
            title=title,
            type=TicketType.NEW_INITIATIVE,
            created=today,
            entity=entity,
            status=TicketStatus.ACTIVE,
        )

        # 2. Create chain
        chain_id = to_kebab_case(title)
        template = ChainTemplate.FULL_FUNNEL
        sequence = TEMPLATE_SEQUENCES[template]

        chain = Chain(
            chain_id=chain_id,
            title=title,
            ticket_id=ticket_id,
            created=today,
            updated=today,
            completion_vision=vision,
            template=template,
            expected_sequence=sequence,
            entity=entity,
            links=[ChainLink(
                link_number=1,
                session_type="discovery",
                started=today,
            )],
        )

        ticket.chain_id = chain_id
        ticket.chain_status = chain.status.value

        try:
            write_ticket(data_dir, ticket)
            write_chain(data_dir, chain)
        except OSError as e:
            return error_response(IO_ERROR, f"Failed to write: {e}")

        return success_response({
            "ticket_id": ticket_id,
            "chain_id": chain_id,
            "template": template.value,
            "first_session": "discovery",
            "link_number": 1,
            "message": "Initiative created. Discovery session is active. Record your session declaration.",
        })

    @mcp.tool(
        name="cmd_enhancement",
        annotations={
            "title": "/enhancement",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def cmd_enhancement(
        title: str,
        vision: str,
        entity: str | None = None,
        ctx: Context = None,
    ) -> str:
        """Create enhancement: ticket + chain + planning declaration.

        Pre-typed: Planning -> Architecture -> Build -> Review.
        Starts in Planning.
        """
        from datetime import date

        from schemas import Chain, ChainLink, Ticket, TicketStatus
        from storage import next_ticket_number, to_kebab_case, write_chain, write_ticket

        data_dir = get_data_dir(ctx)
        today = date.today()

        ticket_id = next_ticket_number(data_dir)
        ticket = Ticket(
            ticket_id=ticket_id,
            title=title,
            type=TicketType.ENHANCEMENT,
            created=today,
            entity=entity,
            status=TicketStatus.ACTIVE,
        )

        chain_id = to_kebab_case(title)
        template = ChainTemplate.ENHANCEMENT
        sequence = TEMPLATE_SEQUENCES[template]

        chain = Chain(
            chain_id=chain_id,
            title=title,
            ticket_id=ticket_id,
            created=today,
            updated=today,
            completion_vision=vision,
            template=template,
            expected_sequence=sequence,
            entity=entity,
            links=[ChainLink(
                link_number=1,
                session_type="planning",
                started=today,
            )],
        )

        ticket.chain_id = chain_id
        ticket.chain_status = chain.status.value

        try:
            write_ticket(data_dir, ticket)
            write_chain(data_dir, chain)
        except OSError as e:
            return error_response(IO_ERROR, f"Failed to write: {e}")

        return success_response({
            "ticket_id": ticket_id,
            "chain_id": chain_id,
            "template": template.value,
            "first_session": "planning",
            "link_number": 1,
            "message": "Enhancement created. Planning session is active. Record your session declaration.",
        })

    @mcp.tool(
        name="cmd_refactor",
        annotations={
            "title": "/refactor",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def cmd_refactor(
        title: str,
        scope: str,
        entity: str | None = None,
        ctx: Context = None,
    ) -> str:
        """Create refactor: ticket + chain + architecture declaration.

        Pre-typed: Architecture -> Build -> Review.
        Starts in Architecture. scope = "what's being refactored and why?"
        """
        from datetime import date

        from schemas import Chain, ChainLink, Ticket, TicketStatus
        from storage import next_ticket_number, to_kebab_case, write_chain, write_ticket

        data_dir = get_data_dir(ctx)
        today = date.today()

        ticket_id = next_ticket_number(data_dir)
        ticket = Ticket(
            ticket_id=ticket_id,
            title=title,
            type=TicketType.REFACTOR,
            created=today,
            entity=entity,
            status=TicketStatus.ACTIVE,
        )

        chain_id = to_kebab_case(title)
        template = ChainTemplate.REFACTOR
        sequence = TEMPLATE_SEQUENCES[template]

        chain = Chain(
            chain_id=chain_id,
            title=title,
            ticket_id=ticket_id,
            created=today,
            updated=today,
            completion_vision=scope,
            template=template,
            expected_sequence=sequence,
            entity=entity,
            links=[ChainLink(
                link_number=1,
                session_type="architecture",
                started=today,
            )],
        )

        ticket.chain_id = chain_id
        ticket.chain_status = chain.status.value

        try:
            write_ticket(data_dir, ticket)
            write_chain(data_dir, chain)
        except OSError as e:
            return error_response(IO_ERROR, f"Failed to write: {e}")

        return success_response({
            "ticket_id": ticket_id,
            "chain_id": chain_id,
            "template": template.value,
            "first_session": "architecture",
            "link_number": 1,
            "message": "Refactor created. Architecture session is active. Record your session declaration.",
        })

    @mcp.tool(
        name="cmd_bug_fix",
        annotations={
            "title": "/bug-fix",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def cmd_bug_fix(
        title: str,
        description: str,
        entity: str | None = None,
        create_chain: bool = False,
        ctx: Context = None,
    ) -> str:
        """Create bug-fix ticket. Optionally creates chain.

        Pre-typed: Build -> Review (optional). Asks before creating chain
        via create_chain parameter. If false, ticket exists for tracking
        but no chain is created.
        """
        from datetime import date

        from schemas import Chain, ChainLink, Ticket, TicketStatus
        from storage import next_ticket_number, to_kebab_case, write_chain, write_ticket

        data_dir = get_data_dir(ctx)
        today = date.today()

        ticket_id = next_ticket_number(data_dir)
        ticket = Ticket(
            ticket_id=ticket_id,
            title=title,
            type=TicketType.BUG_FIX,
            created=today,
            entity=entity,
            description=description,
        )

        result = {
            "ticket_id": ticket_id,
            "title": title,
            "type": "bug-fix",
        }

        if create_chain:
            chain_id = to_kebab_case(title)
            template = ChainTemplate.BUG_FIX
            sequence = TEMPLATE_SEQUENCES[template]

            chain = Chain(
                chain_id=chain_id,
                title=title,
                ticket_id=ticket_id,
                created=today,
                updated=today,
                completion_vision=description,
                template=template,
                expected_sequence=sequence,
                entity=entity,
                links=[ChainLink(
                    link_number=1,
                    session_type="build",
                    started=today,
                )],
            )

            ticket.chain_id = chain_id
            ticket.chain_status = chain.status.value
            ticket.status = TicketStatus.ACTIVE

            try:
                write_ticket(data_dir, ticket)
                write_chain(data_dir, chain)
            except OSError as e:
                return error_response(IO_ERROR, f"Failed to write: {e}")

            result.update({
                "chain_id": chain_id,
                "template": template.value,
                "first_session": "build",
                "link_number": 1,
                "message": "Bug-fix created with chain. Build session is active.",
            })
        else:
            try:
                write_ticket(data_dir, ticket)
            except OSError as e:
                return error_response(IO_ERROR, f"Failed to write ticket: {e}")

            result["message"] = "Bug-fix ticket created. No chain — fix directly."

        return success_response(result)
