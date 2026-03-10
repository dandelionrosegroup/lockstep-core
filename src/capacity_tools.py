# Lockstep Chain Protocol — capacity tracking tools
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

"""Capacity tracking tools (5 tools).

Active when capacity_tracking.enabled = true. All tools return
structured JSON, never prose. Growth model: Decision 6.
"""

from __future__ import annotations

from datetime import date, datetime

from mcp.server.fastmcp import Context

from errors import (
    IO_ERROR,
    NOT_FOUND,
    VALIDATION_ERROR,
    error_response,
    success_response,
)
from schemas import (
    CapacityEvent,
    CapacityFile,
    CapacityStage,
    StageHistoryEntry,
    StagnationTracking,
)
from storage import (
    capacity_path,
    get_data_dir,
    list_capacity_files,
    read_capacity,
    write_capacity,
)
from tool_inputs import (
    CheckStagnationInput,
    GetCapacityEventsInput,
    ReadCapacityInput,
    RecordCapacityEventInput,
    UpdateCapacityStageInput,
)


def register_capacity_tools(mcp):
    """Register all 5 capacity tracking tools on the FastMCP instance."""

    @mcp.tool(
        name="read_capacity",
        annotations={
            "title": "Read Capacity",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def read_capacity_tool(params: ReadCapacityInput, ctx: Context) -> str:
        """Read growth stage for a specific role or all roles."""
        data_dir = get_data_dir(ctx)

        if params.role:
            if not capacity_path(data_dir, params.role).exists():
                return error_response(
                    NOT_FOUND,
                    f"Capacity role '{params.role}' not found",
                    "Available roles are in data/capacity/",
                )
            cap = read_capacity(data_dir, params.role)
            return success_response(cap.model_dump(mode="json", exclude_none=True))

        # All roles
        files = list_capacity_files(data_dir)
        if not files:
            return success_response({"roles": [], "message": "No capacity roles tracked yet"})

        roles = []
        for path in files:
            role_name = path.stem
            cap = read_capacity(data_dir, role_name)
            roles.append({
                "role": cap.role,
                "display_name": cap.display_name,
                "current_stage": cap.current_stage.value,
                "stage_entered": str(cap.stage_entered) if cap.stage_entered else None,
                "event_count": len(cap.events),
                "stagnation_count": cap.stagnation.current_count,
                "last_active": str(cap.dormancy.last_active_date) if cap.dormancy.last_active_date else None,
            })

        return success_response({"roles": roles})

    @mcp.tool(
        name="update_capacity_stage",
        annotations={
            "title": "Update Capacity Stage",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def update_capacity_stage(
        params: UpdateCapacityStageInput, ctx: Context
    ) -> str:
        """Record a stage transition (training-wheels -> partnership -> safety-net)."""
        data_dir = get_data_dir(ctx)

        if not capacity_path(data_dir, params.role).exists():
            return error_response(
                NOT_FOUND, f"Capacity role '{params.role}' not found"
            )

        cap = read_capacity(data_dir, params.role)

        # Idempotent: same stage = no-op
        if cap.current_stage == params.new_stage:
            return success_response({
                "role": cap.role,
                "stage": cap.current_stage.value,
                "changed": False,
            })

        today = date.today()
        old_stage = cap.current_stage

        # Close current stage history entry
        if cap.stage_history:
            cap.stage_history[-1].exited = today

        # Add new stage history entry
        cap.stage_history.append(StageHistoryEntry(
            stage=params.new_stage,
            entered=today,
            chains_at_stage=0,
            trigger=params.trigger,
        ))

        cap.current_stage = params.new_stage
        cap.stage_entered = today

        # Reset stagnation counter on stage change
        cap.stagnation.current_count = 0

        write_capacity(data_dir, cap)

        return success_response({
            "role": cap.role,
            "previous_stage": old_stage.value,
            "stage": cap.current_stage.value,
            "trigger": params.trigger,
            "changed": True,
        })

    @mcp.tool(
        name="record_capacity_event",
        annotations={
            "title": "Record Capacity Event",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def record_capacity_event(
        params: RecordCapacityEventInput, ctx: Context
    ) -> str:
        """Log a capacity-relevant event with typed attribution (Partner's field notes)."""
        data_dir = get_data_dir(ctx)

        # Auto-create capacity file if it doesn't exist
        path = capacity_path(data_dir, params.role)
        if path.exists():
            cap = read_capacity(data_dir, params.role)
        else:
            cap = CapacityFile(
                role=params.role,
                display_name=params.role.replace("-", " ").title(),
                stage_entered=date.today(),
                stagnation=StagnationTracking(),
            )
            cap.stage_history.append(StageHistoryEntry(
                stage=CapacityStage.TRAINING_WHEELS,
                entered=date.today(),
                chains_at_stage=0,
                trigger="auto-created on first capacity event",
            ))

        event = CapacityEvent(
            timestamp=datetime.now(),
            chain_id=params.chain_id,
            event_type=params.event_type,
            description=params.description,
        )
        cap.events.append(event)

        # Update dormancy tracking
        cap.dormancy.last_active_date = date.today()
        cap.dormancy.last_chain_id = params.chain_id

        # Update stagnation counter (chains at current stage)
        cap.stagnation.current_count += 1
        if cap.stage_history:
            cap.stage_history[-1].chains_at_stage = cap.stagnation.current_count

        # Recompute event ratio from recent events (last 20)
        _recompute_event_ratio(cap)

        try:
            write_capacity(data_dir, cap)
        except OSError as e:
            return error_response(IO_ERROR, f"Failed to write capacity: {e}")

        return success_response({
            "role": cap.role,
            "event_type": params.event_type.value,
            "event_count": len(cap.events),
            "current_stage": cap.current_stage.value,
            "stagnation_count": cap.stagnation.current_count,
        })

    @mcp.tool(
        name="get_capacity_events",
        annotations={
            "title": "Get Capacity Events",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_capacity_events(
        params: GetCapacityEventsInput, ctx: Context
    ) -> str:
        """Query capacity event history with optional filters."""
        data_dir = get_data_dir(ctx)

        if not capacity_path(data_dir, params.role).exists():
            return error_response(
                NOT_FOUND, f"Capacity role '{params.role}' not found"
            )

        cap = read_capacity(data_dir, params.role)
        events = cap.events

        # Apply filters
        if params.event_type:
            events = [e for e in events if e.event_type == params.event_type]
        if params.since:
            events = [e for e in events if e.timestamp.date() >= params.since]

        # Apply limit (most recent first)
        events = events[-params.limit:]

        return success_response({
            "role": cap.role,
            "total_events": len(cap.events),
            "filtered_count": len(events),
            "events": [e.model_dump(mode="json") for e in events],
        })

    @mcp.tool(
        name="check_stagnation",
        annotations={
            "title": "Check Stagnation",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def check_stagnation(params: CheckStagnationInput, ctx: Context) -> str:
        """Evaluate if any role has hit its stagnation threshold.

        Stagnation = active engagement but no growth.
        Dormancy = no engagement at all.
        Both surfaced as observations, not errors (Design Principle 2).
        """
        data_dir = get_data_dir(ctx)

        if params.role:
            if not capacity_path(data_dir, params.role).exists():
                return error_response(
                    NOT_FOUND, f"Capacity role '{params.role}' not found"
                )
            files = [capacity_path(data_dir, params.role)]
        else:
            files = list_capacity_files(data_dir)

        if not files:
            return success_response({
                "alerts": [],
                "message": "No capacity roles tracked yet",
            })

        alerts = []
        today = date.today()

        for path in files:
            role_name = path.stem
            cap = read_capacity(data_dir, role_name)

            # Stagnation check
            if cap.stagnation.current_count >= cap.stagnation.threshold:
                alerts.append({
                    "role": cap.role,
                    "type": "stagnation",
                    "message": (
                        f"Role '{cap.display_name}' has {cap.stagnation.current_count} "
                        f"{cap.stagnation.threshold_unit} at stage '{cap.current_stage.value}'"
                    ),
                    "current_stage": cap.current_stage.value,
                    "count": cap.stagnation.current_count,
                    "threshold": cap.stagnation.threshold,
                })

            # Dormancy check (90 days without activity)
            if cap.dormancy.last_active_date:
                days_inactive = (today - cap.dormancy.last_active_date).days
                if days_inactive >= 90:
                    alerts.append({
                        "role": cap.role,
                        "type": "dormancy",
                        "message": (
                            f"Role '{cap.display_name}' has been inactive for "
                            f"{days_inactive} days"
                        ),
                        "days_inactive": days_inactive,
                        "last_active": str(cap.dormancy.last_active_date),
                    })

        return success_response({"alerts": alerts})

    # --- Internal helpers ---

    def _recompute_event_ratio(cap: CapacityFile):
        """Recompute the event ratio snapshot from recent events."""
        recent = cap.events[-20:]  # Last 20 events
        if not recent:
            return

        counts = {
            "partner_performed": 0,
            "partner_scaffolded": 0,
            "human_performed": 0,
            "human_independent": 0,
            "human_corrected": 0,
        }
        for event in recent:
            counts[event.event_type.value] += 1

        total = len(recent)
        cap.event_ratio.partner_performed = round(counts["partner_performed"] / total, 2)
        cap.event_ratio.partner_scaffolded = round(counts["partner_scaffolded"] / total, 2)
        cap.event_ratio.human_performed = round(counts["human_performed"] / total, 2)
        cap.event_ratio.human_independent = round(counts["human_independent"] / total, 2)
        cap.event_ratio.human_corrected = round(counts["human_corrected"] / total, 2)
        cap.event_ratio.sample_size = total
        cap.event_ratio.last_computed = date.today()
