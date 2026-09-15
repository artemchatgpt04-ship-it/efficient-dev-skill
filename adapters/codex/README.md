# Codex adapter

The Codex adapter will expose the repository's root `SKILL.md` through Codex's skill discovery mechanism and translate Codex project context into the shared core contracts.

Planned responsibilities:

- discover the configured Codex skill directory rather than hard-code a user path;
- install by copy or link only after the user chooses an installation mode;
- preserve the root `SKILL.md` and its relative links to shared resources;
- initialize project-local `.efficient-dev` state through the common installer;
- document Codex-specific invocation and compatibility checks.

A typical destination may be `$CODEX_HOME/skills/efficient-dev-skill`, with a user-level Codex skills directory used when `CODEX_HOME` is not set. Stage 2 must verify the active environment before modifying it.

No token-saving logic belongs here.
