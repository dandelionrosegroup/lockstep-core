# Lockstep Chain Protocol

Chain-based project tracking for Human+AI collaboration. An MCP server that gives your AI coding assistant persistent memory across sessions — chains link work together, tickets track what needs doing, and handoffs preserve context so nothing gets lost between conversations.

## Who is this for?

Anyone using AI coding assistants (Claude, etc.) who's tired of re-explaining context every session. Lockstep is especially useful if you:

- Work on multi-session projects where continuity matters
- Want structured session types (discovery, planning, build, review) without rigid enforcement
- Are neurodivergent and benefit from external scaffolding for executive function
- Want your AI partner to track growth and capacity over time

## Install

### MCPB Bundle (Claude Desktop)

1. Download `lockstep-chain-protocol-0.1.0.mcpb` from the [latest release](https://github.com/dandelionrosegroup/lockstep-core/releases)
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
      "args": ["run", "--with", "mcp>=1.0.0", "--with", "pydantic>=2.0.0", "--with", "PyYAML>=6.0", "src/server.py"],
      "cwd": "/path/to/lockstep-core",
      "env": {
        "LOCKSTEP_DATA_DIR": "/path/to/your/data"
      }
    }
  }
}
```

## Quick Start

Once installed, your AI assistant has access to 35 tools and 5 commands. Here's the typical flow:

### 1. Create your first initiative

Tell your assistant:
> "Create a new initiative called 'Build user authentication' with the vision 'Users can sign up, log in, and manage their accounts.'"

This creates a ticket, a chain with the full-funnel template (Discovery → Research → Planning → Architecture → Build → Review), and starts a Discovery session.

### 2. Work through sessions

Each session is a **link** in the chain. When you finish a session, record a handoff:
> "Record a handoff for this session — we decided on JWT tokens, files changed were auth.py and models.py, and next session should be Planning."

### 3. Pick up where you left off

Next conversation, your assistant can read the chain and last handoff to get full context:
> "Read the chain for 'build-user-authentication' and show me the last handoff."

No more re-explaining. The chain remembers.

## Tools Reference

### Chain Lifecycle (14 tools)
| Tool | Description |
|------|-------------|
| `create_chain` | Create a new chain from a ticket |
| `read_chain` | Read full chain state |
| `get_chain_status` | Lightweight status check |
| `set_chain_status` | Update chain status |
| `set_chain_entity` | Tag chain with entity ownership |
| `update_chain_metadata` | Update vision, entity, capacity role |
| `add_chain_link` | Add a new session link |
| `complete_chain_link` | Mark a link as complete |
| `pause_chain` | Pause chain (preserves state) |
| `resume_chain` | Resume a paused chain |
| `complete_chain` | Mark entire chain complete |
| `archive_chain` | Move to archive with retention metadata |
| `branch_chain` | Fork when work splits |
| `rename_chain` | Rename chain and update all cross-references |

### Ticket Lifecycle (6 tools)
| Tool | Description |
|------|-------------|
| `create_ticket` | Create ticket with auto-assigned ID |
| `read_ticket` | Read full ticket state |
| `update_ticket` | Update metadata and append notes |
| `close_ticket` | Close ticket (advisory: flags if chain incomplete) |
| `tag_ticket` | Add or remove tags |
| `link_ticket_chain` | Associate ticket with chain |

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
| `get_dashboard` | Overview of chains, tickets, capacity |
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

## Contributing

Lockstep is GPL v3 licensed. Contributions welcome.

```bash
# Set up development environment
git clone https://github.com/dandelionrosegroup/lockstep-core.git
cd lockstep-core
python3 -m venv .venv
.venv/bin/pip install mcp pydantic PyYAML pytest pytest-asyncio

# Run tests
.venv/bin/python3 -m pytest tests/ -v
```

Check [open issues](https://github.com/dandelionrosegroup/lockstep-core/issues) for good places to start. Issues tagged `good first issue` are well-scoped and documented.

## License

[GNU General Public License v3.0](LICENSE) — Copyright (C) 2025-2026 Jack Daniel Williams / Dandelion Rose Group, LLC

Built as part of [Dandelion Rose Group](https://github.com/dandelionrosegroup)'s mission to prove that neurodivergent minds are uniquely wired for AI partnership.
