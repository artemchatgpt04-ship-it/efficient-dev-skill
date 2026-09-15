# Project-local state

An installed Skill may maintain state inside the target repository:

```text
.efficient-dev/
|-- config                  future
|-- project-map.json        Stage 2
|-- cache/
`-- state/
```

Stage 2 defines only `project-map.json`. Other names remain logical future contracts.

| Element | Purpose | Rebuildable? | Persistence |
| --- | --- | --- | --- |
| `config` | Project choices, exclusions, safety policy, adapter selection, and explicit overrides. | Not fully; defaults cannot reproduce user choices. | Preserve across runs and upgrades. Never overwrite silently. |
| `project-map.json` | Compact derived view of important structure and probable source-test relationships. | Yes, from current project sources. | Rebuild explicitly after relevant changes; Stage 2 does not detect staleness. |
| `cache/` | Source-linked summaries and other derived read knowledge. | Yes. | Reuse only while inputs are verified unchanged; safe to delete for recovery. |
| `state/` | Compact checkpoints such as the latest analysis boundary, pending invalidations, and compatible Skill version. | Usually; deletion may lose continuity but not source truth. | Preserve between runs, prune deliberately, and recover conservatively. |

## Ownership rules

- The installed Skill must not store its universal rules or core implementation under `.efficient-dev`.
- Project-local state must not mutate the Skill repository.
- Future cached or incremental items will need enough provenance to decide whether they are fresh, stale, or unknown.
- `config` is project-owned; generated data is tool-owned but always subordinate to source files.
- The installer should ignore `.efficient-dev` by default until the project chooses a version-control policy. A project may intentionally commit non-sensitive configuration or maps, but that must be explicit.

## Recovery expectations

Deleting `project-map`, `cache/`, or `state/` may reduce speed and continuity but must not prevent the Skill from rebuilding knowledge from the project. Deleting `config` may lose intentional choices, so updates and uninstall flows must preserve or explicitly back it up.
