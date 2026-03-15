"""Phase 2 tests: promote_ticket, advisory nudges, child ticket nesting.

Covers happy paths and key edge cases per build plan.
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
from schemas import Ticket, TicketNote, TicketStatus, TicketType  # noqa: E402
from storage import read_chain, read_ticket, write_ticket  # noqa: E402
from tool_inputs import PromoteTicketInput  # noqa: E402


class FakeContext:
    def __init__(self, data_dir: Path):
        self.request_context = MagicMock()
        self.request_context.lifespan_context = {"data_dir": data_dir}


def setup_data_dir() -> Path:
    data_dir = Path(tempfile.mkdtemp(prefix="lockstep-test-p2-"))
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
    # TEST GROUP 1: promote_ticket
    # ============================================================

    # --- Test 1: Happy path promotion ---
    print("1. promote_ticket — happy path")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        # Create a standalone ticket
        r = await call("cmd_new_ticket",
            title="Add OAuth Support",
            type="enhancement",
            entity="AIC",
            tags=["auth", "security"],
        )
        ticket_id = r["ticket_id"]

        # Promote it
        r = await call("promote_ticket",
            params=PromoteTicketInput(
                ticket_id=ticket_id,
                completion_vision="OAuth fully integrated",
            ),
        )
        assert r["promoted"] is True, f"Expected promoted=True: {r}"
        assert r["chain_type"] == "enhancement", f"Wrong chain type: {r}"
        assert r["first_session"] == "planning", f"Wrong first session: {r}"
        assert r["chain_id"] == "add-oauth-support", f"Wrong chain_id: {r}"

        # Verify ticket is now linked and active
        ticket = read_ticket(data_dir, ticket_id)
        assert ticket.chain_id == "add-oauth-support"
        assert ticket.status == TicketStatus.ACTIVE

        # Verify chain was created with correct schema
        chain = read_chain(data_dir, "add-oauth-support")
        assert chain.chain_type == "enhancement"
        assert chain.ticket_id == ticket_id
        assert chain.expected_sequence == ["planning", "architecture", "build", "review"]
        assert len(chain.links) == 1
        assert chain.links[0].session_type == "planning"
        assert chain.schema_version == "2.0"

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # --- Test 2: Promote closed ticket (should fail) ---
    print("2. promote_ticket — closed ticket rejected")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_new_ticket",
            title="Closed Work",
            type="bug-fix",
        )
        ticket_id = r["ticket_id"]

        # Close it
        from tool_inputs import CloseTicketInput
        await call("close_ticket", params=CloseTicketInput(ticket_id=ticket_id))

        # Try to promote
        r = await call("promote_ticket",
            params=PromoteTicketInput(
                ticket_id=ticket_id,
                completion_vision="Should fail",
            ),
        )
        assert r.get("error") == "invalid_state", f"Expected invalid_state error: {r}"

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # --- Test 3: Promote ticket already in a chain (should fail) ---
    print("3. promote_ticket — already chained rejected")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        # Create initiative (auto-creates chain)
        r = await call("cmd_new_initiative",
            title="Already Chained",
            vision="Test double promotion",
        )
        ticket_id = r["ticket_id"]

        # Try to promote again
        r = await call("promote_ticket",
            params=PromoteTicketInput(
                ticket_id=ticket_id,
                completion_vision="Should fail",
            ),
        )
        assert r.get("error") == "already_exists", f"Expected already_exists error: {r}"

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # --- Test 4: Promotion with candidate scanning ---
    print("4. promote_ticket — candidate scanning (entity+tags)")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        # Create origin ticket
        r = await call("cmd_new_ticket",
            title="Auth Overhaul",
            type="enhancement",
            entity="AIC",
            tags=["auth", "security"],
        )
        origin_id = r["ticket_id"]

        # Create related ticket (same entity + overlapping tags)
        r = await call("cmd_new_ticket",
            title="Review Auth Flows",
            type="enhancement",
            entity="AIC",
            tags=["auth", "review"],
        )
        related_id = r["ticket_id"]

        # Create unrelated ticket (different entity)
        r = await call("cmd_new_ticket",
            title="Other Work",
            type="bug-fix",
            entity="DRG",
            tags=["auth"],
        )
        unrelated_id = r["ticket_id"]

        # Create ticket with no tag overlap
        r = await call("cmd_new_ticket",
            title="AIC Billing",
            type="enhancement",
            entity="AIC",
            tags=["billing"],
        )
        no_overlap_id = r["ticket_id"]

        # Promote origin
        r = await call("promote_ticket",
            params=PromoteTicketInput(
                ticket_id=origin_id,
                completion_vision="Auth system rebuilt",
            ),
        )
        assert r["promoted"] is True

        # Should find related_id as candidate, NOT unrelated or no-overlap
        candidates = r.get("nesting_candidates", [])
        candidate_ids = [c["ticket_id"] for c in candidates]
        assert related_id in candidate_ids, f"Missing related ticket: {candidate_ids}"
        assert unrelated_id not in candidate_ids, f"Included wrong-entity ticket: {candidate_ids}"
        assert no_overlap_id not in candidate_ids, f"Included no-overlap ticket: {candidate_ids}"

        # Verify shared_tags reported correctly
        related_candidate = next(c for c in candidates if c["ticket_id"] == related_id)
        assert "auth" in related_candidate["shared_tags"]

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # --- Test 5: Promotion with immediate nesting ---
    print("5. promote_ticket — immediate nesting via nest_tickets")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_new_ticket",
            title="Main Feature",
            type="new-initiative",
            entity="DRG",
            tags=["feature"],
        )
        origin_id = r["ticket_id"]

        r = await call("cmd_new_ticket",
            title="Sub Task A",
            type="enhancement",
            entity="DRG",
            tags=["feature"],
        )
        child_a = r["ticket_id"]

        r = await call("cmd_new_ticket",
            title="Sub Task B",
            type="bug-fix",
            entity="DRG",
            tags=["feature"],
        )
        child_b = r["ticket_id"]

        # Promote with immediate nesting
        r = await call("promote_ticket",
            params=PromoteTicketInput(
                ticket_id=origin_id,
                completion_vision="Feature complete",
                nest_tickets=[child_a, child_b],
            ),
        )
        assert r["promoted"] is True
        assert child_a in r.get("nested_tickets", [])
        assert child_b in r.get("nested_tickets", [])

        # Verify chain state
        chain = read_chain(data_dir, r["chain_id"])
        assert chain.ticket_id == origin_id  # Origin stays in ticket_id
        assert child_a in chain.child_tickets
        assert child_b in chain.child_tickets
        assert origin_id not in chain.child_tickets  # Origin never in child_tickets

        # Verify child tickets have chain_id set
        ta = read_ticket(data_dir, child_a)
        assert ta.chain_id == r["chain_id"]
        tb = read_ticket(data_dir, child_b)
        assert tb.chain_id == r["chain_id"]

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # --- Test 6: Promote with explicit chain_type override ---
    print("6. promote_ticket — explicit chain_type override")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_new_ticket",
            title="Upgrade Dependencies",
            type="enhancement",
        )
        ticket_id = r["ticket_id"]

        # Override: use refactor instead of enhancement
        r = await call("promote_ticket",
            params=PromoteTicketInput(
                ticket_id=ticket_id,
                completion_vision="All deps current",
                chain_type="refactor",
            ),
        )
        assert r["chain_type"] == "refactor"
        assert r["first_session"] == "architecture"

        chain = read_chain(data_dir, r["chain_id"])
        assert chain.chain_type == "refactor"
        assert chain.expected_sequence == ["architecture", "build", "review"]

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # ============================================================
    # TEST GROUP 2: Advisory nudges
    # ============================================================

    # --- Test 7: Nudge triggers at 3+ notes ---
    print("7. advisory nudge — triggers at 3 notes")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_new_ticket",
            title="Growing Ticket",
            type="enhancement",
        )
        ticket_id = r["ticket_id"]

        from tool_inputs import UpdateTicketInput

        # Add notes one at a time — no nudge at 1 or 2
        for i in range(1, 3):
            r = await call("update_ticket",
                params=UpdateTicketInput(ticket_id=ticket_id, note=f"Note {i}"),
            )
            assert "promotion_nudge" not in r, f"Premature nudge at note {i}: {r}"

        # Third note should trigger nudge
        r = await call("update_ticket",
            params=UpdateTicketInput(ticket_id=ticket_id, note="Note 3"),
        )
        assert "promotion_nudge" in r, f"Missing nudge at 3 notes: {r}"
        nudge = r["promotion_nudge"]
        assert "3 notes" in nudge["reasons"][0]
        assert nudge["suggested_chain_type"] == "enhancement"

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # --- Test 8: No nudge when ticket already has chain ---
    print("8. advisory nudge — suppressed when already chained")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_new_initiative",
            title="Already Tracked",
            vision="Testing nudge suppression",
        )
        ticket_id = r["ticket_id"]

        from tool_inputs import UpdateTicketInput
        for i in range(5):
            r = await call("update_ticket",
                params=UpdateTicketInput(ticket_id=ticket_id, note=f"Note {i+1}"),
            )

        # Should never nudge — already linked to chain
        assert "promotion_nudge" not in r, f"Spurious nudge on chained ticket: {r}"

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # --- Test 9: No nudge for maintenance tickets ---
    print("9. advisory nudge — suppressed for maintenance type")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_new_ticket",
            title="Update Deps",
            type="maintenance",
        )
        ticket_id = r["ticket_id"]

        from tool_inputs import UpdateTicketInput
        for i in range(4):
            r = await call("update_ticket",
                params=UpdateTicketInput(ticket_id=ticket_id, note=f"Note {i+1}"),
            )

        assert "promotion_nudge" not in r, f"Nudge on maintenance ticket: {r}"

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # --- Test 10: Nudge in tag_ticket response ---
    print("10. advisory nudge — fires from tag_ticket too")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_new_ticket",
            title="Taggable Ticket",
            type="enhancement",
        )
        ticket_id = r["ticket_id"]

        # Pre-load notes to trigger threshold
        from tool_inputs import UpdateTicketInput
        for i in range(3):
            await call("update_ticket",
                params=UpdateTicketInput(ticket_id=ticket_id, note=f"Note {i+1}"),
            )

        # tag_ticket should also carry the nudge
        from tool_inputs import TagTicketInput
        r = await call("tag_ticket",
            params=TagTicketInput(ticket_id=ticket_id, add=["important"]),
        )
        assert "promotion_nudge" in r, f"Missing nudge from tag_ticket: {r}"

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # ============================================================
    # TEST GROUP 3: Child ticket nesting via link_ticket_chain
    # ============================================================

    # --- Test 11: Origin ticket linked — not a child ---
    print("11. link_ticket_chain — origin ticket is NOT a child")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_new_initiative",
            title="Origin Test",
            vision="Test origin vs child",
        )
        ticket_id = r["ticket_id"]
        chain_id = r["chain_id"]

        # Re-link the origin ticket (idempotent case)
        from tool_inputs import LinkTicketChainInput
        r = await call("link_ticket_chain",
            params=LinkTicketChainInput(ticket_id=ticket_id, chain_id=chain_id),
        )
        assert r["is_child_ticket"] is False, f"Origin marked as child: {r}"

        # Verify chain.child_tickets is still empty
        chain = read_chain(data_dir, chain_id)
        assert ticket_id not in chain.child_tickets

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # --- Test 12: Non-origin ticket linked — becomes child ---
    print("12. link_ticket_chain — non-origin becomes child_ticket")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_new_initiative",
            title="Parent Chain",
            vision="Test child nesting",
        )
        origin_id = r["ticket_id"]
        chain_id = r["chain_id"]

        # Create a separate ticket
        r = await call("cmd_new_ticket",
            title="Child Work",
            type="bug-fix",
        )
        child_id = r["ticket_id"]

        # Link it to the chain
        from tool_inputs import LinkTicketChainInput
        r = await call("link_ticket_chain",
            params=LinkTicketChainInput(ticket_id=child_id, chain_id=chain_id),
        )
        assert r["is_child_ticket"] is True, f"Should be child: {r}"

        # Verify bidirectional link
        chain = read_chain(data_dir, chain_id)
        assert child_id in chain.child_tickets
        assert origin_id not in chain.child_tickets

        child = read_ticket(data_dir, child_id)
        assert child.chain_id == chain_id

        passed += 1
        print("   PASS")
    except Exception as e:
        failed += 1
        print(f"   FAIL: {e}")
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    # --- Test 13: Duplicate child link is idempotent ---
    print("13. link_ticket_chain — duplicate child link idempotent")
    data_dir = setup_data_dir()
    ctx = FakeContext(data_dir)
    try:
        r = await call("cmd_new_initiative",
            title="Idempotent Test",
            vision="Test double-link",
        )
        chain_id = r["chain_id"]

        r = await call("cmd_new_ticket",
            title="Link Me Twice",
            type="enhancement",
        )
        child_id = r["ticket_id"]

        from tool_inputs import LinkTicketChainInput
        # Link twice
        await call("link_ticket_chain",
            params=LinkTicketChainInput(ticket_id=child_id, chain_id=chain_id),
        )
        await call("link_ticket_chain",
            params=LinkTicketChainInput(ticket_id=child_id, chain_id=chain_id),
        )

        # Should appear only once in child_tickets
        chain = read_chain(data_dir, chain_id)
        assert chain.child_tickets.count(child_id) == 1, \
            f"Duplicate in child_tickets: {chain.child_tickets}"

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
    print(f"Phase 2 tests: {passed}/{total} passed")
    if failed:
        print(f"FAILURES: {failed}")
    else:
        print("ALL TESTS PASSED")
    print(f"{'='*50}")

    return failed


if __name__ == "__main__":
    failures = asyncio.run(run_tests())
    sys.exit(1 if failures else 0)
