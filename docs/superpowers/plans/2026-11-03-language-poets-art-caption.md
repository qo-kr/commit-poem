# Language-specific poets and artwork caption implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development for the independent quote selection task and requesting-code-review before integration.

**Goal:** Publish independently styled English/Korean poems, topic-matched nonrepeating people from four 100-person pools and visible artwork credits.

**Architecture:** Keep existing JSON edition fields and bounded shared prompt. Add language-specific catalog selectors and pass both profiles through generation and rendering. Keep caption separate until Slack attaches an image. Rank each 100-person pool by themes, exclude recent successful people, persist successful daily references atomically and restore them on same-day reruns.

**Tech Stack:** Python, pytest, Ruff, existing Slack Web API and Codex image generation.

## Task 1: Fixed quote calendar

Superseded by the user's later 100-person thematic-selection instruction: retain the
fixed-calendar helper for compatibility, but production uses `selection.choose_daily`.
Expand `commitpoem/data/quotations.json` to 100 unique verified authors. Add
`commitpoem/selection.py` and tests covering topic rank, recent99 exclusion per category,
quote omissions, same-day restore, corrupt history and atomic concurrent persistence.

- [ ] Add failing tests in `tests/test_quotations.py`: all-keyword days visit every quote, changing matching sets cannot repeat adjacent quotations, unrelated date candidates return None, default uses Seoul.
- [ ] Run `rtk proxy .venv/bin/pytest -q tests/test_quotations.py` and observe failure.
- [ ] In `commitpoem/quotations.py`, select `QUOTATIONS[(day.toordinal()-1) % len(QUOTATIONS)]`, then return it only when its complete keyword matches.
- [ ] Run targeted tests; update old date-implicit quote assertions in edition tests during integration.

## Task 2: Two daily poet profiles

- [ ] Add failing tests in `tests/test_catalog.py` and `tests/test_backends.py` for `select_daily_poets(day)` and separate original poems with common title/theme.
- [ ] Split loaded catalog constants without dropping any profiles. Define explicit English-language membership and independent seeded rotations.
- [ ] Expand `commitpoem/data/english_poets.json` to 100 complete profiles, retaining the original46; verify new biography and work links.
- [ ] Add optional `korean_poet` alongside `poet` throughout backend prompt, generation, render and CLI; `poet` now credits the English poem.
- [ ] Preserve the six strict JSON fields, bounded source input, literal anchor and one repair attempt. Freeze Seoul day in the CLI and use it for quote selection.
- [ ] Verify prompts specify separate styles and independent compositions, rather than translation, and signatures/intros use the correct profile.

## Task 3: Artwork caption and style guidance

- [ ] Add failing Slack tests that caption appears directly below the image and disappears on missing/upload-failed images, including preflight 50-block accounting.
- [ ] Add `Publication.artwork_caption`, render title and painter attribution there, and pass it through CLI to Slack.
- [ ] Append caption blocks only after successful attachment; keep it out of artwork generation input. Preserve bounded invalid-file retries and parent/thread failure behavior.
- [ ] Strengthen Giotto's catalog technique with fresco plaster, earth pigments, blue, sculptural masses and restrained shallow space, preserving poem subjects.

## Task 4: Verify and deploy

- [ ] Run targeted tests, full `rtk proxy .venv/bin/pytest -q`, Ruff and diff whitespace checks.
- [ ] Update README/CHANGELOG, review final diff for spec compliance then code quality.
- [ ] Commit, push, merge and fast-forward the local production main using existing user authorization. Preserve 09:00 KST schedule.
