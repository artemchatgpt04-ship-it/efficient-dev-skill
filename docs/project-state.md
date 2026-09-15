# Project-local state

An installed Skill may maintain state inside the target repository:

```text
.efficient-dev/
|-- config
|-- project-map
|-- cache/
`-- state/
```

Names are logical contracts in Stage 1; file extensions and serialization formats remain undecided.

| Element | Purpose | Rebuildable? | Persistence |
| --- | --- | --- | --- |
| `config` | Project choices, exclusions, safety policy, adapter selection, and explicit overrides. | Not fully; defaults cannot reproduce user choices. | Preserve across runs and upgrades. Never overwrite silently. |
| `project-map` | Compact derived view of important structure and relationships, plus freshness metadata. | Yes, from current project sources. | Reuse across runs when fresh; replace atomically when rebuilt. |
| `cache/` | Source-linked summaries and other derived read knowledge. | Yes. | Reuse only while inputs are verified unchanged; safe to delete for recovery. |
| `state/` | Compact checkpoints such as the latest analysis boundary, pending invalidations, and compatible Skill version. | Usually; deletion may lose continuity but not source truth. | Preserve between runs, prune deliberately, and recover conservatively. |

## Ownership rules

- The installed Skill must not store its universal rules or core implementation under `.efficient-dev`.
- Project-local state must not mutate the Skill repository.
- Every derived item needs enough provenance to decide whether it is fresh, stale, or unknown.
- `config` is project-owned; generated data is tool-owned but always subordinate to source files.
- The installer should ignore `.efficient-dev` by default until the project chooses a version-control policy. A project may intentionally commit non-sensitive configuration or maps, but that must be explicit.

## Recovery expectations

Deleting `project-map`, `cache/`, or `state/` may reduce speed and continuity but must not prevent the Skill from rebuilding knowledge from the project. Deleting `config` may lose intentional choices, so updates and uninstall flows must preserve or explicitly back it up.
