# Upgrading Lockstep Core

## v0.1.0 → v0.2.0

### What Changed

**Schema version:** `1.0` → `2.0`

- Chain files: `template` field renamed to `chain_type`
- All data files: `schema_version` updated from `'1.0'` to `'2.0'`
- New fields added to chains: `chain_type` replaces `template`

**Data directory resolution:** v0.2.0 uses a 3-step resolution for finding
your data:

1. `LOCKSTEP_DATA_DIR` environment variable (set by MCPB `user_config`)
2. `config.json` file adjacent to `src/server.py`
3. Default: `~/.lockstep/data`

**Auto-migration:** v0.2.0 automatically migrates v1 data files on read.
When the server reads a chain or ticket with `schema_version: '1.0'`, it
upgrades the file in place — no manual migration required. This happens
transparently once the server is pointed at the correct data directory.

### Upgrade Steps

#### 1. Install v0.2.0

Install via MCPB bundle or clone the repository. If using MCPB, the
extension UI will prompt you to set a **Data Directory**.

#### 2. Point to your existing data

If you have existing v0.1.0 data, you need to tell v0.2.0 where it is.
There are three ways to do this (in priority order):

**Option A: MCPB Settings UI** (recommended for MCPB installs)

Set the Data Directory field in the extension settings to your existing
data path. After saving, restart Claude Desktop to apply.

**Option B: Environment variable**

Set `LOCKSTEP_DATA_DIR` to your data directory path:

```bash
export LOCKSTEP_DATA_DIR="/path/to/your/lockstep/data"
```

**Option C: Config file** (recommended for local development)

Create `config.json` in the `src/` directory:

```json
{
  "data_dir": "/path/to/your/lockstep/data"
}
```

#### 3. Verify the connection

After configuring, call `get_dashboard` in your first session. The response
now includes a `diagnostics` block:

```json
{
  "diagnostics": {
    "data_dir": "/path/to/your/lockstep/data",
    "resolution_method": "env"
  }
}
```

Check that:
- `data_dir` points to your actual data directory
- `resolution_method` shows the expected source (`env`, `config`, or `default`)
- Your chains and tickets appear in the dashboard

If `resolution_method` is `"default"` and your dashboard is empty, the
server is not finding your data. See **Known Issues** below.

#### 4. Schema migration (automatic)

No action needed. When v0.2.0 reads a v1 file, it automatically:
- Updates `schema_version` from `'1.0'` to `'2.0'`
- Renames `template` to `chain_type` (chains only)
- Writes the updated file back to disk

Migration happens on first read of each file. After one full dashboard
load, all accessed files will be upgraded.

#### 5. Manual migration script (optional)

A standalone migration script is included for bulk conversion without
running the server:

```bash
# Dry run — shows what would change
uv run scripts/migrate_v1_to_v2.py /path/to/your/lockstep/data --dry-run

# Apply migration
uv run scripts/migrate_v1_to_v2.py /path/to/your/lockstep/data
```

This is optional — the auto-migration on read handles the same conversion.
The script is useful if you want to migrate all files at once or verify
the migration before connecting the server.

---

### Known Issues

#### MCPB `user_config` interpolation may not set environment variables

**Symptom:** You configured the Data Directory in the MCPB extension UI,
but `get_dashboard` returns empty results and `resolution_method` shows
`"default"`.

**Cause:** The MCPB stores your setting correctly but may not interpolate
`${user_config.data_directory}` into the `LOCKSTEP_DATA_DIR` environment
variable when spawning the server process. This is a known MCPB issue,
not a Lockstep Core bug.

**Workarounds:**

1. **Config file method:** Create `src/config.json` with your data path
   (see Option C above). This bypasses MCPB interpolation entirely.

2. **Check stderr:** On startup, the server logs its resolved data path:
   ```
   [lockstep] Data directory: /path/to/data (resolved via: default)
   ```
   If you see `resolved via: default` when you expected `env`, the MCPB
   interpolation failed.

3. **Empty data warning:** If the server starts with an empty default
   directory, it will warn:
   ```
   [lockstep] Warning: Using default data directory with no existing data
   [lockstep] If upgrading from v0.1.0, set LOCKSTEP_DATA_DIR ...
   ```

#### Data appears lost after upgrade

**Symptom:** Dashboard shows zero chains and tickets after installing
v0.2.0.

**Cause:** Your data is safe — the server is looking in a different
directory than where your v0.1.0 data lives.

**Fix:** Check `get_dashboard` → `diagnostics.data_dir` to see where
the server is looking, then reconfigure to point to your actual data
using one of the three methods above.

---

### Version History

| Version | Schema | Key Changes |
|---------|--------|-------------|
| v0.1.0  | 1.0    | Initial release. `template` field on chains. |
| v0.2.0  | 2.0    | `template` → `chain_type`. Progressive disclosure. Chain type templates. Startup diagnostics. Auto-migration on read. |
