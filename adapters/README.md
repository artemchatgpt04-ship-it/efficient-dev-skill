# Adapters

Adapters connect the shared Skill to a coding-agent host. They own only:

- how the host discovers or invokes the Skill;
- host-specific file locations and configuration;
- translation between host capabilities and core contracts;
- installation, update, and compatibility details for that host.

Adapters do not own routing, caching, change detection, reading policy, test selection, or context compression. Shared behavior belongs in `core/` and `rules/`.

Each adapter must eventually pass the same core behavior suite plus its own installation and compatibility checks.
