# commitpoem Constitution

> **Version**: 1.0
> **Status**: Canonical — proposal_only (AI cannot modify directly)
> **Ratified**: 2026-03-23

---

## I. Core Principles

### 1. Specification First
All development is driven by specifications. Code serves the specification, not the
other way around. Changes to requirements go through the proposal flow.

### 2. Test-First Development
Tests are written before implementation. No implementation code shall be written
before test scenarios are defined and acceptance criteria are clear.

### 3. Clean Architecture
- Separation of concerns: each module has a single responsibility
- Dependency direction: inner layers never depend on outer layers
- Interface boundaries: modules communicate through well-defined interfaces

### 4. Simplicity
- Start simple, add complexity only when proven necessary (YAGNI)
- Maximum 3 top-level packages for initial implementation
- No speculative or "might need" features
- Prefer framework features over custom abstractions

### 5. Observability
- Structured logging required for all services
- Error paths must produce actionable log messages
- Health/readiness endpoints for server applications

---

## II. Quality Gates

### Code Quality
- [ ] All public APIs have type hints
- [ ] No unused imports or dead code
- [ ] Functions are focused (single responsibility)
- [ ] Error handling covers expected failure modes

### Testing Standards
- [ ] Unit tests for all business logic
- [ ] Integration tests for external boundaries (DB, API, message queue)
- [ ] Edge cases identified and tested
- [ ] Test names describe the scenario, not the implementation

### Security
- [ ] No secrets in source code or configuration files
- [ ] Input validation at system boundaries
- [ ] Dependencies pinned to known-good versions
- [ ] Security-sensitive operations logged

---

## III. Development Workflow

### Modification Policy
| Artifact | Policy |
|----------|--------|
| Constitution | proposal_only — human approval required |
| Spec | proposal_only — human approval required |
| Plan / Tasks | AI-generated, human-reviewable |
| Code | AI-generated, AOP-verified, human-reviewable |

### Review Process
1. All code changes go through AOP aspect verification
2. Security HIGH findings block merge unconditionally
3. Review convergence required before advancing to verify stage

---

## IV. Governance

This constitution supersedes all other development practices for this project.
Amendments require explicit documentation, rationale, and human approval through
the proposal flow.
