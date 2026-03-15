"""Phase 3 tests: progressive disclosure, spawn_child_chain, lifecycle hooks.

Covers disclosure filtering, dashboard summaries, cross-type spawning,
and auto-close vs advisory lifecycle behavior.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from templates import load_templates  # noqa: E402
load_templates()

from server import mcp  # noqa: E402
from schemas import ChainStatus, TicketStatus  # noqa: E402
from storage import read_chain, read_ticket  # noqa: E402
from tool_inputs import (  # noqa: E402
    CompleteChainInput,
    CompleteChainLinkInput,
    GetDashboardInput,
    ReadChainInput,
    SpawnChildChainInput,
)


class FakeContext:
    def __init__(self, data_dir: Path):
        self.request_context = MagicMock()
        self.request_context.lifespan_context = {"data_dir": data_dir}


def setup_data_dir() -> Path:
    data_dir = Path(tempfile.mkdtemp(prefix="lockstep-test-p3-"))
    for subdir in [
        "chains", "tickets", "capacity", "declarations",
        "handoffs", "catches", "archive/chains", "archive/tickets",
    ]:
        (data_dir / subdir).mkdir(parents=True, exist_ok=True)
    return data_dir


def parse(result: str) -> dict:
    return json.loads(result)


async def run_tests():
    tools = mcp._tool_manager._tools
    passed = 0
    failed = 0

    async def call(name: str, **kwargs):
        tool = tools[name]
        return parse(await tool.fn(ctx=ctx, **kwargs))

    # ============================================================
    # TEST GROUP 1: Progressive Disclosure in read_chain
    # ============================================================

    # --- Test 1: Discovery phase hides late-phase fields ---
    print("1. read_chain disclosure — discovery hides capacity_role, child_chains")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_new_initiative",
            title="Disclosure Test",
            vision="Test progressive disclosure",
            entity="AIC",
        )
        chain_id = r["chain_id"]

        r = await call("read_chain",
            params=ReadChainInput(chain_id=chain_id),
        )

        # Should have disclosure metadata
        assert "_disclosure" in r, f"Missing _disclosure: {list(r.keys())}"
        assert r["_disclosure"]["phase"] == "discovery"
        assert "prompt" in r["_disclosure"]

        # Core fields always present
        assert "chain_id" in r
        assert "title" in r
        assert "links" in r
        assert "completion_vision" in r  # Disclosed in discovery

        # Late-phase fields hidden
        assert "capacity_role" not in r, f"capacity_role should be hidden: {r.keys()}"

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # --- Test 2: Build phase shows all fields ---
    print("2. read_chain disclosure — build phase shows all")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_bug_fix",
            title="Build Phase Test",
            description="Test full disclosure in build",
            create_chain=True,
            entity="DRG",
        )
        chain_id = r["chain_id"]

        r = await call("read_chain",
            params=ReadChainInput(chain_id=chain_id),
        )

        # Build phase: show [all] — everything visible
        assert "completion_vision" in r
        assert "entity" in r
        assert "expected_sequence" in r

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # --- Test 3: Chain with no template shows full data ---
    print("3. read_chain disclosure — no template = full data")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        from tool_inputs import CreateChainInput
        r = await call("create_chain",
            params=CreateChainInput(
                title="No Template Chain",
                ticket_id="TICKET-999",
                completion_vision="Test no template",
            ),
        )
        chain_id = r["chain_id"]

        r = await call("read_chain",
            params=ReadChainInput(chain_id=chain_id),
        )

        # No template = no filtering
        assert "_disclosure" not in r
        assert "completion_vision" in r

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # ============================================================
    # TEST GROUP 2: Dashboard Progressive Disclosure
    # ============================================================

    # --- Test 4: Dashboard uses lighter footprint for early-phase chains ---
    print("4. dashboard — early-phase chain has lighter footprint")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        await call("cmd_new_initiative",
            title="Early Phase Chain",
            vision="Test dashboard disclosure",
            entity="AIC",
        )

        r = await call("get_dashboard", params=GetDashboardInput())
        chains = r["active_chains"]
        assert len(chains) >= 1

        chain_entry = chains[0]
        # Dashboard should have essentials
        assert "chain_id" in chain_entry
        assert "title" in chain_entry
        assert "status" in chain_entry

        # Should have current_phase from disclosure
        assert "current_phase" in chain_entry or "current_session_type" in chain_entry

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # ============================================================
    # TEST GROUP 3: spawn_child_chain
    # ============================================================

    # --- Test 5: Happy path spawn with different type ---
    print("5. spawn_child_chain — cross-type fork")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_new_initiative",
            title="Infrastructure Work",
            vision="Set up CI/CD",
            entity="DRG",
        )
        parent_id = r["chain_id"]

        r = await call("spawn_child_chain",
            params=SpawnChildChainInput(
                parent_chain_id=parent_id,
                title="NeuroAudacity Episode on CI",
                completion_vision="Episode script and outline",
                chain_type="enhancement",
                spawn_reason="CI work surfaced content idea for NeuroAudacity",
            ),
        )

        assert r["parent_chain_id"] == parent_id
        assert r["child_chain_type"] == "enhancement"
        assert r["spawn_reason"] == "CI work surfaced content idea for NeuroAudacity"
        assert r["first_session"] == "planning"  # enhancement starts at planning

        # Verify child chain state
        child = read_chain(data_dir, r["child_chain_id"])
        assert child.chain_type == "enhancement"
        assert child.parent_chain == parent_id
        assert child.spawn_reason == "CI work surfaced content idea for NeuroAudacity"
        assert child.expected_sequence == ["planning", "architecture", "build", "review"]
        assert len(child.links) == 1

        # Verify parent updated
        parent = read_chain(data_dir, parent_id)
        assert r["child_chain_id"] in parent.child_chains

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # --- Test 6: Spawn from nonexistent parent fails ---
    print("6. spawn_child_chain — nonexistent parent rejected")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("spawn_child_chain",
            params=SpawnChildChainInput(
                parent_chain_id="does-not-exist",
                title="Orphan Chain",
                completion_vision="Should fail",
                chain_type="bug-fix",
                spawn_reason="Testing error path",
            ),
        )
        assert r.get("error") == "not_found"

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # --- Test 7: Spawn inherits entity and capacity_role from parent ---
    print("7. spawn_child_chain — inherits parent metadata")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_enhancement",
            title="Parent Enhancement",
            vision="Test inheritance",
            entity="AIC",
        )
        parent_id = r["chain_id"]

        r = await call("spawn_child_chain",
            params=SpawnChildChainInput(
                parent_chain_id=parent_id,
                title="Child Refactor",
                completion_vision="Refactor piece of enhancement",
                chain_type="refactor",
                spawn_reason="Complexity warrants separate refactor track",
            ),
        )

        child = read_chain(data_dir, r["child_chain_id"])
        assert child.entity == "AIC"  # Inherited from parent

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # ============================================================
    # TEST GROUP 4: Lifecycle Hooks
    # ============================================================

    # --- Test 8: Bug-fix chain completion auto-closes ticket ---
    print("8. lifecycle — bug-fix complete_chain auto-closes ticket")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_bug_fix",
            title="Auto Close Bug",
            description="Test auto-close on completion",
            create_chain=True,
        )
        ticket_id = r["ticket_id"]
        chain_id = r["chain_id"]

        # Complete the chain link first
        await call("complete_chain_link",
            params=CompleteChainLinkInput(
                chain_id=chain_id,
                deliverables=["Fix applied"],
            ),
        )

        # Complete the chain — should auto-close ticket
        r = await call("complete_chain",
            params=CompleteChainInput(chain_id=chain_id),
        )
        assert r["changed"] is True
        assert r.get("ticket_auto_closed") == ticket_id, f"Missing auto-close: {r}"

        # Verify ticket is actually closed
        ticket = read_ticket(data_dir, ticket_id)
        assert ticket.status == TicketStatus.CLOSED
        assert ticket.closed is not None

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # --- Test 9: Enhancement chain completion gives advisory (no auto-close) ---
    print("9. lifecycle — enhancement complete_chain gives advisory, no auto-close")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_enhancement",
            title="Advisory Test",
            vision="Test advisory on completion",
        )
        ticket_id = r["ticket_id"]
        chain_id = r["chain_id"]

        await call("complete_chain_link",
            params=CompleteChainLinkInput(
                chain_id=chain_id,
                deliverables=["Enhancement delivered"],
            ),
        )

        r = await call("complete_chain",
            params=CompleteChainInput(chain_id=chain_id),
        )
        assert r["changed"] is True
        assert "ticket_auto_closed" not in r, f"Should NOT auto-close: {r}"

        # Should have advisory
        advisories = r.get("advisories", [])
        has_close_advisory = any("consider closing" in a for a in advisories)
        assert has_close_advisory, f"Missing close advisory: {advisories}"

        # Ticket should still be open/active
        ticket = read_ticket(data_dir, ticket_id)
        assert ticket.status != TicketStatus.CLOSED

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # --- Test 10: Auto-close skipped if ticket already closed ---
    print("10. lifecycle — auto-close skips already-closed ticket")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_bug_fix",
            title="Pre Closed Bug",
            description="Ticket closed before chain completes",
            create_chain=True,
        )
        ticket_id = r["ticket_id"]
        chain_id = r["chain_id"]

        # Close ticket manually first
        from tool_inputs import CloseTicketInput
        await call("close_ticket", params=CloseTicketInput(ticket_id=ticket_id))

        await call("complete_chain_link",
            params=CompleteChainLinkInput(chain_id=chain_id, deliverables=["Done"]),
        )

        r = await call("complete_chain",
            params=CompleteChainInput(chain_id=chain_id),
        )
        assert r["changed"] is True
        # Should NOT auto-close (already closed)
        assert "ticket_auto_closed" not in r

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # --- Test 11: complete_chain idempotent (unchanged on second call) ---
    print("11. lifecycle — complete_chain idempotent")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_bug_fix",
            title="Idempotent Complete",
            description="Test double completion",
            create_chain=True,
        )
        chain_id = r["chain_id"]

        await call("complete_chain_link",
            params=CompleteChainLinkInput(chain_id=chain_id, deliverables=["Done"]),
        )

        r1 = await call("complete_chain", params=CompleteChainInput(chain_id=chain_id))
        assert r1["changed"] is True

        r2 = await call("complete_chain", params=CompleteChainInput(chain_id=chain_id))
        assert r2["changed"] is False

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # ============================================================
    # SUMMARY
    # ============================================================
    total = passed + failed
    print(f"\n{'='*50}")
    print(f"Phase 3 tests: {passed}/{total} passed")
    if failed:
        print(f"FAILURES: {failed}")
    else:
        print("ALL TESTS PASSED")
    print(f"{'='*50}")

    return failed


if __name__ == "__main__":
    failures = asyncio.run(run_tests())
    sys.exit(1 if failures else 0)
