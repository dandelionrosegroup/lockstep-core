# Changelog

All notable changes to Lockstep Core are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **A note on iteration:** This changelog tells the real story of how Lockstep
> was built — not a polished highlight reel. v0.1.0 shipped with a hardcoded
> enum for chain types and no way to promote a ticket into a chain. v0.2.0
> exists because we used v0.1.0, hit its edges, and rebuilt those parts better.
> That's not failure — that's the process working. If you're neurodivergent and
> building something, know that "ship it, learn from it, improve it" is not
> just acceptable — it's the only honest way to build. Perfection at launch is
> a myth that keeps good ideas trapped in people's heads.

---

## [0.2.0] — 2026-03-15

The "Tickets Grow Up" release. Everything we learned from daily-driving v0.1.0
got folded back in: tickets can become chains, chain types are defined in YAML
instead of code, and progressive disclosure means early-phase work isn't buried
under fields that don't matter yet. The storage layer, MCP server infrastructure,
session/handoff tooling, and capacity system are unchanged — this is an evolution,
not a rewrite.

### Added

- **Ticket promotion** (`promote_ticket` tool) — standalone tickets can now be
  promoted into full chains when they outgrow their original scope. Scans open
  tickets by entity and tags to surface related work as nesting candidates.
  This was the single biggest missing piece in v0.1.0: we kept creating tickets
  that grew into multi-session efforts with no clean path to chain them.

- **Advisory nudges** — when a ticket accumulates 3+ notes or links to 2+
  related tickets, tool responses include a soft suggestion to consider
  promotion. Advisory, never enforcing — consistent with Lockstep's core
  design principle.

- **YAML-defined chain types** (`templates/` directory) — chain types are now
  defined as YAML template files loaded at runtime. Adding a new chain type
  means dropping a `.yaml` file in `templates/` — no code changes required.
  Ships with four battle-tested templates:
  - `full-funnel` — discovery → research → planning → architecture → build → review
  - `enhancement` — planning → architecture → build → review
  - `refactor` — architecture → build → review
  - `bug-fix` — build → review (autonomous-eligible)

- **Progressive disclosure** — each chain type template defines per-phase field
  visibility. Early phases show only what matters (completion vision, entity, tags);
  later phases expand to show everything. `read_chain`, `get_dashboard`, and query
  tools all respect disclosure rules. The goal: reduce cognitive load during
  discovery and planning, surface complexity only when it's actionable. Full data
  always accessible via direct YAML file read for power users.

- **Child chain spawning** (`spawn_child_chain` tool) — chains can now fork into
  typed child chains with a `spawn_reason` field capturing *why* the fork happened.
  This preserves chain lineage as research data: the pattern of infrastructure work
  spawning content ideas (e.g., a build session surfacing a podcast episode concept)
  maps cross-domain ideation patterns that are especially common in neurodivergent
  workflows.

- **Child ticket nesting** — chains track `child_tickets` with bidirectional
  references. `link_ticket_chain` auto-detects child relationships. Identity
  continuity preserved: TICKET-NNN references always resolve post-promotion.

- **Lifecycle hooks** — `complete_chain` now auto-closes the origin ticket for
  `bug-fix` and `maintenance` chain types (autonomous-eligible work). For all
  other chain types, completion returns an advisory about open tickets rather
  than silently closing them. This was requested in TICKET-055 and TICKET-059.

- **Schema version tracking** — YAML files now carry `schema_version: "2.0"`.
  The loader checks version on read and auto-migrates v1 files on first access,
  so mixed-version data directories work without manual intervention.

- **Migration script** (`scripts/migrate_v1_to_v2.py`) — batch-updates all
  existing chain and ticket YAML files from v1 to v2 schema. Creates a full
  backup before any writes. Renames `template` field to `chain_type`, populates
  `schema_version`, and preserves all existing data. Rollback is one command
  away if anything goes wrong.

- **GitHub Actions CI** — automated test suite runs on every push and pull
  request across Python 3.11, 3.12, and 3.13. Four test files, 50 tests
  covering integration, promotion, progressive disclosure, spawning, and
  lifecycle hooks.

- **Custom chain type documentation** — README now includes full documentation
  on the YAML template format, field reference, and examples for creating your
  own chain types.

### Changed

- **Chain schema** — `template` field (Python enum) replaced by `chain_type`
  field (string matching a YAML template). Chains also gain `child_tickets`,
  `child_chains`, and `spawn_reason` fields. This is the core structural change
  that enables the promotion model.

- **Dashboard output** — `get_dashboard` now respects progressive disclosure,
  showing lighter-weight summaries for chains in early phases and richer detail
  for chains in build/review phases.

- **`read_chain` output** — filtered by the chain's current phase and its
  template's disclosure rules. Fields not relevant to the current phase are
  omitted from the response (still stored in YAML, just not surfaced).

- **`update_ticket` responses** — now include advisory nudge when the ticket
  has 3+ notes, suggesting promotion may be worth considering.

- **`tag_ticket` responses** — now include advisory nudge when applicable,
  surfacing promotion candidates based on shared tags.

- **README** — complete overhaul with usage examples, custom chain type docs,
  migration instructions, tools reference table, and contributing guide.

- **Manifest** — Python version pinned to 3.11 (`--python 3.11` in mcp_config
  args) for consistent cross-platform behavior.

- **Version** — bumped to 0.2.0 in pyproject.toml and manifest.json.

### Fixed

- **Python version pinning** — manifest now specifies `--python 3.11` to prevent
  uv from selecting an incompatible Python version on systems with multiple
  installations. This was the root cause of several installation failures
  reported against v0.1.0. (TICKET-061)

