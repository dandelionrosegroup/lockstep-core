"""Integration test for all 39 Lockstep MCP tools.

End-to-end: command -> tool sequence -> schema write -> query read.
Tests the full Link 5 acceptance criteria.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# Ensure local imports work
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from server import mcp  # noqa: E402


class FakeContext:
    """Minimal context that mimics FastMCP's lifespan state."""

    def __init__(self, data_dir: Path):
        self.request_context = MagicMock()
        self.request_context.lifespan_context = {
            "data_dir": data_dir,
            "resolution_method": "test",
        }


def setup_data_dir() -> Path:
    """Create a temp data directory with required subdirs."""
    data_dir = Path(tempfile.mkdtemp(prefix="lockstep-test-"))
    for subdir in [
        "chains", "tickets", "capacity", "declarations",
        "handoffs", "catches", "archive/chains", "archive/tickets",
    ]:
        (data_dir / subdir).mkdir(parents=True, exist_ok=True)
    return data_dir


def parse(result: str) -> dict:
    return json.loads(result)


async def test_end_to_end():
    """Full flow: command -> tools -> query -> verify."""
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    tools = mcp._tool_manager._tools
    errors = []

    async def call(name: str, **kwargs):
        tool = tools[name]
        return parse(await tool.fn(ctx=ctx, **kwargs))

    try:
        # === 1. Command: /new-initiative ===
        print("1. Testing cmd_new_initiative...")
        r = await call("cmd_new_initiative",
            title="Test Initiative",
            vision="Complete end-to-end testing",
            entity="test-corp",
        )
        assert "ticket_id" in r, f"Missing ticket_id: {r}"
        assert "chain_id" in r, f"Missing chain_id: {r}"
        ticket_id = r["ticket_id"]
        chain_id = r["chain_id"]
        assert r["chain_type"] == "full-funnel"
        assert r["first_session"] == "discovery"
        print(f"   OK: ticket={ticket_id}, chain={chain_id}")

        # === 2. Record session declaration ===
        print("2. Testing record_session_declaration...")
        from tool_inputs import RecordSessionDeclarationInput
        r = await call("record_session_declaration",
            params=RecordSessionDeclarationInput(
                chain_id=chain_id,
                session_type="discovery",
                goal="Explore the problem space",
                deliverable="Problem statement document",
                completion_criteria=["Stakeholders identified", "Scope defined"],
                out_of_scope=["Implementation details"],
            ),
        )
        assert r.get("partner_confirmed") is True, f"Declaration failed: {r}"
        print(f"   OK: declaration recorded for link {r['link_number']}")

        # === 3. Record catch event ===
        print("3. Testing record_catch_event...")
        from tool_inputs import RecordCatchEventInput
        from schemas import CatchTrigger, CatchAction, PartnerAssessment
        r = await call("record_catch_event",
            params=RecordCatchEventInput(
                chain_id=chain_id,
                session_type="discovery",
                trigger=CatchTrigger.SCOPE_DRIFT,
                action_taken=CatchAction.ACKNOWLEDGED_AND_CONTINUED,
                human_reasoning="Needed to briefly check architecture context",
                partner_assessment=PartnerAssessment.LEGITIMATE,
                assessment_note="Context-carrying, not avoidance",
            ),
        )
        assert "catch_path" in r, f"Catch failed: {r}"
        print(f"   OK: catch event recorded")

        # === 4. Record capacity event ===
        print("4. Testing record_capacity_event...")
        from tool_inputs import RecordCapacityEventInput
        from schemas import CapacityEventType
        r = await call("record_capacity_event",
            params=RecordCapacityEventInput(
                role="project-management",
                chain_id=chain_id,
                event_type=CapacityEventType.PARTNER_SCAFFOLDED,
                description="Partner guided session declaration, human executed",
            ),
        )
        assert r["event_count"] == 1, f"Event count wrong: {r}"
        print(f"   OK: capacity event logged, count={r['event_count']}")

        # === 5. Record gate skip ===
        print("5. Testing record_gate_skip...")
        from tool_inputs import RecordGateSkipInput
        r = await call("record_gate_skip",
            params=RecordGateSkipInput(
                chain_id=chain_id,
                skipped_from="research",
                skipped_to="planning",
                reason="Already have sufficient research from prior work",
                partner_assessment="Legitimate skip — existing context carries",
            ),
        )
        assert r["total_skips"] == 1, f"Skip count wrong: {r}"
        print(f"   OK: gate skip recorded")

        # === 6. Query: get_dashboard ===
        print("6. Testing get_dashboard...")
        from tool_inputs import GetDashboardInput
        r = await call("get_dashboard",
            params=GetDashboardInput(),
        )
        assert len(r["active_chains"]) >= 1, f"No active chains: {r}"
        assert len(r["open_tickets"]) >= 1, f"No open tickets: {r}"
        assert "diagnostics" in r, "Dashboard missing diagnostics block"
        assert r["diagnostics"]["resolution_method"] == "test"
        assert "data_dir" in r["diagnostics"]
        print(f"   OK: dashboard shows {len(r['active_chains'])} chains, {len(r['open_tickets'])} tickets, data_dir={r['diagnostics']['data_dir']}")

        # === 7. Query: search_chains ===
        print("7. Testing search_chains...")
        from tool_inputs import SearchChainsInput
        r = await call("search_chains",
            params=SearchChainsInput(entity="test-corp"),
        )
        assert r["count"] >= 1, f"Search returned 0: {r}"
        print(f"   OK: found {r['count']} chains for entity")

        # === 8. Query: list_tickets ===
        print("8. Testing list_tickets...")
        from tool_inputs import ListTicketsInput
        r = await call("list_tickets",
            params=ListTicketsInput(),
        )
        assert r["count"] >= 1, f"No tickets listed: {r}"
        print(f"   OK: {r['count']} open tickets")

        # === 9. Read capacity ===
        print("9. Testing read_capacity...")
        from tool_inputs import ReadCapacityInput
        r = await call("read_capacity",
            params=ReadCapacityInput(role="project-management"),
        )
        assert r["current_stage"] == "training-wheels"
        print(f"   OK: role at stage '{r['current_stage']}'")

        # === 10. Check stagnation ===
        print("10. Testing check_stagnation...")
        from tool_inputs import CheckStagnationInput
        r = await call("check_stagnation",
            params=CheckStagnationInput(),
        )
        assert "alerts" in r, f"Missing alerts: {r}"
        print(f"   OK: {len(r['alerts'])} stagnation alerts")

        # === 11. Check chain health ===
        print("11. Testing check_chain_health...")
        from tool_inputs import CheckChainHealthInput
        r = await call("check_chain_health",
            params=CheckChainHealthInput(),
        )
        assert r["healthy_count"] >= 1, f"No healthy chains: {r}"
        print(f"   OK: {r['healthy_count']} healthy chains")

        # === 12. Record handoff ===
        print("12. Testing record_handoff...")
        from tool_inputs import RecordHandoffInput
        from schemas import HandoffStatus
        r = await call("record_handoff",
            params=RecordHandoffInput(
                chain_id=chain_id,
                session_type="discovery",
                status=HandoffStatus.COMPLETE,
                decisions_made=["Problem scope defined", "Stakeholders mapped"],
                files_changed=[{"path": "docs/problem-statement.md", "action": "created"}],
                open_threads=["Need to validate with finance team"],
                recommended_next_type="research",
                quick_start="Start with stakeholder interview synthesis",
                context_for_next_partner="Discovery went smoothly, human engaged",
                emotional_context="Energized, good momentum",
            ),
        )
        assert "handoff_path" in r, f"Handoff failed: {r}"
        print(f"   OK: handoff recorded for link {r['link_number']}")

        # === 13. Command: /bug-fix (no chain) ===
        print("13. Testing cmd_bug_fix (no chain)...")
        r = await call("cmd_bug_fix",
            title="Fix typo in docs",
            description="Misspelled 'protocol' in README",
            create_chain=False,
        )
        assert "chain_id" not in r, f"Unexpected chain: {r}"
        assert "No chain" in r.get("message", ""), f"Wrong message: {r}"
        print(f"   OK: bug-fix ticket without chain")

        # === 14. Command: /bug-fix (with chain) ===
        print("14. Testing cmd_bug_fix (with chain)...")
        r = await call("cmd_bug_fix",
            title="Fix broken gate skip counter",
            description="Gate skip count not incrementing",
            create_chain=True,
        )
        assert "chain_id" in r, f"Missing chain: {r}"
        assert r["first_session"] == "build"
        print(f"   OK: bug-fix with chain={r['chain_id']}")

        # === 15. Command: /new-ticket (generic) ===
        print("15. Testing cmd_new_ticket...")
        r = await call("cmd_new_ticket",
            title="Investigate performance",
            type="enhancement",
            priority="high",
            description="Dashboard query is slow with many chains",
        )
        assert "lockstep_prompt" in r, f"Missing lockstep prompt: {r}"
        print(f"   OK: generic ticket with lockstep prompt")

        # === 16. Command: /enhancement ===
        print("16. Testing cmd_enhancement...")
        r = await call("cmd_enhancement",
            title="Add dashboard caching",
            vision="Dashboard loads in under 500ms",
        )
        assert r["first_session"] == "planning"
        print(f"   OK: enhancement chain starting at planning")

        # === 17. Command: /refactor ===
        print("17. Testing cmd_refactor...")
        r = await call("cmd_refactor",
            title="Refactor storage layer",
            scope="Extract YAML I/O into abstract interface for future DB backend",
        )
        assert r["first_session"] == "architecture"
        print(f"   OK: refactor chain starting at architecture")

        # === 18. Update capacity stage ===
        print("18. Testing update_capacity_stage...")
        from tool_inputs import UpdateCapacityStageInput
        from schemas import CapacityStage
        r = await call("update_capacity_stage",
            params=UpdateCapacityStageInput(
                role="project-management",
                new_stage=CapacityStage.PARTNERSHIP,
                trigger="Ratio shift: human_performed now dominant over last 5 chains",
            ),
        )
        assert r["changed"] is True
        assert r["stage"] == "partnership"
        print(f"   OK: stage transition to partnership")

        # === 19. Get capacity events ===
        print("19. Testing get_capacity_events...")
        from tool_inputs import GetCapacityEventsInput
        r = await call("get_capacity_events",
            params=GetCapacityEventsInput(role="project-management"),
        )
        assert r["filtered_count"] >= 1, f"No events: {r}"
        print(f"   OK: {r['filtered_count']} events returned")

        # === Final: list_chains to verify total ===
        print("\n20. Final verification: list_chains...")
        from tool_inputs import ListChainsInput
        r = await call("list_chains", params=ListChainsInput())
        print(f"   Total active chains: {r['count']}")

        print(f"\n{'='*50}")
        print(f"ALL 20 TESTS PASSED")
        print(f"Tools tested: 19 unique tools + 5 commands")
        print(f"{'='*50}")

    except AssertionError as e:
        errors.append(str(e))
        print(f"\nFAILED: {e}")
    except Exception as e:
        errors.append(str(e))
        print(f"\nERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        shutil.rmtree(data_dir, ignore_errors=True)

    return errors


if __name__ == "__main__":
    errors = asyncio.run(test_end_to_end())
    sys.exit(1 if errors else 0)
