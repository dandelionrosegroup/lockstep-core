# Lockstep Chain Protocol — data schemas
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

"""Data schemas for Lockstep Protocol.

8 schemas: Chain, Ticket, Capacity, CatchEvent, SessionDeclaration,
Handoff, plus supporting enums and sub-models.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --- Enums ---

class ChainStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    BLOCKED = "blocked"
    COMPLETE = "complete"
    ARCHIVED = "archived"


class ChainLinkStatus(str, Enum):
    ACTIVE = "active"
    COMPLETE = "complete"
    CAUGHT = "caught"


class ChainTemplate(str, Enum):
    FULL_FUNNEL = "full-funnel"
    ENHANCEMENT = "enhancement"
    REFACTOR = "refactor"
    BUG_FIX = "bug-fix"


class TicketType(str, Enum):
    NEW_INITIATIVE = "new-initiative"
    ENHANCEMENT = "enhancement"
    REFACTOR = "refactor"
    BUG_FIX = "bug-fix"
    MAINTENANCE = "maintenance"


class TicketStatus(str, Enum):
    OPEN = "open"
    ACTIVE = "active"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class CapacityStage(str, Enum):
    TRAINING_WHEELS = "training-wheels"
    PARTNERSHIP = "partnership"
    SAFETY_NET = "safety-net"


class CatchTrigger(str, Enum):
    SCOPE_DRIFT = "scope_drift"
    CONTEXT_PRESSURE = "context_pressure"
    MOMENTUM_SHIFT = "momentum_shift"
    RABBIT_HOLE = "rabbit_hole"


class CatchAction(str, Enum):
    PAUSED = "paused"
    REDIRECTED = "redirected"
    CHECKPOINTED = "checkpointed"
    ACKNOWLEDGED_AND_CONTINUED = "acknowledged_and_continued"
    HANDED_OFF = "handed_off"


class PartnerAssessment(str, Enum):
    """A4 resolution: small enum for pattern detection across catch events."""
    LEGITIMATE = "legitimate"
    AVOIDANCE = "avoidance"
    OVERCORRECTION = "overcorrection"
    UNCLEAR = "unclear"


class CapacityEventType(str, Enum):
    PARTNER_PERFORMED = "partner_performed"
    PARTNER_SCAFFOLDED = "partner_scaffolded"
    HUMAN_PERFORMED = "human_performed"
    HUMAN_INDEPENDENT = "human_independent"
    HUMAN_CORRECTED = "human_corrected"


class HandoffStatus(str, Enum):
    PAUSED = "paused"
    COMPLETE = "complete"


# --- Sub-models ---

class ChainLink(BaseModel):
    """A single session link within a chain."""
    link_number: int
    session_type: str
    status: ChainLinkStatus = ChainLinkStatus.ACTIVE
    started: date
    completed: Optional[date] = None
    deliverables: list[str] = Field(default_factory=list)
    handoff: Optional[str] = None
    progress_markers: list[str] = Field(default_factory=list)


class GateSkip(BaseModel):
    """Record of a session-type leapfrog (Design Principle 1)."""
    timestamp: datetime
    skipped_from: str
    skipped_to: str
    reason: str
    partner_assessment: str


class TicketNote(BaseModel):
    """Append-only note entry on a ticket."""
    timestamp: date
    content: str


class StageHistoryEntry(BaseModel):
    """Record of a capacity stage transition."""
    stage: CapacityStage
    entered: date
    exited: Optional[date] = None
    chains_at_stage: int = 0
    trigger: str


class StagnationTracking(BaseModel):
    """Stagnation state within a capacity file."""
    threshold: int = 5
    threshold_unit: str = "chains"
    current_count: int = 0
    last_surfaced: Optional[date] = None


class DormancyTracking(BaseModel):
    """Dormancy state within a capacity file."""
    last_active_date: Optional[date] = None
    last_chain_id: Optional[str] = None


class CapacityEvent(BaseModel):
    """A single capacity-relevant event (Partner's field notes)."""
    timestamp: datetime
    chain_id: str
    event_type: CapacityEventType
    description: str


class EventRatio(BaseModel):
    """Precomputed ratio snapshot for dashboard performance."""
    partner_performed: float = 0.0
    partner_scaffolded: float = 0.0
    human_performed: float = 0.0
    human_independent: float = 0.0
    human_corrected: float = 0.0
    sample_size: int = 0
    last_computed: Optional[date] = None


class FileChange(BaseModel):
    """A file changed during a session (for handoff)."""
    path: str
    action: str


class NextSession(BaseModel):
    """Recommendation for the next session (in handoff)."""
    recommended_type: Optional[str] = None
    quick_start: Optional[str] = None


# --- Top-level schemas ---

SCHEMA_VERSION = "1.0"


class Chain(BaseModel):
    """Chain YAML schema — full chain lifecycle."""
    schema_version: str = SCHEMA_VERSION
    chain_id: str
    title: str
    ticket_id: str
    status: ChainStatus = ChainStatus.ACTIVE
    created: date
    updated: date
    completed: Optional[date] = None
    archived: Optional[date] = None
    entity: Optional[str] = None
    created_by: Optional[str] = None
    completion_vision: str
    template: Optional[ChainTemplate] = None
    expected_sequence: list[str] = Field(default_factory=list)
    links: list[ChainLink] = Field(default_factory=list)
    gate_skips: list[GateSkip] = Field(default_factory=list)
    parent_chain: Optional[str] = None
    child_chains: list[str] = Field(default_factory=list)
    capacity_role: Optional[str] = None


class Ticket(BaseModel):
    """Ticket YAML schema — work unit."""
    schema_version: str = SCHEMA_VERSION
    ticket_id: str
    title: str
    type: TicketType
    status: TicketStatus = TicketStatus.OPEN
    created: date
    closed: Optional[date] = None
    entity: Optional[str] = None
    priority: TicketPriority = TicketPriority.NORMAL
    tags: list[str] = Field(default_factory=list)
    chain_id: Optional[str] = None
    chain_status: Optional[str] = None
    description: Optional[str] = None
    notes: list[TicketNote] = Field(default_factory=list)


class CapacityFile(BaseModel):
    """Capacity file YAML schema — per-role growth tracking."""
    schema_version: str = SCHEMA_VERSION
    role: str
    display_name: str
    current_stage: CapacityStage = CapacityStage.TRAINING_WHEELS
    stage_entered: Optional[date] = None
    stage_history: list[StageHistoryEntry] = Field(default_factory=list)
    stagnation: StagnationTracking = Field(default_factory=StagnationTracking)
    dormancy: DormancyTracking = Field(default_factory=DormancyTracking)
    events: list[CapacityEvent] = Field(default_factory=list)
    event_ratio: EventRatio = Field(default_factory=EventRatio)


class CatchEvent(BaseModel):
    """Catch event schema — qualitative scope-drift capture."""
    timestamp: datetime
    trigger: CatchTrigger
    session_type: str
    chain_id: str
    action_taken: CatchAction
    human_reasoning: Optional[str] = None
    partner_assessment: PartnerAssessment
    assessment_note: Optional[str] = None


class SessionDeclaration(BaseModel):
    """Session Declaration schema — 6 components."""
    chain_id: str
    link_number: int
    session_type: str
    goal: str
    deliverable: str
    completion_criteria: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    partner_confirmed: bool = False
    context_from_previous: Optional[str] = None
    timestamp: Optional[datetime] = None


class Handoff(BaseModel):
    """Handoff schema — session-end continuity record."""
    chain_id: str
    link_number: int
    session_type: str
    status: HandoffStatus
    date: date
    decisions_made: list[str] = Field(default_factory=list)
    files_changed: list[FileChange] = Field(default_factory=list)
    tickets_spawned: list[str] = Field(default_factory=list)
    tickets_updated: list[str] = Field(default_factory=list)
    open_threads: list[str] = Field(default_factory=list)
    next_session: NextSession = Field(default_factory=NextSession)
    context_for_next_partner: Optional[str] = None
    emotional_context: Optional[str] = None
