# Lockstep Chain Protocol — tool input schemas
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

"""Pydantic input models for all 34 Lockstep MCP tools.

Each tool gets a dedicated input model with Field descriptions
that surface in Claude's tool UI.

14 chain lifecycle + 6 ticket lifecycle + 5 capacity + 6 query + 4 session support
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas import (
    CapacityEventType,
    CapacityStage,
    CatchAction,
    CatchTrigger,
    ChainStatus,
    HandoffStatus,
    PartnerAssessment,
    TicketPriority,
    TicketType,
)


# --- Chain Lifecycle Inputs (13 tools) ---


class CreateChainInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., description="Human-readable chain title")
    ticket_id: str = Field(..., description="Associated ticket ID (e.g. TICKET-002)")
    completion_vision: str = Field(
        ..., description="What 'done' looks like for this chain"
    )
    chain_type: Optional[str] = Field(
        None, description="Chain type identifier (e.g. full-funnel, enhancement, refactor, bug-fix)"
    )
    expected_sequence: list[str] = Field(
        default_factory=list,
        description="Expected session type sequence (e.g. ['discovery', 'planning', 'build'])",
    )
    entity: Optional[str] = Field(
        None, description="Subsidiary entity identifier (null = parent org)"
    )
    created_by: Optional[str] = Field(
        None, description="User identifier who created this chain"
    )
    capacity_role: Optional[str] = Field(
        None, description="Which capacity role this chain serves (when capacity_tracking enabled)"
    )


class ReadChainInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chain_id: str = Field(..., description="Chain identifier to read")


class GetChainStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chain_id: str = Field(..., description="Chain identifier")


class SetChainStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chain_id: str = Field(..., description="Chain identifier")
    status: ChainStatus = Field(..., description="New status: active, paused, blocked, complete, archived")


class SetChainEntityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chain_id: str = Field(..., description="Chain identifier")
    entity: Optional[str] = Field(..., description="Subsidiary entity identifier (null = parent org)")


class UpdateChainMetadataInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chain_id: str = Field(..., description="Chain identifier")
    completion_vision: Optional[str] = Field(
        None, description="Updated completion vision"
    )
    entity: Optional[str] = Field(None, description="Updated entity")
    capacity_role: Optional[str] = Field(
        None, description="Updated capacity role"
    )
    note: Optional[str] = Field(
        None, description="Free-text note to append to chain context"
    )


class AddChainLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chain_id: str = Field(..., description="Chain identifier")
    session_type: str = Field(
        ..., description="Session type for this link (e.g. 'build', 'review')"
    )
    started: Optional[date] = Field(
        None, description="Start date (defaults to today)"
    )
    progress_markers: list[str] = Field(
        default_factory=list,
        description="Initial progress markers for this link",
    )


class CompleteChainLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chain_id: str = Field(..., description="Chain identifier")
    link_number: Optional[int] = Field(
        None, description="Link number to complete (defaults to current active link)"
    )
    deliverables: list[str] = Field(
        default_factory=list, description="List of deliverable paths/descriptions"
    )
    handoff: Optional[str] = Field(
        None, description="Path to handoff file"
    )
    progress_markers: list[str] = Field(
        default_factory=list,
        description="Final progress markers for the completed link",
    )


class PauseChainInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chain_id: str = Field(..., description="Chain identifier")


class ResumeChainInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chain_id: str = Field(..., description="Chain identifier")


class CompleteChainInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chain_id: str = Field(..., description="Chain identifier")


class ArchiveChainInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chain_id: str = Field(..., description="Chain identifier to archive")


class BranchChainInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_chain_id: str = Field(..., description="Parent chain identifier to branch from")
    title: str = Field(..., description="Title for the new branch chain")
    completion_vision: str = Field(
        ..., description="What 'done' looks like for the branch"
    )
    ticket_id: Optional[str] = Field(
        None, description="Ticket ID for branch (inherits from parent if not provided)"
    )
    chain_type: Optional[str] = Field(
        None, description="Chain type (inherits from parent if not provided)"
    )
    spawn_reason: Optional[str] = Field(
        None, description="Why this fork was created — captures cross-type ideation patterns"
    )


class RenameChainInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chain_id: str = Field(..., description="Current chain identifier to rename")
    new_title: str = Field(..., description="New title (will be converted to kebab-case for the new chain_id)")


# --- Ticket Lifecycle Inputs (6 tools) ---


class CreateTicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., description="Ticket title")
    type: TicketType = Field(
        ..., description="Ticket type: new-initiative, enhancement, refactor, bug-fix, maintenance"
    )
    entity: Optional[str] = Field(
        None, description="Subsidiary entity identifier"
    )
    priority: TicketPriority = Field(
        TicketPriority.NORMAL,
        description="Priority: critical, high, normal, low",
    )
    tags: list[str] = Field(
        default_factory=list, description="Classification tags"
    )
    description: Optional[str] = Field(
        None, description="Ticket description"
    )


class ReadTicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str = Field(..., description="Ticket identifier (e.g. TICKET-002)")


class UpdateTicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str = Field(..., description="Ticket identifier")
    priority: Optional[TicketPriority] = Field(None, description="Updated priority")
    entity: Optional[str] = Field(None, description="Updated entity")
    description: Optional[str] = Field(None, description="Updated description")
    note: Optional[str] = Field(
        None, description="Note to append to the ticket's notes log"
    )


class CloseTicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str = Field(..., description="Ticket identifier")


class TagTicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str = Field(..., description="Ticket identifier")
    add: list[str] = Field(
        default_factory=list, description="Tags to add"
    )
    remove: list[str] = Field(
        default_factory=list, description="Tags to remove"
    )


class LinkTicketChainInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str = Field(..., description="Ticket identifier")
    chain_id: str = Field(..., description="Chain identifier to link")


class PromoteTicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str = Field(..., description="Ticket to promote into a chain")
    completion_vision: str = Field(
        ..., description="What 'done' looks like for the resulting chain"
    )
    chain_type: Optional[str] = Field(
        None, description="Chain type (inferred from ticket type if not provided)"
    )
    nest_tickets: list[str] = Field(
        default_factory=list,
        description="Ticket IDs to nest under the new chain immediately (from candidate list)",
    )


# --- Capacity Tracking Inputs (5 tools) ---


class ReadCapacityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Optional[str] = Field(
        None, description="Capacity role to read (e.g. 'finance'). Omit to read all roles."
    )


class UpdateCapacityStageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(..., description="Capacity role identifier")
    new_stage: CapacityStage = Field(
        ..., description="New stage: training-wheels, partnership, safety-net"
    )
    trigger: str = Field(
        ..., description="What triggered this transition (e.g. 'ratio shift over last 5 chains')"
    )


class RecordCapacityEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(..., description="Capacity role this event applies to")
    chain_id: str = Field(..., description="Chain where the event occurred")
    event_type: CapacityEventType = Field(
        ...,
        description="Event attribution: partner_performed, partner_scaffolded, human_performed, human_independent, human_corrected",
    )
    description: str = Field(
        ..., description="What happened (Partner's field notes)"
    )


class GetCapacityEventsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(..., description="Capacity role to query events for")
    event_type: Optional[CapacityEventType] = Field(
        None, description="Filter by event type"
    )
    since: Optional[date] = Field(
        None, description="Only events after this date"
    )
    limit: int = Field(
        50, description="Maximum number of events to return (default 50)"
    )


class CheckStagnationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Optional[str] = Field(
        None, description="Specific role to check. Omit to check all roles."
    )


# --- Query Tool Inputs (6 tools) ---


class SearchChainsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity: Optional[str] = Field(None, description="Filter by entity")
    status: Optional[ChainStatus] = Field(None, description="Filter by chain status")
    session_type: Optional[str] = Field(
        None, description="Filter chains that have a link with this session type"
    )
    since: Optional[date] = Field(None, description="Chains created after this date")
    before: Optional[date] = Field(None, description="Chains created before this date")


class ListChainsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # No parameters — lists all active chains


class SearchTicketsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Optional[TicketType] = Field(None, description="Filter by ticket type")
    entity: Optional[str] = Field(None, description="Filter by entity")
    priority: Optional[TicketPriority] = Field(None, description="Filter by priority")
    status: Optional[str] = Field(None, description="Filter by status: open, active, closed")


class ListTicketsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # No parameters — lists all open tickets


class GetDashboardInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity: Optional[str] = Field(
        None, description="Filter dashboard to a specific entity"
    )


class CheckChainHealthInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stale_days: int = Field(
        30, description="Days without update before a chain is considered stale (default 30)"
    )


# --- Session Support Inputs (4 tools) ---


class RecordSessionDeclarationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chain_id: str = Field(..., description="Chain this session belongs to")
    session_type: str = Field(
        ..., description="Session type (e.g. 'build', 'architecture')"
    )
    goal: str = Field(..., description="Session goal — what are we doing?")
    deliverable: str = Field(
        ..., description="Expected deliverable — what artifact will this produce?"
    )
    completion_criteria: list[str] = Field(
        default_factory=list, description="How do we know we're done?"
    )
    out_of_scope: list[str] = Field(
        default_factory=list, description="What are we explicitly NOT doing?"
    )
    context_from_previous: Optional[str] = Field(
        None, description="Context carried forward from previous session"
    )


class RecordHandoffInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chain_id: str = Field(..., description="Chain this handoff belongs to")
    session_type: str = Field(..., description="Session type being handed off")
    status: HandoffStatus = Field(
        ..., description="Session outcome: paused or complete"
    )
    decisions_made: list[str] = Field(
        default_factory=list, description="Key decisions from this session"
    )
    files_changed: list[dict] = Field(
        default_factory=list,
        description="Files changed: [{path: str, action: str}]",
    )
    tickets_spawned: list[str] = Field(
        default_factory=list, description="Ticket IDs created during this session"
    )
    tickets_updated: list[str] = Field(
        default_factory=list, description="Ticket IDs updated during this session"
    )
    open_threads: list[str] = Field(
        default_factory=list, description="Unresolved items for next session"
    )
    recommended_next_type: Optional[str] = Field(
        None, description="Recommended session type for next link"
    )
    quick_start: Optional[str] = Field(
        None, description="Quick-start instructions for next session"
    )
    context_for_next_partner: Optional[str] = Field(
        None, description="Context for the next Partner instance"
    )
    emotional_context: Optional[str] = Field(
        None, description="Human's energy/emotional state (optional, valuable)"
    )


class RecordGateSkipInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chain_id: str = Field(..., description="Chain where the skip occurred")
    skipped_from: str = Field(
        ..., description="Expected session type that was skipped"
    )
    skipped_to: str = Field(
        ..., description="Actual session type chosen instead"
    )
    reason: str = Field(
        ..., description="Human's reason for skipping"
    )
    partner_assessment: str = Field(
        ..., description="Partner's clinical observation of the skip"
    )


class RecordCatchEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chain_id: str = Field(..., description="Chain where the catch fired")
    session_type: str = Field(
        ..., description="Session type when catch occurred"
    )
    trigger: CatchTrigger = Field(
        ..., description="What triggered the catch: scope_drift, context_pressure, momentum_shift, rabbit_hole"
    )
    action_taken: CatchAction = Field(
        ..., description="What happened: paused, redirected, checkpointed, acknowledged_and_continued, handed_off"
    )
    human_reasoning: Optional[str] = Field(
        None, description="Human's explanation (optional but gold when present)"
    )
    partner_assessment: PartnerAssessment = Field(
        ..., description="Partner's clinical observation: legitimate, avoidance, overcorrection, unclear"
    )
    assessment_note: Optional[str] = Field(
        None, description="Free-text nuance alongside the enum assessment"
    )
