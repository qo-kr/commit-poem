# Daily Humanities Implementation Plan

> Execute in this session with superpowers:subagent-driven-development. The user approved
> implementation and automatic-run updates; do not ask for a second authorization.

**Goal:** Publish a coherent bilingual literary edition with varied art and educational references.

**Architecture:** Curated profiles supply daily identities and trusted links. Backends return
validated structured content; a renderer builds the Slack edition and image prompt. CLI
aggregates multiple organizations; the existing cron wrapper defines the Seoul daily window.

**Tech stack:** Python 3.11, dataclasses, zoneinfo, Click, requests, pytest, Ruff, Bash.

## Task 1: Curated daily profiles

- [x] Add tests in tests/test_catalog.py for 100 distinct painters, all 200 existing poets,
  complete biographies/work links/style guidance, KST selection and daily rotation.
- [x] Run `rtk proxy .venv/bin/pytest tests/test_catalog.py -q` and observe missing catalog failures.
- [x] Add commitpoem/catalog.py and packaged data under commitpoem/data/ with frozen Profile
  records (name, bio, work, url, work_url, style) and select_daily(day=None).
- [x] Run targeted tests; review profile completeness and factual/source risks.

## Task 2: Coherent edition and artwork

- [x] Add tests for JSON parsing, empty/malformed responses, shared titles, bilingual behind
  stories, matching sourced quotations, Slack formatting, and selected painter propagation.
- [x] Observe failures before adding commitpoem/edition.py and commitpoem/quotations.py.
- [x] Replace independent-poem instructions in commitpoem/backends.py with a single work
  and translation schema. Keep public generate_poem returning a rendered string.
- [x] Extend image.py with a painter argument and varied technique guidance, keeping fallback.
- [x] Run targeted backend/poem/image/edition tests and review generated prompt snapshots.

## Task 3: Multi-organization daily automation

- [x] Add tests for repeated --org, duplicate organizations, --repo exclusion, API failures,
  empty organization logging and Seoul previous-day UTC boundaries.
- [x] Observe failures; modify cli.py, github_client.py and run-daily.sh with targeted changes.
- [x] Run CLI/GitHub/shell tests and `rtk proxy bash -n run-daily.sh`.
- [x] Update README.md and .env.example for behavior, source attribution and access needs.

## Task 4: Handoff verification

- [x] Run full pytest and Ruff; remove the six pre-existing unused test imports/variables.
- [x] Build and inspect a wheel to confirm profile data is included.
- [x] Independently review spec compliance, then code quality; address substantive findings.
- [x] Verify installed entry point and cron path use the updated checkout without sending Slack messages.
- [x] Report tests, active schedule and the unresolved zero-visible-repository result for k-gen-food.

## Approved local-first extension and verification

- Added local_git.py and local Git tests. Origin pairing covers root repositories plus
  immediate child clones/worktrees; duplicate remote/SHA pairs are collected once.
- Daily wrapper now uses four local roots and filters qo-kr, genideas-secure-labs and
  k-gen-food. Local mode does not require GITHUB_TOKEN.
- User explicitly approved clean-main fast-forward automation. Index locking serializes
  checkout/switch/commit during updates; dirty, divergent and in-progress checkouts skip.
- Independent specification and quality reviews passed after fixes for quote provenance,
  date-walk pruning and concurrent branch switching.
- Final pytest: 312 passed. Ruff and diff whitespace checks pass. Wheel builds and
  imports all three catalogs with 200 poet and 100 painter records.
- Live OpenAI generation passed schema validation and rendering without Slack delivery.
- Cron entry verified: daily09 Asia/Seoul, existing run-daily.sh and editable installation.
- Actual local synchronization passed: 24 clean-main checkouts verified, 16 advanced,
  46 dirty/other-branch checkouts skipped; 313 unique previous-Seoul-day commits collected.
  No Slack message was sent by verification runs.