- **MCPB download filename** — README now references the correct `.mcpb` asset
  filename matching the GitHub release.

### Removed

- **`ChainTemplate` enum** — replaced entirely by the YAML template system.
  The enum was a quick-and-dirty solution for v0.1.0 that worked but didn't
  scale. Hardcoding workflow types in Python meant every new chain type required
  a code change, a version bump, and a new release. YAML templates make this
  a configuration concern instead of a code concern — exactly where it belongs.

### Migration

If upgrading from v0.1.0 with existing data:

```bash
python scripts/migrate_v1_to_v2.py ~/.lockstep/data
```

The script creates a backup, migrates all YAML files, and reports results. The
server also auto-migrates v1 files on read, so manual migration is recommended
but not strictly required.

---

## [0.1.0] — 2026-03-10

The first public release. Everything started here — shipped from a private
development environment to a public GitHub repo in a single day. Was it perfect?
No. The chain type system was a hardcoded Python enum. There was no way to
promote a ticket into a chain. Progressive disclosure didn't exist. But it
*worked* — chains linked sessions together, handoffs preserved context, capacity
tracking made growth visible, and the core thesis (advisory, not enforcing)
was solid from day one.

The honest truth: v0.1.0 shipped because "done is better than perfect" and
because the only way to find the real gaps was to use it every day. Five days
of daily use surfaced the exact pain points that became v0.2.0. That's not a
bug in the process — that's the process.

### Added

- **Chain-based project tracking** — the core abstraction. Chains link sessions
  together as a sequence of work, preserving decisions, context, and momentum
  across conversations. Each link represents one session with its type, status,
  deliverables, and handoff context.

- **Ticket system** — lightweight issue tracking integrated with chains. Tickets
  track what needs doing; chains track how it gets done. Auto-assigned sequential
  IDs (TICKET-001, TICKET-002, ...).

- **Session types** — discovery, research, planning, architecture, build, review.
  Each type signals the *kind* of thinking happening in a session. Advisory —
  you can do a build session in a discovery chain if that's what the work needs.

- **Structured handoffs** — `record_handoff` captures decisions made, files
  changed, open threads, and recommendations for the next session. This is what
  makes multi-session AI collaboration actually work: the next conversation
  picks up where the last one left off instead of starting from scratch.

- **Session declarations** — `record_session_declaration` captures the goal,
  expected deliverable, and success criteria at session start. The counterpart
  to handoffs: declarations say what you're trying to do, handoffs say what
  you actually did.

- **Capacity tracking** — growth stages (training-wheels → partnership →
  safety-net) with event logging and stagnation detection. Makes invisible
  progress visible — especially valuable for neurodivergent individuals who
  struggle to recognize their own growth.

- **Gate skip recording** — `record_gate_skip` logs when the expected session
  type sequence is skipped (e.g., jumping from discovery to build). No blocking,
  no enforcement — just a record that the skip happened and why. Over time,
  these records surface patterns (ADHD-driven leapfrogging, scope pressure,
  genuine efficiency) that inform better workflow design.

- **Catch events** — `record_catch_event` logs scope drift, momentum shifts,
  or moments where the protocol catches something the human might have missed.
  Named after the feeling: "good catch."

- **Chain branching** — `branch_chain` forks a chain when work genuinely splits
  into parallel tracks. Preserves lineage so you can trace how the split happened.

- **Dashboard** — `get_dashboard` provides an aggregate view of active chains,
  open tickets, capacity summary, and health alerts in one call.

- **Chain health checks** — `check_chain_health` detects stale, forgotten, or
  blocked chains. Surfaces what's been sitting too long without attention.

- **Fully local storage** — all data stored as human-readable YAML files on
  your machine. No database, no network requests, no telemetry, no data
  collection. Your project data is yours.

- **MCPB packaging** — installable via Claude Desktop's extension system.
  Download the `.mcpb` bundle, double-click, configure your data directory,
  and you're running.

- **Five compound commands** — `cmd_new_initiative`, `cmd_enhancement`,
  `cmd_refactor`, `cmd_bug_fix`, `cmd_new_ticket`. One-shot shortcuts that
  create a ticket, chain, and first session link in a single call.

- **Privacy policy** — published at GitHub Pages. Lockstep collects nothing.
  No analytics, no crash reporting, no usage data. Period.

- **Issue templates** — GitHub issue templates for bug reports and feature
  requests, lowering the barrier for community contributions.

- **Open source under GPL v3** — free to use, modify, and distribute.
  Modifications must stay open source. This is a deliberate choice: tools
  for neurodivergent empowerment should be community property.

### Known Issues at Launch

These were known when v0.1.0 shipped and were accepted as the cost of
shipping sooner rather than later:

- Chain types hardcoded as a Python enum — adding new types required code
  changes. (Fixed in v0.2.0 with YAML templates.)
- No ticket-to-chain promotion path — tickets that grew in scope had to be
  manually recreated as chains. (Fixed in v0.2.0 with `promote_ticket`.)
- No progressive disclosure — all chain fields shown regardless of phase,
  increasing cognitive load during early exploratory work. (Fixed in v0.2.0.)
- Windows installation untested — the manifest assumed macOS/Linux uv paths.
  (Partially addressed in v0.2.0 with Python version pinning; full Windows
  validation pending.)

---

## Links

- **Repository:** https://github.com/dandelionrosegroup/lockstep-core
- **Issues:** https://github.com/dandelionrosegroup/lockstep-core/issues

[0.2.0]: https://github.com/dandelionrosegroup/lockstep-core/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/dandelionrosegroup/lockstep-core/releases/tag/v0.1.0
