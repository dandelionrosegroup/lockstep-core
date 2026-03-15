# Lockstep Chain Protocol

Chain-based project tracking for Human+AI collaboration. An MCP server that gives your AI coding assistant persistent memory across sessions — chains link work together, tickets track what needs doing, and handoffs preserve context so nothing gets lost between conversations.

## Who is this for?

Anyone using AI coding assistants (Claude, etc.) who's tired of re-explaining context every session. Lockstep is especially useful if you:

- Work on multi-session projects where continuity matters
- Want structured session types (discovery, planning, build, review) without rigid enforcement
- Are neurodivergent and benefit from external scaffolding for executive function
- Want your AI partner to track growth and capacity over time

## Features

- **37 tools + 5 commands** for full project lifecycle management
- **Chain-based tracking** — sessions link together as a chain of work
- **YAML-defined chain types** — full-funnel, enhancement, refactor, bug-fix out of the box, or create your own
- **Progressive disclosure** — early phases show fewer fields to reduce cognitive load; information surfaces as it becomes relevant
- **Ticket promotion** — standalone tickets can be promoted into chains when they grow; related tickets discovered automatically
- **Session types** — discovery, research, planning, architecture, build, review
- **Structured handoffs** — decisions, files changed, open threads, and next-session recommendations transfer between conversations
- **Capacity tracking** — growth stages (training-wheels → partnership → safety-net) with event logging
- **Advisory, not enforcing** — the protocol flags and explains, never blocks
- **Fully local** — all data stored as YAML files on your machine, no network access
- **Human-readable data** — inspect, edit, or version-control your project data directly

## Installation

### From Anthropic Directory (Claude Desktop)

1. Find "Lockstep Core" in the Anthropic Directory
2. Click Install
3. When prompted, choose a data directory (default: `~/.lockstep/data`)

### MCPB Bundle (Manual)

