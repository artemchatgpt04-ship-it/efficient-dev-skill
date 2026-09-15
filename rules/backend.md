# Backend rules

- Trace the affected handler or service through its direct inputs, outputs, and callers before editing shared layers.
- Preserve API contracts, error behavior, validation, and transactional boundaries.
- Expand checks across consumers when a public endpoint, shared service, or cross-module contract changes.
