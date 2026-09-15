# Adapters

Adapters connect the shared Skill to a coding-agent host. They own only:

- how the host discovers or invokes the Skill;
- host-specific file locations and configuration;
- translation between host capabilities and core contracts;
- installation, update, and compatibility details for that host.

Adapters do not own routing, caching, change detection, reading policy, test selection, or context compression. Shared behavior belongs in `core/` and `rules/`.

Stage 5 adapters are implemented as destination resolvers in `installer/adapters.py`.
Both install the same allowlisted bundle and pass the same lifecycle suite; their only
difference is the agent-specific discovery location and guidance. See the
[installation architecture](../docs/installation.md).
