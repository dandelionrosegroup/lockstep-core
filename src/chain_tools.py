# Lockstep Chain Protocol — chain lifecycle tools
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

"""Chain lifecycle tools (15 tools).

All tools return structured JSON, never prose.
No-delete policy: archive, never destroy.
Idempotent where specified.
"""

from __future__ import annotations

from datetime import date, datetime

from mcp.server.fastmcp import Context

from errors import (
    ALREADY_EXISTS,
    INVALID_STATE,
    IO_ERROR,
    NOT_FOUND,
    error_response,
    success_response,
)
from schemas import Chain, ChainLink, ChainLinkStatus, ChainStatus
from storage import (
    archive_chain_file,
    chain_path,
    get_data_dir,
    read_chain,
    read_ticket,
    to_kebab_case,
    write_chain,
    write_ticket,
)
from tool_inputs import (
    AddChainLinkInput,
    ArchiveChainInput,
    BranchChainInput,
    CompleteChainInput,
    CompleteChainLinkInput,
    CreateChainInput,
    GetChainStatusInput,
    PauseChainInput,
    ReadChainInput,
    RenameChainInput,
    ResumeChainInput,
    SetChainEntityInput,
    SetChainStatusInput,
    SpawnChildChainInput,
    UpdateChainMetadataInput,
)


