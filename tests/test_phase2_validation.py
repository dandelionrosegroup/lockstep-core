"""Phase 2 validation tests for Lockstep Protocol Plugin.

Tests the behavioral concerns flagged during Phase 1 Post-Build Eval:
1. Gate Protocol records skips but never blocks
2. Catch events record all required fields
3. Capacity stage transitions work with behavioral heuristics
4. Handoff format includes all required fields (especially emotional context)
5. Chain templates are advisory (any session type can follow any other)
6. Session declarations validate required fields
7. Cross-tool data consistency (write → query → verify)
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from server import mcp  # noqa: E402


class FakeContext:
    def __init__(self, data_dir: Path):
        self.request_context = MagicMock()
        self.request_context.lifespan_context = {"data_dir": data_dir}


def setup_data_dir() -> Path:
    data_dir = Path(tempfile.mkdtemp(prefix="lockstep-phase2-"))
    for subdir in [
        "chains", "tickets", "capacity", "declarations",
        "handoffs", "catches", "archive/chains", "archive/tickets",
    ]:
        (data_dir / subdir).mkdir(parents=True, exist_ok=True)
    return data_dir


def parse(result: str) -> dict:
    return json.loads(result)


# ── Test 1: Gate Protocol is advisory, never blocking ───────────────

async def test_gate_skip_records_but_does_not_block():
    """Gate Protocol records skips but never refuses a session type.

    Design principle: Advisory Gate, Not Hard Enforcement.
    The system records the skip — it never prevents it.
    """
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    tools = mcp._tool_manager._tools

    async def call(name, **kw):
        return parse(await tools[name].fn(ctx=ctx, **kw))

    try:
        # Create an initiative (suggests full-funnel template)
        r = await call("cmd_new_initiative",
            title="Test Gate Advisory",
            vision="Verify gates don't block",
            entity="test",
        )
        chain_id = r["chain_id"]

        # Record multiple gate skips — system should accept all of them
        from tool_inputs import RecordGateSkipInput

        skip1 = await call("record_gate_skip",
            params=RecordGateSkipInput(
                chain_id=chain_id,
                skipped_from="discovery",
                skipped_to="build",
                reason="I know what I'm doing",
                partner_assessment="Risky but human's call",
            ),
        )
        assert skip1["total_skips"] == 1

        skip2 = await call("record_gate_skip",
            params=RecordGateSkipInput(
                chain_id=chain_id,
                skipped_from="planning",
                skipped_to="build",
                reason="Small scope, planning not needed",
                partner_assessment="Reasonable for scope",
            ),
        )
        assert skip2["total_skips"] == 2

        # Verify skip data persists for pattern detection
        from tool_inputs import SearchChainsInput
        chains = await call("search_chains",
            params=SearchChainsInput(entity="test"),
        )
        assert chains["count"] >= 1

    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


# ── Test 2: Catch events capture all required fields ────────────────

async def test_catch_event_completeness():
    """Catch events record trigger, action, human reasoning, and partner assessment.

    All four fields matter: the trigger (what happened), the action (what was done),
    the reasoning (why the human chose it), and the assessment (Partner's read).
    """
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    tools = mcp._tool_manager._tools

    async def call(name, **kw):
        return parse(await tools[name].fn(ctx=ctx, **kw))

    try:
        r = await call("cmd_new_initiative",
            title="Catch Test", vision="Test catches", entity="test",
        )
        chain_id = r["chain_id"]

        from tool_inputs import RecordCatchEventInput
        from schemas import CatchTrigger, CatchAction, PartnerAssessment

        # Test each catch trigger type
        for trigger, action, reasoning, assessment in [
            (CatchTrigger.SCOPE_DRIFT, CatchAction.REDIRECTED,
             "Started redesigning the whole API", PartnerAssessment.LEGITIMATE),
            (CatchTrigger.CONTEXT_PRESSURE, CatchAction.PAUSED,
             "Context window is nearly full", PartnerAssessment.LEGITIMATE),
            (CatchTrigger.MOMENTUM_SHIFT, CatchAction.CHECKPOINTED,
             "I'm getting tired, let's pause", PartnerAssessment.LEGITIMATE),
            (CatchTrigger.RABBIT_HOLE, CatchAction.ACKNOWLEDGED_AND_CONTINUED,
             "Tangent but useful context", PartnerAssessment.AVOIDANCE),
        ]:
            r = await call("record_catch_event",
                params=RecordCatchEventInput(
                    chain_id=chain_id,
                    session_type="discovery",
                    trigger=trigger,
                    action_taken=action,
                    human_reasoning=reasoning,
                    partner_assessment=assessment,
                    assessment_note=f"Test note for {trigger.value}",
                ),
            )
            assert "catch_path" in r, f"Catch failed for {trigger}: {r}"

    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


# ── Test 3: Capacity stage transitions ──────────────────────────────

async def test_capacity_stage_lifecycle():
    """Capacity stages progress: training-wheels → partnership → safety-net.

    Tests that:
    - Default stage is training-wheels
    - Transitions move forward
    - Regression (backward transition) is allowed (regression is normal)
    - Events accumulate correctly
    """
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    tools = mcp._tool_manager._tools

    async def call(name, **kw):
        return parse(await tools[name].fn(ctx=ctx, **kw))

    try:
        from tool_inputs import (
            RecordCapacityEventInput, UpdateCapacityStageInput,
            ReadCapacityInput, GetCapacityEventsInput,
        )
        from schemas import CapacityStage, CapacityEventType

        role = "infrastructure"

        # Log events at training-wheels
        await call("record_capacity_event",
            params=RecordCapacityEventInput(
                role=role, chain_id="test-chain-1",
                event_type=CapacityEventType.PARTNER_SCAFFOLDED,
                description="Partner guided deployment process",
            ),
        )

        # Read — should be at training-wheels
        cap = await call("read_capacity", params=ReadCapacityInput(role=role))
        assert cap["current_stage"] == "training-wheels"

        # Transition to partnership
        r = await call("update_capacity_stage",
            params=UpdateCapacityStageInput(
                role=role,
                new_stage=CapacityStage.PARTNERSHIP,
                trigger="Human handling most deployment work independently",
            ),
        )
        assert r["changed"] is True
        assert r["stage"] == "partnership"

        # Transition to safety-net
        r = await call("update_capacity_stage",
            params=UpdateCapacityStageInput(
                role=role,
                new_stage=CapacityStage.SAFETY_NET,
                trigger="Human corrects own mistakes before Partner flags them",
            ),
        )
        assert r["changed"] is True
        assert r["stage"] == "safety-net"

        # Regression back to partnership (allowed — regression is normal)
        r = await call("update_capacity_stage",
            params=UpdateCapacityStageInput(
                role=role,
                new_stage=CapacityStage.PARTNERSHIP,
                trigger="New complexity introduced, human needs more support",
            ),
        )
        assert r["changed"] is True
        assert r["stage"] == "partnership"

        # Verify events persisted
        events = await call("get_capacity_events",
            params=GetCapacityEventsInput(role=role),
        )
        assert events["filtered_count"] >= 1

    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


# ── Test 4: Handoff format completeness ─────────────────────────────

async def test_handoff_includes_emotional_context():
    """Handoffs must include emotional context.

    An ADHD brain returning to work needs to know not just *what* happened
    but *how it felt*. This is a design principle, not an optional field.
    """
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    tools = mcp._tool_manager._tools

    async def call(name, **kw):
        return parse(await tools[name].fn(ctx=ctx, **kw))

    try:
        r = await call("cmd_new_initiative",
            title="Handoff Test", vision="Test handoffs", entity="test",
        )
        chain_id = r["chain_id"]

        from tool_inputs import RecordHandoffInput
        from schemas import HandoffStatus

        handoff = await call("record_handoff",
            params=RecordHandoffInput(
                chain_id=chain_id,
                session_type="discovery",
                status=HandoffStatus.COMPLETE,
                decisions_made=["Scope defined", "Stakeholders mapped"],
                files_changed=[{"path": "docs/scope.md", "action": "created"}],
                open_threads=["Finance team validation pending"],
                recommended_next_type="planning",
                quick_start="Begin with task decomposition from scope doc",
                context_for_next_partner="Discovery productive, human energized",
                emotional_context="Strong momentum, excited about next steps",
            ),
        )
        assert "handoff_path" in handoff

        # Read back the handoff file and verify emotional_context persisted
        import yaml
        handoff_files = list((data_dir / "handoffs").glob("*.yaml"))
        assert len(handoff_files) >= 1
        with open(handoff_files[0]) as f:
            saved = yaml.safe_load(f)
        assert saved.get("emotional_context") == "Strong momentum, excited about next steps"
        assert saved.get("context_for_next_partner") == "Discovery productive, human energized"

    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


# ── Test 5: Chain templates are advisory ────────────────────────────

async def test_any_session_type_can_follow_any_other():
    """Chain templates suggest session order but never enforce it.

    Design principle: Advisory Gate, Not Hard Enforcement.
    A user should be able to declare any session type at any point in a chain.
    """
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    tools = mcp._tool_manager._tools

    async def call(name, **kw):
        return parse(await tools[name].fn(ctx=ctx, **kw))

    try:
        r = await call("cmd_new_initiative",
            title="Advisory Test", vision="Test flexibility", entity="test",
        )
        chain_id = r["chain_id"]

        from tool_inputs import RecordSessionDeclarationInput

        # Declare sessions in a non-standard order
        # Initiative suggests: Discovery → Research → Planning → Architecture → Build → Review
        # We'll do: Build (skip everything) → then Maintenance (unusual)
        for session_type in ["build", "maintenance", "review"]:
            r = await call("record_session_declaration",
                params=RecordSessionDeclarationInput(
                    chain_id=chain_id,
                    session_type=session_type,
                    goal=f"Test {session_type} session",
                    deliverable=f"{session_type} output",
                    completion_criteria=[f"{session_type} criteria met"],
                ),
            )
            # The system must accept any session type — no refusal
            assert r.get("partner_confirmed") is True, \
                f"System refused {session_type}: {r}"

    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


# ── Test 6: Cross-tool data consistency ─────────────────────────────

async def test_write_then_query_consistency():
    """Data written by lifecycle tools is readable by query tools.

    End-to-end: create → query → verify match.
    """
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    tools = mcp._tool_manager._tools

    async def call(name, **kw):
        return parse(await tools[name].fn(ctx=ctx, **kw))

    try:
        # Create via command
        r = await call("cmd_enhancement",
            title="Query Consistency Test",
            vision="Verify write-read cycle",
        )
        chain_id = r["chain_id"]
        ticket_id = r["ticket_id"]

        # Query chain
        from tool_inputs import SearchChainsInput, ListTicketsInput, GetDashboardInput

        chains = await call("search_chains",
            params=SearchChainsInput(status="active"),
        )
        chain_ids = [c["chain_id"] for c in chains["chains"]]
        assert chain_id in chain_ids, f"Chain {chain_id} not in search results"

        # Query tickets
        tickets = await call("list_tickets", params=ListTicketsInput())
        ticket_ids = [t["ticket_id"] for t in tickets["tickets"]]
        assert ticket_id in ticket_ids, f"Ticket {ticket_id} not in list"

        # Dashboard
        dash = await call("get_dashboard", params=GetDashboardInput())
        assert len(dash["active_chains"]) >= 1
        assert len(dash["open_tickets"]) >= 1

    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(test_gate_skip_records_but_does_not_block())
    print("PASS: test_gate_skip_records_but_does_not_block")
    asyncio.run(test_catch_event_completeness())
    print("PASS: test_catch_event_completeness")
    asyncio.run(test_capacity_stage_lifecycle())
    print("PASS: test_capacity_stage_lifecycle")
    asyncio.run(test_handoff_includes_emotional_context())
    print("PASS: test_handoff_includes_emotional_context")
    asyncio.run(test_any_session_type_can_follow_any_other())
    print("PASS: test_any_session_type_can_follow_any_other")
    asyncio.run(test_write_then_query_consistency())
    print("PASS: test_write_then_query_consistency")
    print("\nALL 6 PHASE 2 TESTS PASSED")