1. Download `lockstep-core.mcpb` from the [latest release](https://github.com/dandelionrosegroup/lockstep-core/releases)
2. Open it with Claude Desktop (double-click or drag in)
3. When prompted, choose a data directory (default: `~/.lockstep/data`)

### Manual Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
git clone https://github.com/dandelionrosegroup/lockstep-core.git
cd lockstep-core
```

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "lockstep": {
      "command": "uv",
      "args": ["run", "--python", "3.11", "--with", "mcp>=1.0.0", "--with", "pydantic>=2.0.0", "--with", "PyYAML>=6.0", "src/server.py"],
      "cwd": "/path/to/lockstep-core",
      "env": {
        "LOCKSTEP_DATA_DIR": "/path/to/your/data"
      }
    }
  }
}
```

## Configuration

Lockstep needs one setting: a **data directory** where it stores chains, tickets, and capacity data.

- **Default:** `~/.lockstep/data`
- **Custom:** Set `LOCKSTEP_DATA_DIR` environment variable or configure during MCPB install
- Lockstep creates subdirectories automatically (`chains/`, `tickets/`, `capacity/`, `declarations/`, `handoffs/`, `catches/`, `archive/`)

## Usage Examples

### Start a new initiative

Create a ticket, chain, and first session in one command.

**User prompt:**
> "Create a new initiative called 'Build user authentication' with the vision 'Users can sign up, log in, and manage their accounts.'"

**Tool call:** `cmd_new_initiative`

```json
{
  "title": "Build user authentication",
  "vision": "Users can sign up, log in, and manage their accounts."
}
```

**Response:**
```json
{
  "ticket_id": "TICKET-001",
  "chain_id": "build-user-authentication",
  "chain_type": "full-funnel",
  "first_session": "discovery",
  "link_number": 1,
  "message": "Initiative created. Discovery session is active. Record your session declaration."
}
```

### Promote a ticket into a chain

When a standalone ticket grows in scope, promote it to get chain tracking with automatic discovery of related work.

**User prompt:**
> "Promote TICKET-005 into a chain. The completion vision is 'OAuth fully integrated and tested.'"

**Tool call:** `promote_ticket`

```json
{
  "ticket_id": "TICKET-005",
  "completion_vision": "OAuth fully integrated and tested"
}
```

**Response:**
```json
{
  "promoted": true,
  "ticket_id": "TICKET-005",
  "chain_id": "add-oauth-support",
  "chain_type": "enhancement",
  "first_session": "planning",
  "nesting_candidates": [
    {
      "ticket_id": "TICKET-008",
      "title": "Review Auth Flows",
      "shared_tags": ["auth"]
    }
  ],
  "candidate_message": "Found 1 related ticket(s) that could be nested.",
  "message": "Ticket promoted to chain 'add-oauth-support'. Planning session is active."
}
```

### Record a handoff

Capture session context so the next conversation can pick up seamlessly.

**User prompt:**
> "Record a handoff — we decided on JWT tokens and bcrypt for passwords. Files changed: auth.py (created), models.py (modified). Next session should be Planning."

**Tool call:** `record_handoff`

```json
{
  "chain_id": "build-user-authentication",
  "session_type": "discovery",
  "status": "complete",
  "decisions_made": ["JWT tokens for auth", "bcrypt for password hashing"],
  "files_changed": [
    {"path": "auth.py", "action": "created"},
    {"path": "models.py", "action": "modified"}
  ],
  "recommended_next_type": "planning",
  "quick_start": "Define API routes, data models, and auth middleware based on JWT+bcrypt decisions."
}
```

## Tools Reference

### Chain Lifecycle (15 tools)
| Tool | Description |
|------|-------------|
| `create_chain` | Create a new chain from a ticket |
| `read_chain` | Read chain state (filtered by progressive disclosure) |
| `get_chain_status` | Lightweight status check |
| `set_chain_status` | Update chain status |
| `set_chain_entity` | Tag chain with entity ownership |
| `update_chain_metadata` | Update vision, entity, capacity role |
| `add_chain_link` | Add a new session link |
| `complete_chain_link` | Mark a link as complete |
| `pause_chain` | Pause chain (preserves state) |
| `resume_chain` | Resume a paused chain |
| `complete_chain` | Mark chain complete (auto-closes ticket for bug-fix/maintenance) |
| `archive_chain` | Move to archive with retention metadata |
| `branch_chain` | Fork when work splits |
| `spawn_child_chain` | Cross-type fork with spawn reason (e.g. infrastructure → content) |
| `rename_chain` | Rename chain and update all cross-references |

### Ticket Lifecycle (7 tools)
| Tool | Description |
|------|-------------|
| `create_ticket` | Create ticket with auto-assigned ID |
| `read_ticket` | Read full ticket state |
| `update_ticket` | Update metadata and append notes (returns promotion nudge at 3+ notes) |
| `close_ticket` | Close ticket (advisory: flags if chain incomplete) |
| `tag_ticket` | Add or remove tags (returns promotion nudge if applicable) |
| `link_ticket_chain` | Associate ticket with chain (auto-detects child tickets) |
| `promote_ticket` | Promote standalone ticket into a chain with candidate scanning |

### Capacity Tracking (5 tools)
| Tool | Description |
|------|-------------|
| `read_capacity` | Read capacity role data |
| `update_capacity_stage` | Transition between growth stages |
| `record_capacity_event` | Log a capacity-relevant event |
| `get_capacity_events` | Query capacity event history |
| `check_stagnation` | Check for stalled growth |

### Query Tools (6 tools)
| Tool | Description |
|------|-------------|
| `search_chains` | Filter chains by entity, status, type, date |
| `list_chains` | List all active chains |
| `search_tickets` | Filter tickets by type, entity, priority |
| `list_tickets` | List all open tickets |
| `get_dashboard` | Overview with progressive disclosure per chain phase |
| `check_chain_health` | Find stale or blocked chains |

### Session Support (4 tools)
| Tool | Description |
|------|-------------|
| `record_session_declaration` | Write session declaration (goal, deliverable, criteria) |
| `record_handoff` | Write session-end handoff with context for next session |
| `record_gate_skip` | Log when session type sequence is skipped |
| `record_catch_event` | Log scope drift or momentum shift |

### Commands (5 shortcuts)
| Command | Description |
|---------|-------------|
| `cmd_new_ticket` | Create a ticket (generic) |
| `cmd_new_initiative` | Ticket + full-funnel chain + discovery session |
| `cmd_enhancement` | Ticket + enhancement chain + planning session |
| `cmd_refactor` | Ticket + refactor chain + architecture session |
| `cmd_bug_fix` | Bug-fix ticket, optionally with chain |

## Creating Custom Chain Types

Chain types are defined as YAML files in `templates/`. Drop a new file to create a new chain type — no code changes required.

### Template Format

```yaml
# templates/your-type.yaml
chain_type: your-type
display_name: Your Type
phases: [planning, build, review]
autonomous_eligible: false
required_fields:
  - completion_vision
optional_fields:
  - capacity_role
  - parent_chain
progressive_disclosure:
  planning:
    show: [completion_vision, entity, tags]
    prompt: "What are we building and why?"
  build:
    show: [all]
    prompt: null
  review:
    show: [all]
    prompt: "Does this meet the completion vision?"
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `chain_type` | Yes | Unique identifier (kebab-case) |
| `display_name` | Yes | Human-readable name |
| `phases` | Yes | Ordered list of session types this chain walks through |
| `autonomous_eligible` | No | Can AI proceed without human review? (default: false) |
| `required_fields` | No | Fields required at chain creation |
| `optional_fields` | No | Fields that may be set later |
| `progressive_disclosure` | No | Per-phase field visibility and prompts |

### Progressive Disclosure

Each phase can define:
- **`show`**: List of chain fields visible during this phase. Use `[all]` to show everything.
- **`prompt`**: Optional guidance text surfaced to the AI partner during this phase.

Available fields for `show`: `completion_vision`, `entity`, `tags`, `capacity_role`, `parent_chain`, `child_chains`, `child_tickets`, `spawn_reason`, `expected_sequence`, `gate_skips`, `all`.

Core structural fields (`chain_id`, `title`, `status`, `links`, etc.) are always visible regardless of disclosure rules.

### Built-in Chain Types

| Type | Phases | Autonomous |
|------|--------|-----------|
| `full-funnel` | discovery → research → planning → architecture → build → review | No |
| `enhancement` | planning → architecture → build → review | No |
| `refactor` | architecture → build → review | No |
| `bug-fix` | build → review | Yes |

## Migrating from v0.1.0

If you have existing v0.1.0 data, run the migration script:

```bash
python scripts/migrate_v1_to_v2.py ~/.lockstep/data
```

This creates a backup, renames `template` to `chain_type`, and bumps the schema version. The server also auto-migrates any v1 files it encounters on read, so migration is optional but recommended for clean data.

## Design Principles

1. **Advisory, not enforcing.** The protocol flags and explains — it never blocks. If you want to skip from Discovery straight to Build, it records the skip and moves on.
2. **Make the unconscious conscious.** Session handoffs, catch events, and capacity tracking illuminate patterns over time without forcing behavior change.
3. **Scaffold growth, respect autonomy.** Growth stages (training-wheels → partnership → safety-net) make the path of least resistance the productive path, but they're never the only path.
4. **Protocol serves partnership.** If the structure fights the work, the structure bends.

## Data Storage

All data is stored as YAML files in your configured data directory:

```
~/.lockstep/data/
├── chains/          # CHAIN-[kebab-title].yaml
├── tickets/         # TICKET-[number].yaml
├── capacity/        # [role-name].yaml
├── declarations/    # Session declaration records
├── handoffs/        # Session handoff records
├── catches/         # Catch event records
└── archive/         # Completed chains and tickets
    ├── chains/
    └── tickets/
```

YAML files are human-readable and version-controllable. No database required.

## Privacy Policy

Lockstep is a fully local MCP server. It collects no data, makes no network requests, and includes no telemetry. Your project data stays on your machine.

Full policy: [PRIVACY.md](PRIVACY.md)

## Support

- **Issues:** [github.com/dandelionrosegroup/lockstep-core/issues](https://github.com/dandelionrosegroup/lockstep-core/issues)
- **Discussions:** [github.com/dandelionrosegroup/lockstep-core/discussions](https://github.com/dandelionrosegroup/lockstep-core/discussions)

## Contributing

Lockstep is GPL v3 licensed. Contributions welcome.

```bash
# Set up development environment
git clone https://github.com/dandelionrosegroup/lockstep-core.git
cd lockstep-core
python3 -m venv .venv
.venv/bin/pip install mcp pydantic PyYAML

# Run tests
python3 tests/test_integration.py
python3 tests/test_phase2_promotion.py
python3 tests/test_phase3_disclosure.py
```

Check [open issues](https://github.com/dandelionrosegroup/lockstep-core/issues) for good places to start.

## License

[GNU General Public License v3.0](LICENSE) — Copyright (C) 2025-2026 Jack Daniel Williams / Dandelion Rose Group, LLC

Built as part of [Dandelion Rose Group](https://github.com/dandelionrosegroup)'s mission to prove that neurodivergent minds are uniquely wired for AI partnership.
