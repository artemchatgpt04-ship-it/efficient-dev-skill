# Codex adapter

The Codex adapter resolves discovery locations; all routing, caching, change tracking,
test selection, and context behavior remains in the shared core.

The default workspace destination is:

```text
PROJECT/.agents/skills/efficient-dev/
```

Current Codex documentation also supports user skills under
`HOME/.agents/skills/`. Use installer mode `global` explicitly for that destination.
This development environment still contains working Skills under
`HOME/.codex/skills/`, so `legacy-global` remains available only as an explicit
compatibility mode. The adapter does not inspect or edit Codex configuration.

Codex scans repository Skill directories from the current working directory toward
the repository root and normally notices changes automatically. If the installed Skill
does not appear, restart Codex as advised by the current documentation.

See [installer usage](../../installer/README.md) and
[installation architecture](../../docs/installation.md).
