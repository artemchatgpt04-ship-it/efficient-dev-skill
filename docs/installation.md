# Installation architecture

## Verified discovery contracts

The Stage 5 paths were checked against current official documentation on 2026-09-15.

- [Codex Skills documentation](https://developers.openai.com/codex/skills) defines
  repository Skills under `$REPO_ROOT/.agents/skills` and user Skills under
  `$HOME/.agents/skills`. Repository discovery walks from the current directory toward
  the repository root. Codex normally notices changes automatically, with restart as a
  documented fallback.
- [Antigravity Skills documentation](https://antigravity.google/docs/skills) defines
  workspace bundles under `<workspace-root>/.agents/skills/<skill-folder>` and global
  IDE bundles under `~/.gemini/config/skills/<skill-folder>`.
- Google's
  [Antigravity Skills codelab](https://codelabs.developers.google.com/getting-started-with-antigravity-skills)
  additionally documents `~/.gemini/antigravity-cli/skills` for CLI-global Skills.

The active development environment also has usable Codex Skills under
`HOME/.codex/skills`, which differs from the current documented user path. The installer
therefore uses `.agents/skills` for new installs and keeps `.codex/skills` as an explicit
`legacy-global` compatibility mode. It never modifies both.

## Boundaries

```text
installer CLI
    |
    +-- Codex adapter --------> destination + discovery note
    +-- Antigravity adapter --> destination + discovery note
    |
    `-- shared installer service
            +-- validates target and confined destination
            +-- builds allowlisted bundle
            +-- records ownership manifest
            `-- install / status / update / uninstall

installed Skill bundle ------> shared core and routed resources
target .efficient-dev -------> separate project-owned runtime state
```

Adapters contain only destination rules and discovery guidance. They do not reimplement
Project Map, Task Router, Smart Reader, Read Cache, Change Tracker, Instruction Router,
Test Router, or Context Compressor.

## Bundle and ownership

The bundle is constructed from an allowlist:

- root `SKILL.md` and `VERSION`;
- all Python modules directly in `core/efficient_dev/`, plus `core/__init__.py` and its
  compact README;
- Markdown instruction groups in `rules/`;
- the lightweight core CLI wrapper and its README;
- project-state documentation needed by the installed `SKILL.md` links.

Tests, fixtures, installer sources, adapter development notes, Git metadata, CI files,
repository architecture notes, caches, and source-checkout runtime state are excluded.
Both adapters receive the same bundle, so there is one core source of truth.

Each install writes `.efficient-dev-install.json` inside the Skill directory. Its only
fields are `version`, `agent`, `install_mode`, `managed_files`, and `installed_at`.
`VERSION` is the single source of release version for installer and status output.

## Lifecycle and safety

`install` requires an existing non-root target directory, confines the adapter result to
the selected project or home, refuses symbolic-link destinations, and refuses any
existing Skill directory. It builds in a uniquely named sibling and moves the complete
bundle into place.

`status` distinguishes `missing`, `installed`, and `broken`. A healthy result requires a
valid manifest for the requested agent and mode, normalized in-root managed paths, all
managed regular files, matching version metadata, valid `SKILL.md`, and an importable
core layout.

`update` accepts only a healthy managed install with a compatible major version. It
builds the new allowlisted bundle separately, preserves non-conflicting unmanaged files,
swaps directories, and keeps a temporary rollback copy until the swap succeeds.

`uninstall` validates the complete manifest before changing anything. It unlinks only
registered regular files, deletes the manifest last, and removes only directories left
empty. Unknown files and symbolic links are reported and retained. There is deliberately
no recursive “delete state” option.

Managed paths are normalized portable relative paths. Absolute paths, `..`, duplicate
entries, paths escaping the resolved installation root, unexpected managed directories,
and symbolic links are rejected. Temporary recursive removal is limited to installer-
generated siblings with exact known name prefixes.

The target project's `.efficient-dev` directory is never an installation destination
and is absent from the manifest. Install does not create it; update and uninstall do not
read, replace, invalidate, or remove it.

## Deliberate limitations

Discovery is verified structurally rather than by launching an interactive Codex or
Antigravity session. Updates use an already obtained source checkout and never contact
GitHub, a registry, or an update service. The installer does not edit global agent
configuration, migrate arbitrary unmanaged installations, remove project state, or
promise compatibility across a major-version change.
