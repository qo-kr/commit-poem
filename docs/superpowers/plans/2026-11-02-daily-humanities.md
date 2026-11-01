# Daily Humanities Implementation Plan

> Execute in this session with superpowers:subagent-driven-development. The user approved
> implementation and automatic-run updates; do not ask for a second authorization.

**Goal:** Publish a coherent bilingual literary edition with varied art and educational references.

**Architecture:** Curated profiles supply daily identities and trusted links. Backends return
validated structured content; a renderer builds the Slack edition and image prompt. CLI
aggregates multiple organizations; the existing cron wrapper defines the Seoul daily window.

**Tech stack:** Python 3.11, dataclasses, zoneinfo, Click, requests, pytest, Ruff, Bash.

## Task 1: Curated daily profiles

- [ ] Add tests in tests/test_catalog.py for 100 distinct painters, all 200 existing poets,
  complete biographies/work links/style guidance, KST selection and daily rotation.
- [ ] Run `rtk proxy .venv/bin/pytest tests/test_catalog.py -q` and observe missing catalog failures.
- [ ] Add commitpoem/catalog.py and packaged data under commitpoem/data/ with frozen Profile
  records (name, bio, work, url, work_url, style) and select_daily(day=None).
- [ ] Run targeted tests; review profile completeness and factual/source risks.

## Task 2: Coherent edition and artwork

- [ ] Add tests for JSON parsing, empty/malformed responses, shared titles, bilingual behind
  stories, matching sourced quotations, Slack formatting, and selected painter propagation.
- [ ] Observe failures before adding commitpoem/edition.py and commitpoem/quotations.py.
- [ ] Replace independent-poem instructions in commitpoem/backends.py with a single work
  and translation schema. Keep public generate_poem returning a rendered string.
- [ ] Extend image.py with a painter argument and varied technique guidance, keeping fallback.
- [ ] Run targeted backend/poem/image/edition tests and review generated prompt snapshots.

## Task 3: Multi-organization daily automation

- [ ] Add tests for repeated --org, duplicate organizations, --repo exclusion, API failures,
  empty organization logging and Seoul previous-day UTC boundaries.
- [ ] Observe failures; modify cli.py, github_client.py and run-daily.sh with targeted changes.
- [ ] Run CLI/GitHub/shell tests and `rtk proxy bash -n run-daily.sh`.
- [ ] Update README.md and .env.example for behavior, source attribution and access needs.

## Task 4: Handoff verification

- [ ] Run full pytest and Ruff; remove the six pre-existing unused test imports/variables.
- [ ] Build and inspect a wheel to confirm profile data is included.
- [ ] Independently review spec compliance, then code quality; address substantive findings.
- [ ] Verify installed entry point and cron path use the updated checkout without sending Slack messages.
- [ ] Report tests, active schedule and the unresolved zero-visible-repository result for k-gen-food.