def register_chain_tools(mcp):
    """Register all 15 chain lifecycle tools on the FastMCP instance."""

    @mcp.tool(
        name="create_chain",
        annotations={
            "title": "Create Chain",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def create_chain(params: CreateChainInput, ctx: Context) -> str:
        """Create a new chain from a ticket. Generates chain_id from kebab-case title."""
        data_dir = get_data_dir(ctx)
        chain_id = to_kebab_case(params.title)

        if chain_path(data_dir, chain_id).exists():
            return error_response(
                ALREADY_EXISTS,
                f"Chain '{chain_id}' already exists",
                "Use a different title or read the existing chain",
            )

        today = date.today()
        chain = Chain(
            chain_id=chain_id,
            title=params.title,
            ticket_id=params.ticket_id,
            created=today,
            updated=today,
            completion_vision=params.completion_vision,
            chain_type=params.chain_type,
            expected_sequence=params.expected_sequence,
            entity=params.entity,
            created_by=params.created_by,
            capacity_role=params.capacity_role,
        )

        try:
            write_chain(data_dir, chain)
        except OSError as e:
            return error_response(IO_ERROR, f"Failed to write chain: {e}")

        # Link ticket to chain if ticket exists
        try:
            ticket = read_ticket(data_dir, params.ticket_id)
            ticket.chain_id = chain_id
            ticket.chain_status = chain.status.value
            if ticket.status.value == "open":
                from schemas import TicketStatus

                ticket.status = TicketStatus.ACTIVE
            write_ticket(data_dir, ticket)
        except FileNotFoundError:
            pass  # Ticket may not exist yet — not an error

        return success_response(chain.model_dump(mode="json", exclude_none=True))

    @mcp.tool(
        name="read_chain",
        annotations={
            "title": "Read Chain",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def read_chain_tool(params: ReadChainInput, ctx: Context) -> str:
        """Read chain state filtered through progressive disclosure.

        Early-phase chains show fewer fields to reduce cognitive load.
        Full data always accessible via direct YAML read.
        """
        from templates import apply_disclosure

        data_dir = get_data_dir(ctx)
        try:
            chain = read_chain(data_dir, params.chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{params.chain_id}' not found"
            )
        chain_dict = chain.model_dump(mode="json", exclude_none=True)
        disclosed = apply_disclosure(chain_dict)
        return success_response(disclosed)

    @mcp.tool(
        name="get_chain_status",
        annotations={
            "title": "Get Chain Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_chain_status(params: GetChainStatusInput, ctx: Context) -> str:
        """Lightweight status check: current link, phase, health."""
        data_dir = get_data_dir(ctx)
        try:
            chain = read_chain(data_dir, params.chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{params.chain_id}' not found"
            )

        current_link = None
        if chain.links:
            active_links = [l for l in chain.links if l.status == ChainLinkStatus.ACTIVE]
            current_link = active_links[-1].model_dump(mode="json", exclude_none=True) if active_links else None

        return success_response({
            "chain_id": chain.chain_id,
            "title": chain.title,
            "status": chain.status.value,
            "link_count": len(chain.links),
            "current_link": current_link,
            "child_chains": chain.child_chains,
        })

    @mcp.tool(
        name="set_chain_status",
        annotations={
            "title": "Set Chain Status",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def set_chain_status(params: SetChainStatusInput, ctx: Context) -> str:
        """Update chain status with state transition validation."""
        data_dir = get_data_dir(ctx)
        try:
            chain = read_chain(data_dir, params.chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{params.chain_id}' not found"
            )

        # Idempotent: setting same status = no-op
        if chain.status == params.status:
            return success_response({
                "chain_id": chain.chain_id,
                "status": chain.status.value,
                "changed": False,
            })

        # Validate transitions: archived/complete chains can't go back to active
        invalid_from = {ChainStatus.ARCHIVED}
        if chain.status in invalid_from:
            return error_response(
                INVALID_STATE,
                f"Cannot change status from '{chain.status.value}' to '{params.status.value}'",
                "Archived chains cannot be modified",
            )

        old_status = chain.status.value
        chain.status = params.status
        chain.updated = date.today()

        if params.status == ChainStatus.COMPLETE:
            chain.completed = date.today()

        write_chain(data_dir, chain)
        _sync_ticket_chain_status(data_dir, chain)

        return success_response({
            "chain_id": chain.chain_id,
            "previous_status": old_status,
            "status": chain.status.value,
            "changed": True,
        })

    @mcp.tool(
        name="set_chain_entity",
        annotations={
            "title": "Set Chain Entity",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def set_chain_entity(params: SetChainEntityInput, ctx: Context) -> str:
        """Tag chain with entity ownership (which subsidiary)."""
        data_dir = get_data_dir(ctx)
        try:
            chain = read_chain(data_dir, params.chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{params.chain_id}' not found"
            )

        chain.entity = params.entity
        chain.updated = date.today()
        write_chain(data_dir, chain)

        return success_response({
            "chain_id": chain.chain_id,
            "entity": chain.entity,
        })

    @mcp.tool(
        name="update_chain_metadata",
        annotations={
            "title": "Update Chain Metadata",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def update_chain_metadata(
        params: UpdateChainMetadataInput, ctx: Context
    ) -> str:
        """General metadata updates: vision, entity, capacity_role, notes."""
        data_dir = get_data_dir(ctx)
        try:
            chain = read_chain(data_dir, params.chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{params.chain_id}' not found"
            )

        updated_fields = []
        if params.completion_vision is not None:
            chain.completion_vision = params.completion_vision
            updated_fields.append("completion_vision")
        if params.entity is not None:
            chain.entity = params.entity
            updated_fields.append("entity")
        if params.capacity_role is not None:
            chain.capacity_role = params.capacity_role
            updated_fields.append("capacity_role")

        chain.updated = date.today()
        write_chain(data_dir, chain)

        result = {
            "chain_id": chain.chain_id,
            "updated_fields": updated_fields,
        }
        if params.note:
            result["note_recorded"] = params.note

        return success_response(result)

    @mcp.tool(
        name="add_chain_link",
        annotations={
            "title": "Add Chain Link",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def add_chain_link(params: AddChainLinkInput, ctx: Context) -> str:
        """Add a new session link to a chain. Auto-increments link_number."""
        data_dir = get_data_dir(ctx)
        try:
            chain = read_chain(data_dir, params.chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{params.chain_id}' not found"
            )

        if chain.status == ChainStatus.ARCHIVED:
            return error_response(
                INVALID_STATE,
                "Cannot add links to an archived chain",
            )

        next_number = len(chain.links) + 1
        link = ChainLink(
            link_number=next_number,
            session_type=params.session_type,
            started=params.started or date.today(),
            progress_markers=params.progress_markers,
        )
        chain.links.append(link)

        # Resume chain if paused
        if chain.status == ChainStatus.PAUSED:
            chain.status = ChainStatus.ACTIVE

        chain.updated = date.today()
        write_chain(data_dir, chain)
        _sync_ticket_chain_status(data_dir, chain)

        return success_response({
            "chain_id": chain.chain_id,
            "link_number": next_number,
            "session_type": params.session_type,
            "status": chain.status.value,
        })

    @mcp.tool(
        name="complete_chain_link",
        annotations={
            "title": "Complete Chain Link",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def complete_chain_link(
        params: CompleteChainLinkInput, ctx: Context
    ) -> str:
        """Mark a chain link as complete, record deliverables."""
        data_dir = get_data_dir(ctx)
        try:
            chain = read_chain(data_dir, params.chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{params.chain_id}' not found"
            )

        if not chain.links:
            return error_response(
                INVALID_STATE, "Chain has no links to complete"
            )

        # Find the target link
        target = None
        if params.link_number is not None:
            for link in chain.links:
                if link.link_number == params.link_number:
                    target = link
                    break
            if target is None:
                return error_response(
                    NOT_FOUND,
                    f"Link {params.link_number} not found in chain",
                )
        else:
            # Default to the last active link
            active = [l for l in chain.links if l.status == ChainLinkStatus.ACTIVE]
            if not active:
                return error_response(
                    INVALID_STATE, "No active links to complete"
                )
            target = active[-1]

        # Idempotent: already complete = no-op
        if target.status == ChainLinkStatus.COMPLETE:
            return success_response({
                "chain_id": chain.chain_id,
                "link_number": target.link_number,
                "status": "complete",
                "changed": False,
            })

        target.status = ChainLinkStatus.COMPLETE
        target.completed = date.today()
        if params.deliverables:
            target.deliverables = params.deliverables
        if params.handoff:
            target.handoff = params.handoff
        if params.progress_markers:
            target.progress_markers = params.progress_markers

        chain.updated = date.today()
        write_chain(data_dir, chain)

        return success_response({
            "chain_id": chain.chain_id,
            "link_number": target.link_number,
            "status": "complete",
            "changed": True,
        })

    @mcp.tool(
        name="pause_chain",
        annotations={
            "title": "Pause Chain",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def pause_chain(params: PauseChainInput, ctx: Context) -> str:
        """Pause chain — preserves state, signals 'not abandoned'. Idempotent."""
        data_dir = get_data_dir(ctx)
        try:
            chain = read_chain(data_dir, params.chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{params.chain_id}' not found"
            )

        # Idempotent: already paused = no-op
        if chain.status == ChainStatus.PAUSED:
            return success_response({
                "chain_id": chain.chain_id,
                "status": "paused",
                "changed": False,
            })

        if chain.status in (ChainStatus.COMPLETE, ChainStatus.ARCHIVED):
            return error_response(
                INVALID_STATE,
                f"Cannot pause a {chain.status.value} chain",
            )

        chain.status = ChainStatus.PAUSED
        chain.updated = date.today()
        write_chain(data_dir, chain)
        _sync_ticket_chain_status(data_dir, chain)

        return success_response({
            "chain_id": chain.chain_id,
            "status": "paused",
            "changed": True,
        })

    @mcp.tool(
        name="resume_chain",
        annotations={
            "title": "Resume Chain",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def resume_chain(params: ResumeChainInput, ctx: Context) -> str:
        """Resume a paused chain. Only valid from paused state."""
        data_dir = get_data_dir(ctx)
        try:
            chain = read_chain(data_dir, params.chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{params.chain_id}' not found"
            )

        # Idempotent: already active = no-op
        if chain.status == ChainStatus.ACTIVE:
            return success_response({
                "chain_id": chain.chain_id,
                "status": "active",
                "changed": False,
            })

        if chain.status != ChainStatus.PAUSED:
            return error_response(
                INVALID_STATE,
                f"Can only resume paused chains, current status: {chain.status.value}",
            )

        chain.status = ChainStatus.ACTIVE
        chain.updated = date.today()
        write_chain(data_dir, chain)
        _sync_ticket_chain_status(data_dir, chain)

        return success_response({
            "chain_id": chain.chain_id,
            "status": "active",
            "changed": True,
        })

    @mcp.tool(
        name="complete_chain",
        annotations={
            "title": "Complete Chain",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def complete_chain(params: CompleteChainInput, ctx: Context) -> str:
        """Mark entire chain complete. Lifecycle hooks per Decision 1.

        Bug-fix/maintenance chains: auto-close associated ticket.
        Other chain types: advisory suggesting ticket closure.
        """
        from templates import is_autonomous_eligible

        data_dir = get_data_dir(ctx)
        try:
            chain = read_chain(data_dir, params.chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{params.chain_id}' not found"
            )

        # Idempotent
        if chain.status == ChainStatus.COMPLETE:
            return success_response({
                "chain_id": chain.chain_id,
                "status": "complete",
                "changed": False,
            })

        if chain.status == ChainStatus.ARCHIVED:
            return error_response(
                INVALID_STATE, "Cannot complete an archived chain"
            )

        # Advisory check: child chains (Design Principle 1 — flag, don't block)
        advisories = []
        for child_id in chain.child_chains:
            try:
                child = read_chain(data_dir, child_id)
                if child.status not in (ChainStatus.COMPLETE, ChainStatus.ARCHIVED):
                    advisories.append(
                        f"Child chain '{child_id}' is still {child.status.value}"
                    )
            except FileNotFoundError:
                advisories.append(f"Child chain '{child_id}' not found")

        chain.status = ChainStatus.COMPLETE
        chain.completed = date.today()
        chain.updated = date.today()
        write_chain(data_dir, chain)
        _sync_ticket_chain_status(data_dir, chain)

        result = {
            "chain_id": chain.chain_id,
            "status": "complete",
            "changed": True,
        }

        # Lifecycle hooks (Task 3d): auto-close for autonomous types, advisory for others
        auto_close = is_autonomous_eligible(chain.chain_type) if chain.chain_type else False
        if chain.ticket_id:
            try:
                ticket = read_ticket(data_dir, chain.ticket_id)
                if ticket.status.value != "closed":
                    if auto_close:
                        from schemas import TicketStatus
                        ticket.status = TicketStatus.CLOSED
                        ticket.closed = date.today()
                        ticket.chain_status = "complete"
                        write_ticket(data_dir, ticket)
                        result["ticket_auto_closed"] = ticket.ticket_id
                    else:
                        advisories.append(
                            f"Chain complete — consider closing ticket '{ticket.ticket_id}'"
                        )
            except FileNotFoundError:
                pass

        if advisories:
            result["advisories"] = advisories

        return success_response(result)

    @mcp.tool(
        name="archive_chain",
        annotations={
            "title": "Archive Chain",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def archive_chain(params: ArchiveChainInput, ctx: Context) -> str:
        """Move completed chain to archive with retention metadata."""
        data_dir = get_data_dir(ctx)
        try:
            chain = read_chain(data_dir, params.chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{params.chain_id}' not found"
            )

        if chain.status == ChainStatus.ARCHIVED:
            return success_response({
                "chain_id": chain.chain_id,
                "status": "archived",
                "changed": False,
            })

        if chain.status != ChainStatus.COMPLETE:
            return error_response(
                INVALID_STATE,
                f"Only complete chains can be archived, current status: {chain.status.value}",
                "Complete the chain first with complete_chain",
            )

        today = date.today()
        chain.status = ChainStatus.ARCHIVED
        chain.archived = today
        chain.updated = today
        write_chain(data_dir, chain)

        try:
            archive_path = archive_chain_file(data_dir, chain.chain_id, today)
        except (OSError, FileExistsError) as e:
            return error_response(IO_ERROR, f"Archive move failed: {e}")

        # Close associated ticket if open
        if chain.ticket_id:
            try:
                ticket = read_ticket(data_dir, chain.ticket_id)
                if ticket.status.value != "closed":
                    from schemas import TicketStatus

                    ticket.status = TicketStatus.CLOSED
                    ticket.closed = today
                    ticket.chain_status = "archived"
                    write_ticket(data_dir, ticket)
            except FileNotFoundError:
                pass

        return success_response({
            "chain_id": chain.chain_id,
            "status": "archived",
            "archive_path": str(archive_path),
            "changed": True,
        })

    @mcp.tool(
        name="branch_chain",
        annotations={
            "title": "Branch Chain",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def branch_chain(params: BranchChainInput, ctx: Context) -> str:
        """Fork chain when work splits. Parent doesn't complete until all branches do."""
        data_dir = get_data_dir(ctx)
        try:
            parent = read_chain(data_dir, params.parent_chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Parent chain '{params.parent_chain_id}' not found"
            )

        child_id = to_kebab_case(params.title)
        if chain_path(data_dir, child_id).exists():
            return error_response(
                ALREADY_EXISTS,
                f"Chain '{child_id}' already exists",
            )

        today = date.today()
        child = Chain(
            chain_id=child_id,
            title=params.title,
            ticket_id=params.ticket_id or parent.ticket_id,
            created=today,
            updated=today,
            completion_vision=params.completion_vision,
            chain_type=params.chain_type or parent.chain_type,
            spawn_reason=params.spawn_reason,
            entity=parent.entity,
            created_by=parent.created_by,
            parent_chain=parent.chain_id,
            capacity_role=parent.capacity_role,
        )

        write_chain(data_dir, child)

        # Update parent
        parent.child_chains.append(child_id)
        parent.updated = today
        write_chain(data_dir, parent)

        return success_response({
            "parent_chain_id": parent.chain_id,
            "child_chain_id": child_id,
            "child_status": child.status.value,
        })

    @mcp.tool(
        name="spawn_child_chain",
        annotations={
            "title": "Spawn Child Chain",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def spawn_child_chain(
        params: SpawnChildChainInput, ctx: Context
    ) -> str:
        """Fork a chain when work needs a different type (Decision 5).

        Type changes create child chains; parent retains its type and
        history. spawn_reason is required — it's what makes cross-domain
        ideation patterns researchable.
        """
        from templates import get_sequence

        data_dir = get_data_dir(ctx)
        try:
            parent = read_chain(data_dir, params.parent_chain_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Parent chain '{params.parent_chain_id}' not found"
            )

        child_id = to_kebab_case(params.title)
        if chain_path(data_dir, child_id).exists():
            return error_response(
                ALREADY_EXISTS,
                f"Chain '{child_id}' already exists",
            )

        sequence = get_sequence(params.chain_type) or []
        first_session = sequence[0] if sequence else "build"

        today = date.today()
        child = Chain(
            chain_id=child_id,
            title=params.title,
            ticket_id=params.ticket_id or parent.ticket_id,
            created=today,
            updated=today,
            completion_vision=params.completion_vision,
            chain_type=params.chain_type,
            expected_sequence=sequence,
            spawn_reason=params.spawn_reason,
            entity=parent.entity,
            created_by=parent.created_by,
            parent_chain=parent.chain_id,
            capacity_role=parent.capacity_role,
            links=[ChainLink(
                link_number=1,
                session_type=first_session,
                started=today,
            )],
        )

        write_chain(data_dir, child)

        parent.child_chains.append(child_id)
        parent.updated = today
        write_chain(data_dir, parent)

        return success_response({
            "parent_chain_id": parent.chain_id,
            "child_chain_id": child_id,
            "child_chain_type": params.chain_type,
            "spawn_reason": params.spawn_reason,
            "first_session": first_session,
            "link_number": 1,
            "message": f"Child chain spawned from '{parent.chain_id}'. {first_session.title()} session is active.",
        })

    @mcp.tool(
        name="rename_chain",
        annotations={
            "title": "Rename Chain",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def rename_chain(params: RenameChainInput, ctx: Context) -> str:
        """Rename a chain: updates chain_id, renames YAML file, and fixes all cross-references.

        Updates: chain file, ticket references, declaration files, handoff files,
        catch files, and parent/child chain references.
        """
        data_dir = get_data_dir(ctx)
        old_id = params.chain_id
        new_id = to_kebab_case(params.new_title)

        # Guard: same name = no-op
        if old_id == new_id:
            return success_response({
                "chain_id": old_id,
                "changed": False,
                "reason": "New title produces the same chain_id",
            })

        # Guard: old chain must exist
        try:
            chain = read_chain(data_dir, old_id)
        except FileNotFoundError:
            return error_response(
                NOT_FOUND, f"Chain '{old_id}' not found"
            )

        # Guard: new chain must not exist
        if chain_path(data_dir, new_id).exists():
            return error_response(
                ALREADY_EXISTS,
                f"Chain '{new_id}' already exists",
                "Choose a different title",
            )

        # Guard: archived chains shouldn't be renamed
        if chain.status == ChainStatus.ARCHIVED:
            return error_response(
                INVALID_STATE,
                "Cannot rename an archived chain",
            )

        # 1. Update chain model
        chain.chain_id = new_id
        chain.title = params.new_title
        chain.updated = date.today()

        # 2. Write new file, delete old file
        write_chain(data_dir, chain)
        old_path = chain_path(data_dir, old_id)
        if old_path.exists():
            old_path.unlink()

        # 3. Update ticket cross-references
        refs_updated = []
        _update_ticket_refs(data_dir, old_id, new_id, refs_updated)

        # 4. Update parent chain's child_chains list
        if chain.parent_chain:
            _update_parent_chain_ref(data_dir, chain.parent_chain, old_id, new_id, refs_updated)

        # 5. Update child chains' parent_chain field
        for child_id in chain.child_chains:
            _update_child_chain_ref(data_dir, child_id, old_id, new_id, refs_updated)

        # 6. Rename declaration files
        _rename_data_files(data_dir / "declarations", old_id, new_id, refs_updated)

        # 7. Rename handoff files
        _rename_data_files(data_dir / "handoffs", old_id, new_id, refs_updated)

        # 8. Rename catch files
        _rename_data_files(data_dir / "catches", old_id, new_id, refs_updated)

        return success_response({
            "old_chain_id": old_id,
            "new_chain_id": new_id,
            "new_title": params.new_title,
            "refs_updated": refs_updated,
            "changed": True,
        })

    # --- Internal helpers (not exposed as tools) ---

    def _update_ticket_refs(data_dir, old_id, new_id, refs_updated):
        """Update chain_id references in all ticket files."""
        from storage import list_ticket_files

        for ticket_path_item in list_ticket_files(data_dir):
            try:
                with open(ticket_path_item) as f:
                    import yaml

                    data = yaml.safe_load(f)
                if data and data.get("chain_id") == old_id:
                    from schemas import Ticket as TicketModel

                    ticket = TicketModel(**data)
                    ticket.chain_id = new_id
                    write_ticket(data_dir, ticket)
                    refs_updated.append(f"ticket:{ticket.ticket_id}")
            except (FileNotFoundError, OSError):
                pass

    def _update_parent_chain_ref(data_dir, parent_id, old_id, new_id, refs_updated):
        """Update a parent chain's child_chains list."""
        try:
            parent = read_chain(data_dir, parent_id)
            if old_id in parent.child_chains:
                parent.child_chains = [
                    new_id if c == old_id else c for c in parent.child_chains
                ]
                parent.updated = date.today()
                write_chain(data_dir, parent)
                refs_updated.append(f"parent_chain:{parent_id}")
        except FileNotFoundError:
            pass

    def _update_child_chain_ref(data_dir, child_id, old_id, new_id, refs_updated):
        """Update a child chain's parent_chain field."""
        try:
            child = read_chain(data_dir, child_id)
            if child.parent_chain == old_id:
                child.parent_chain = new_id
                child.updated = date.today()
                write_chain(data_dir, child)
                refs_updated.append(f"child_chain:{child_id}")
        except FileNotFoundError:
            pass

    def _rename_data_files(directory, old_id, new_id, refs_updated):
        """Rename files in a data subdirectory that contain the old chain_id in their filename."""
        if not directory.exists():
            return
        for path in directory.iterdir():
            if old_id in path.name:
                new_name = path.name.replace(old_id, new_id)
                new_path = path.parent / new_name
                # Also update chain_id inside the YAML content
                try:
                    content = path.read_text()
                    # Replace chain_id value in YAML (handles both "chain_id: old-id" patterns)
                    updated_content = content.replace(old_id, new_id)
                    new_path.write_text(updated_content)
                    if new_path != path:
                        path.unlink()
                    refs_updated.append(f"{directory.name}:{new_name}")
                except OSError:
                    pass

    def _sync_ticket_chain_status(data_dir, chain: Chain):
        """Keep ticket's denormalized chain_status in sync."""
        if not chain.ticket_id:
            return
        try:
            ticket = read_ticket(data_dir, chain.ticket_id)
            ticket.chain_status = chain.status.value
            write_ticket(data_dir, ticket)
        except FileNotFoundError:
            pass
