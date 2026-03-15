# Lockstep Chain Protocol — query and search tools
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

"""Query tools (6 tools).

Read-only search and aggregation across all data categories.
get_dashboard is the universal entry point — first tool every session.
check_chain_health always active regardless of capacity_tracking.
"""

from __future__ import annotations

from datetime import date, timedelta

from mcp.server.fastmcp import Context

from errors import NOT_FOUND, error_response, success_response
from schemas import ChainStatus, TicketStatus
from storage import (
    get_data_dir,
    list_capacity_files,
    list_chain_files,
    list_ticket_files,
    read_capacity,
    read_chain,
    read_ticket,
)
from tool_inputs import (
    CheckChainHealthInput,
    GetDashboardInput,
    ListChainsInput,
    ListTicketsInput,
    SearchChainsInput,
    SearchTicketsInput,
)


def register_query_tools(mcp):
    """Register all 6 query tools on the FastMCP instance."""

    @mcp.tool(
        name="search_chains",
        annotations={
            "title": "Search Chains",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def search_chains(params: SearchChainsInput, ctx: Context) -> str:
        """Search chains by entity, status, session type, date range."""
        data_dir = get_data_dir(ctx)
        results = []

        for path in list_chain_files(data_dir):
            chain = read_chain(data_dir, path.stem.replace("CHAIN-", ""))

            if params.entity and chain.entity != params.entity:
                continue
            if params.status and chain.status != params.status:
                continue
            if params.session_type:
                link_types = {link.session_type for link in chain.links}
                if params.session_type not in link_types:
                    continue
            if params.since and chain.created < params.since:
                continue
            if params.before and chain.created > params.before:
                continue

            results.append({
                "chain_id": chain.chain_id,
                "title": chain.title,
                "status": chain.status.value,
                "entity": chain.entity,
                "created": str(chain.created),
                "link_count": len(chain.links),
                "chain_type": chain.chain_type,
            })

        return success_response({"count": len(results), "chains": results})

    @mcp.tool(
        name="list_chains",
        annotations={
            "title": "List Chains",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def list_chains(params: ListChainsInput, ctx: Context) -> str:
        """List all active chains (lightweight summary view)."""
        data_dir = get_data_dir(ctx)
        chains = []

        for path in list_chain_files(data_dir):
            chain = read_chain(data_dir, path.stem.replace("CHAIN-", ""))
            if chain.status in (ChainStatus.ARCHIVED,):
                continue

            current_type = None
            if chain.links:
                active = [l for l in chain.links if l.status.value == "active"]
                if active:
                    current_type = active[-1].session_type

            chains.append({
                "chain_id": chain.chain_id,
                "title": chain.title,
                "status": chain.status.value,
                "entity": chain.entity,
                "current_session_type": current_type,
                "link_count": len(chain.links),
                "updated": str(chain.updated),
            })

        return success_response({"count": len(chains), "chains": chains})

    @mcp.tool(
        name="search_tickets",
        annotations={
            "title": "Search Tickets",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def search_tickets(params: SearchTicketsInput, ctx: Context) -> str:
        """Search tickets by type, entity, priority, status."""
        data_dir = get_data_dir(ctx)
        results = []

        for path in list_ticket_files(data_dir):
            ticket = read_ticket(data_dir, path.stem)

            if params.type and ticket.type != params.type:
                continue
            if params.entity and ticket.entity != params.entity:
                continue
            if params.priority and ticket.priority != params.priority:
                continue
            if params.status and ticket.status.value != params.status:
                continue

            results.append({
                "ticket_id": ticket.ticket_id,
                "title": ticket.title,
                "type": ticket.type.value,
                "status": ticket.status.value,
                "priority": ticket.priority.value,
                "entity": ticket.entity,
                "chain_id": ticket.chain_id,
                "created": str(ticket.created),
            })

        return success_response({"count": len(results), "tickets": results})

    @mcp.tool(
        name="list_tickets",
        annotations={
            "title": "List Tickets",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def list_tickets(params: ListTicketsInput, ctx: Context) -> str:
        """List all open tickets."""
        data_dir = get_data_dir(ctx)
        tickets = []

        for path in list_ticket_files(data_dir):
            ticket = read_ticket(data_dir, path.stem)
            if ticket.status == TicketStatus.CLOSED:
                continue

            tickets.append({
                "ticket_id": ticket.ticket_id,
                "title": ticket.title,
                "type": ticket.type.value,
                "status": ticket.status.value,
                "priority": ticket.priority.value,
                "entity": ticket.entity,
                "chain_id": ticket.chain_id,
            })

        return success_response({"count": len(tickets), "tickets": tickets})

    @mcp.tool(
        name="get_dashboard",
        annotations={
            "title": "Get Dashboard",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_dashboard(params: GetDashboardInput, ctx: Context) -> str:
        """Aggregate view: active chains, open tickets, capacity summary, alerts.

        First tool called every session — gives Partner the full operational
        picture in one call.
        """
        data_dir = get_data_dir(ctx)

        # Active chains
        active_chains = []
        stale_chains = []
        today = date.today()
        stale_cutoff = today - timedelta(days=30)

        for path in list_chain_files(data_dir):
            chain = read_chain(data_dir, path.stem.replace("CHAIN-", ""))
            if params.entity and chain.entity != params.entity:
                continue
            if chain.status == ChainStatus.ARCHIVED:
                continue

            current_type = None
            if chain.links:
                active = [l for l in chain.links if l.status.value == "active"]
                if active:
                    current_type = active[-1].session_type

            summary = {
                "chain_id": chain.chain_id,
                "title": chain.title,
                "status": chain.status.value,
                "current_session_type": current_type,
                "link_count": len(chain.links),
                "updated": str(chain.updated),
            }

            if chain.status in (ChainStatus.ACTIVE, ChainStatus.PAUSED, ChainStatus.BLOCKED):
                active_chains.append(summary)

            if chain.updated < stale_cutoff and chain.status != ChainStatus.COMPLETE:
                stale_chains.append({
                    "chain_id": chain.chain_id,
                    "title": chain.title,
                    "days_stale": (today - chain.updated).days,
                    "status": chain.status.value,
                })

        # Open tickets
        open_tickets = []
        for path in list_ticket_files(data_dir):
            ticket = read_ticket(data_dir, path.stem)
            if params.entity and ticket.entity != params.entity:
                continue
            if ticket.status == TicketStatus.CLOSED:
                continue
            open_tickets.append({
                "ticket_id": ticket.ticket_id,
                "title": ticket.title,
                "type": ticket.type.value,
                "priority": ticket.priority.value,
            })

        # Capacity summary
        capacity_summary = []
        stagnation_alerts = []
        for path in list_capacity_files(data_dir):
            cap = read_capacity(data_dir, path.stem)
            capacity_summary.append({
                "role": cap.role,
                "display_name": cap.display_name,
                "stage": cap.current_stage.value,
                "event_ratio": cap.event_ratio.model_dump(mode="json", exclude_none=True),
            })
            if cap.stagnation.current_count >= cap.stagnation.threshold:
                stagnation_alerts.append({
                    "role": cap.role,
                    "stage": cap.current_stage.value,
                    "count": cap.stagnation.current_count,
                    "threshold": cap.stagnation.threshold,
                })

        return success_response({
            "active_chains": active_chains,
            "open_tickets": open_tickets,
            "capacity_summary": capacity_summary,
            "stagnation_alerts": stagnation_alerts,
            "stale_chains": stale_chains,
        })

    @mcp.tool(
        name="check_chain_health",
        annotations={
            "title": "Check Chain Health",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def check_chain_health(
        params: CheckChainHealthInput, ctx: Context
    ) -> str:
        """Detect stagnant/forgotten chains. Always active regardless of capacity_tracking."""
        data_dir = get_data_dir(ctx)
        today = date.today()
        cutoff = today - timedelta(days=params.stale_days)

        stale = []
        blocked = []
        healthy = 0

        for path in list_chain_files(data_dir):
            chain = read_chain(data_dir, path.stem.replace("CHAIN-", ""))
            if chain.status in (ChainStatus.COMPLETE, ChainStatus.ARCHIVED):
                continue

            if chain.status == ChainStatus.BLOCKED:
                blocked.append({
                    "chain_id": chain.chain_id,
                    "title": chain.title,
                    "updated": str(chain.updated),
                })
            elif chain.updated < cutoff:
                stale.append({
                    "chain_id": chain.chain_id,
                    "title": chain.title,
                    "status": chain.status.value,
                    "days_stale": (today - chain.updated).days,
                    "last_updated": str(chain.updated),
                })
            else:
                healthy += 1

        return success_response({
            "healthy_count": healthy,
            "stale": stale,
            "blocked": blocked,
            "stale_threshold_days": params.stale_days,
        })
