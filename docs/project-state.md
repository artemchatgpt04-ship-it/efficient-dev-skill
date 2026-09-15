# Project-local state

An installed Skill may maintain state inside the target repository:

```text
.efficient-dev/
|-- config                  future
|-- project-map.json        Stage 2
|-- cache/
|   `-- read-cache.json     Stage 3
`-- state/
    |-- tracked-files.json  Stage 3
    `-- session.json        Stage 4
```

All Stage 2–4 runtime files are UTF-8, human-readable JSON. They are project-local and excluded from this repository by `.gitignore`.

| Element | Purpose | Rebuildable? | Persistence |
| --- | --- | --- | --- |
| `config` | Project choices, exclusions, safety policy, adapter selection, and explicit overrides. | Not fully; defaults cannot reproduce user choices. | Preserve across runs and upgrades. Never overwrite silently. |
| `project-map.json` | Compact derived view of important structure and probable source-test relationships. | Yes, from current project sources. | Rebuild explicitly after relevant changes; Stage 2 does not detect staleness. |
| `cache/read-cache.json` | One current summary, symbols, relationships, SHA-256 fingerprint, and validity per studied path. | Yes, by rereading current sources. | Reuse only after fingerprint validation; safe to delete. |
| `state/tracked-files.json` | Last accepted map of eligible paths to SHA-256 fingerprints. | Yes, by accepting a new baseline. | Preserve to compare runs; deletion resets change history but not source truth. |
| `state/session.json` | Bounded current task, scope, inspected/changed files, findings, decisions, tests, open issues, and next action. | Yes, from current caller-supplied facts. | Separate from Read Cache; safe to replace or delete, but deletion loses handoff continuity. |

## Read Cache format and validity

`read-cache.json` has schema `version: 1` and a sorted `entries` list. Each entry contains `path`, `fingerprint`, bounded `summary`, `symbols`, `relationships`, and `validity`. Validity is `valid`, `stale`, or manually `invalid`; deleted entries are removed. No source text, historical versions, access counters, or timestamps are stored.

A lookup hashes current bytes. Matching content may reuse the summary unless exact source is required. A mismatch marks the entry stale and withholds its knowledge. Recording after a fresh read replaces the single entry for that path.

`tracked-files.json` has schema `version: 1` and a sorted `files` object mapping eligible paths to fingerprints. Added, modified, and deleted paths mark Project Map as potentially stale. Updating the baseline is explicit through `changes --update`.

## Session state format

`session.json` has schema `version: 1`. It stores `task`, `scope`, `files_inspected`, `files_changed`, `key_findings`, `decisions`, `tests_run`, `open_issues`, and `next_action`. It has no command-log or source-code field.

Only caller-supplied facts are accepted. Supplying a field replaces its previous value; omitted fields stay current. Whitespace is normalized, duplicate list items are removed, and both item counts and item lengths are bounded. `context_size` measures compact UTF-8 JSON bytes, not tokens.

## Ownership rules

- The installed Skill must not store its universal rules or core implementation under `.efficient-dev`.
- Project-local state must not mutate the Skill repository.
- Cached knowledge is subordinate to current source bytes; a stored fingerprint is the validity proof.
- Session facts are subordinate to current source, tests, and task state; the compressor does not invent or verify facts.
- `config` is project-owned; generated data is tool-owned but always subordinate to source files.
- The Stage 5 installer does not create, manage, update, or remove `.efficient-dev`.
  A project may intentionally commit non-sensitive configuration or maps, but that must
  be explicit.

## Recovery expectations

Deleting `project-map.json`, `cache/`, `tracked-files.json`, or `session.json` may reduce speed or continuity but must not prevent the Skill from rebuilding from the project and current facts. Deleting `config` may lose intentional choices. Installer update and uninstall leave the complete `.efficient-dev` tree untouched.
