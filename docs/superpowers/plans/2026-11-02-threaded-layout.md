# Threaded daily publication

Approved by the user's exact layout instructions and subsequent request to rerun today's edition.

**Goal:** Publish image first, then the bilingual poem and a quotation under the same title;
put interpretation and all person introductions/references in a thread reply. Remove the AI footer.

**Architecture:** Rendering returns a Publication containing main text, comment, artwork input and
shared title. Slack uploads the image privately, then posts ordered image/text blocks via the bot,
and attaches notes using the returned parent timestamp. A failed reply must never duplicate the parent.

- [x] Add failing rendering tests: no notes/footer in parent, quote uses shared title, person
  introductions and source links in comment, image input excludes quote/notes.
- [x] Introduce Publication in edition.py and generate_publication in poem.py, retaining
  generate_poem as a text-returning convenience. Add quote biography references in quotations.py.
- [x] Add failing transport tests for private upload, image-first blocks, exact thread_ts,
  and partial thread failure without webhook duplication. Preserve legacy post_image behavior.
- [x] Implement bot publication in slack.py and wire cli.py with image-generation fallback
  while retaining threaded notes for no-image runs. Webhook-only mode posts parent text only.
- [x] Update README/.env.example, run targeted/full pytest and Ruff, and build/import the wheel.
- [x] Run today's approved edition once, verify parent and reply with Slack read tools, then commit.

Verified: full pytest338 tests, Ruff, wheel build/import and independent code review passed.
Live parent1793599269.118739 and one reply were read back through Slack: image above poetry;
quotation shares the title; behind story and all introductions/links appear in the reply; no AI footer.
Slack upload visibility lag was reproduced and fixed with bounded retries of the same file
only after explicit invalid-file rejections. Paragraph packing and preflight block limits prevent
posting a parent whose required comment is too large. Ambiguous network failures are not retried.
