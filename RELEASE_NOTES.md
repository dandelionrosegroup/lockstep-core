# Lockstep Core v0.2.1 — Patch Release

Chain-based project tracking for Human+AI collaboration. An MCP server that gives your AI assistant persistent memory across sessions.

## What's in this patch

**Startup diagnostics.** When we tested v0.2.0 from a fresh user perspective (not the creator's), the server started with an empty dashboard and no errors. Data wasn't lost — the server had silently resolved to a default empty directory instead of the configured one. That kind of silent failure is unacceptable.

Now every server startup logs its data directory and *how* it was resolved (environment variable, config file, or default fallback). The `get_dashboard` response includes a `diagnostics` block so you can verify your configuration is working. If the server falls back to a default empty directory, it warns you.

**UPGRADE.md.** Step-by-step migration guide for v0.1.0 → v0.2.0 upgrades covering three configuration methods, the known MCPB interpolation bug and its workaround, and troubleshooting for the "my data appears lost" scenario.

## Known Issue: MCPB `user_config` interpolation

There is a confirmed bug in MCPB where `${user_config.*}` values in the manifest env block are **not interpolated** into the spawned process environment. This means the `LOCKSTEP_DATA_DIR` env var set through Claude Desktop's settings UI may not reach the server. This has been reported upstream.

**Workaround:** Create a `config.json` file in your data directory:
```json
// Create src/config.json adjacent to server.py
{
  "data_dir": "/path/to/your/lockstep/data"
}
```

This bypasses MCPB interpolation entirely. The server checks config.json before falling back to the default directory. See [UPGRADE.md](UPGRADE.md) for full details.

## Upgrading

If you're already on v0.2.0, this is a drop-in replacement — no data migration needed.

If upgrading from v0.1.0, see [UPGRADE.md](UPGRADE.md) for the complete migration guide.

## Install

### MCPB Bundle (Recommended)
1. Download `lockstep-core.mcpb` from the assets below
2. Open it with Claude Desktop (double-click or drag in)
3. When prompted, set your data directory
4. Call `get_dashboard` — check the `diagnostics` block to confirm your path

### Manual Setup
See the [README](README.md) for platform-specific instructions.

Full changelog: [CHANGELOG.md](CHANGELOG.md)

## License

GPL v3 — free to use, modify, and distribute. Modifications must stay open source.

Built by [Dandelion Rose Group](https://github.com/dandelionrosegroup) — proving that neurodivergent minds are uniquely wired for AI partnership.