# Installer

The future installer will connect this standalone repository to another project and coding agent without copying shared logic into an adapter.

## Required behavior

1. Accept an explicit target project and either detect or accept the target agent.
2. Validate all destination paths before writing.
3. Offer a documented copy or link strategy supported by the chosen adapter.
4. Initialize `.efficient-dev` without overwriting existing configuration or state.
5. Keep runtime project data separate from immutable Skill files.
6. Report changes and provide a reversible uninstall plan.
7. Default to local installation; publishing or remote changes require separate authorization.

Updates must preserve project-owned configuration and never silently replace newer or unknown files. The command interface, manifest, and implementation language are deferred to Stage 2.
