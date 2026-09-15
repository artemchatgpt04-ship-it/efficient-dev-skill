# Scripts

This directory is reserved for small deterministic helpers that materially improve reliability, such as change fingerprints, state validation, or instrumentation for behavioral tests.

Stage 1 contains no executable helper because the data formats and observable contracts have not yet been validated. Scripts added later must have a clear caller, avoid scanning beyond their declared scope, fail safely, and be covered by meaningful tests.
