# Daily humanities edition

Approved in chat on 2026-11-02: implement and update the existing automatic daily run.

The daily edition contains one original poem in English and its Korean translation,
one shared bilingual title, a short interpretation grounded in the collected commits,
and a painting inspired by one of 100 historical painters. The selected poet and painter
remain the same throughout a Seoul calendar day. Both receive a short introduction,
representative work, biography/reference link and work reference. Generated work is
explicitly labelled as AI work inspired by the selected figures.

Use structured JSON for generated title, English poem, Korean translation and bilingual
behind story. Render the bilingual title once from these fields and repeat the same
title for both language editions; never ask the model for independent titles. Validate
required fields and reject malformed responses before posting. The behind story must
separate the commit facts from creative interpretation and avoid invented developer intent.

Maintain a curated quotation collection with attribution, source and thematic keywords.
Only append a quotation when its theme matches the commits; skip it otherwise. Quotations
supplement the poem. No model-invented quotations or biographical links.

Preserve the existing 200-poet pool and enrich its educational metadata. Curate exactly
100 distinct deceased painters spanning regions, eras and techniques, each with specific
style guidance. Use deterministic daily rotations so consecutive days do not repeat an
individual before their pool cycles. Pass the chosen painter explicitly to image generation.

Allow repeated --org flags, deduplicate organizations, and aggregate commits from qo-kr,
genideas-secure-labs and k-gen-food into one edition. Preserve --repo and its mutual
exclusion with organization mode. Log repository counts and inaccessible repositories;
do not silently turn API outages into an empty day. Never log credentials.

Keep the existing 09:00 cron entry pointing at run-daily.sh. Update that script to request
all three organizations for the previous Seoul calendar day with correct UTC boundaries.
Check shell syntax, CLI behavior, packaging and the actual cron installation without posting
an unsolicited edition. Existing image-to-text fallback remains supported.

Investigation: backends._build_prompt explicitly asks for TWO poems with independently
generated titles. No parser validates translation correspondence. image._build_image_prompt
always asks for atmospheric, soft, abstract painterly output and chooses no artist.

Initial verification: 263 pytest tests passed. Ruff reports six pre-existing unused
imports/variables in tests. Actual configured GitHub token lists 85 qo-kr repositories,
34 genideas-secure-labs repositories, and zero visible k-gen-food repositories (HTTP 200).
