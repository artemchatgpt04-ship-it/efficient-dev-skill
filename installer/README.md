# Installer

The installer copies a small, versioned Skill bundle into one explicit discovery
location. It uses only the Python standard library and never edits agent configuration
or creates project runtime state.

Run it from this source checkout:

```text
python installer/efficient_dev_installer.py install codex PATH_TO_PROJECT
python installer/efficient_dev_installer.py status codex PATH_TO_PROJECT
python installer/efficient_dev_installer.py update codex PATH_TO_PROJECT
python installer/efficient_dev_installer.py uninstall codex PATH_TO_PROJECT
```

Replace `codex` with `antigravity` for the Antigravity adapter. `PATH_TO_PROJECT`
must already be a directory and cannot be a filesystem root or symbolic link.

## Modes

`workspace` is the default and safest mode. Non-workspace modes are used only when
`--mode` is supplied explicitly:

| Agent | Mode | Destination |
| --- | --- | --- |
| Codex | `workspace` | `PROJECT/.agents/skills/efficient-dev` |
| Codex | `global` | `HOME/.agents/skills/efficient-dev` |
| Codex | `legacy-global` | `HOME/.codex/skills/efficient-dev` |
| Antigravity | `workspace` | `PROJECT/.agents/skills/efficient-dev` |
| Antigravity | `global` | `HOME/.gemini/config/skills/efficient-dev` |
| Antigravity | `cli-global` | `HOME/.gemini/antigravity-cli/skills/efficient-dev` |

Pass `--home PATH_TO_HOME` to test or explicitly control a non-workspace destination.
Otherwise the process user home is used. The installer never selects global mode
automatically.

## Lifecycle guarantees

- `install` refuses an existing destination and creates the bundle through a temporary
  sibling directory before moving it into place.
- `status` validates the manifest, managed files, version, `SKILL.md`, and shared core.
- `update` requires a healthy managed installation, refuses a major-version change,
  refreshes only managed bundle files, and carries forward non-conflicting unmanaged
  files in the Skill directory.
- `uninstall` requires a healthy manifest, validates every managed path, removes only
  manifest-listed files, and leaves unmanaged files in place.

All four commands report the resolved location and discovery note. Add `--json` for
machine-readable output.

Project data under `PROJECT/.efficient-dev` is outside the installation root. The
installer neither creates nor removes it, so existing maps, cache, tracked-file state,
session state, and future project configuration survive update and uninstall.

See [installation architecture](../docs/installation.md) for the bundle allowlist,
manifest, path checks, compatibility policy, and official discovery references.
