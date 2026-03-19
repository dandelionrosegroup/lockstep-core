# Lockstep Core v0.2.0 — "Tickets Grow Up"

Chain-based project tracking for Human+AI collaboration. An MCP server that gives your AI assistant persistent memory across sessions.

## What's new in v0.2.0

**Tickets become chains.** The biggest gap in v0.1.0 was that tickets couldn't grow. Now they can — `promote_ticket` turns any standalone ticket into a full chain when the work outgrows its original scope, with automatic scanning for related tickets to nest.

**Chain types are YAML, not code.** Four built-in templates (full-funnel, enhancement, refactor, bug-fix) ship out of the box. Need a custom workflow? Drop a `.yaml` file in `templates/` — no code changes, no version bump.

**Progressive disclosure.** Early-phase work shows only what matters. Discovery sessions surface completion vision and tags; build phases expand to show everything. Less noise when you're exploring, full detail when you're executing.

**Cross-platform support.** Tested on macOS (ARM), Windows 11 Pro (x64), and Linux. 51 tests, zero platform-specific failures. The manifest now declares explicit compatibility and uses the `uv` server type for host-managed Python across all platforms.

## Highlights

- **Ticket promotion** — tickets grow into chains with candidate scanning and nesting
- **YAML-defined chain types** — add new workflow types without touching code
- **Progressive disclosure** — per-phase field visibility reduces cognitive load
- **Child chain spawning** — cross-type forks that preserve lineage
- **Advisory nudges** — soft suggestions when tickets are ready for promotion
- **Schema migration** — v1 → v2 auto-migration with backup script
- **Cross-platform** — verified on macOS, Windows 11, and Linux
- **42 tools + 5 commands** for full project lifecycle management

## Install

### MCPB Bundle (Recommended)
1. Download `lockstep-core.mcpb` from the assets below
2. Open it with Claude Desktop (double-click or drag in)
3. When prompted, choose a data directory (default: `~/.lockstep/data`)

### Manual Setup
See the [README](README.md) for platform-specific instructions (macOS, Windows, Linux).

## Upgrading from v0.1.0

Your existing data works as-is — the server auto-migrates v1 files on read. For a clean migration:

```bash
python scripts/migrate_v1_to_v2.py ~/.lockstep/data
```

Full changelog: [CHANGELOG.md](CHANGELOG.md)

## License

GPL v3 — free to use, modify, and distribute. Modifications must stay open source.

Built by [Dandelion Rose Group](https://github.com/dandelionrosegroup) — proving that neurodivergent minds are uniquely wired for AI partnership.
