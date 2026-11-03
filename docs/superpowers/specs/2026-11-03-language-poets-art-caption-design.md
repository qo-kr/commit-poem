# Language-specific poets, quote rotation and artwork credits

The user's November 3 instructions replace the previous one-poem/translation rule:
English uses an English-language poet, Korean a Korean poet. The works are independently
composed from the same commits, common theme and bilingual title. Each has its own style
credit, and both poets' introductions/works/references appear in the thread.

Actual generation revealed that a joint request still produced a translation. Generate
English and Korean in separate requests. English returns the shared title pair, English
poem and English behind story; Korean receives only commits and that title pair, never
the English verses, and returns its own poem and behind story. Validate their combined
edition and permit one bounded pair repair. Skip automatic merge subjects when a factual
title anchor can be taken from an actual change commit.

Keep all 200 existing poet profiles for compatibility. Production pools contain 100
Korean poets, 100 English-language poets, 100 painters and 100 quotation authors.
English profiles retain the existing 46 English-language poets and add 54 others.
Freeze both poets, painter and quote date at pipeline start, using Seoul calendar dates.

The user's later clarification requires thematic selection from each 100-person pool.
Score styles/biographies/works and quotation keywords against commit vocabulary and
human motifs (memory, trust, repair, community, change). Exclude the latest 99 successful
selections independently per pool. For quotations, omitted-quote days do not expire
authors. Deterministic date-based tie breaking keeps selection reproducible.
Only use relevant sourced actual quotations. Add 94 verified historical authors, retaining
the existing six. Precisely label anthology-derived quotations and their work contexts.
Never generate an invented statement attributed to a real person.

Persist successful selections in versioned JSON under XDG_STATE_HOME/commitpoem or
~/.local/state/commitpoem. Atomic replacement and a write lock preserve history.
Same-day successful reruns restore the saved people; corrupt history fails before posting.
Generation or Slack failures do not consume people from future rotations.

Store artwork caption separately from poem input. Immediately below a successfully
attached image show the shared bilingual artwork title and painter's name with
"화풍에서 영감을 얻은 그림 / in the style of". No image means no misleading image caption.
Keep the existing image-first layout and threaded biographies. Add specific fresco,
pigment and spatial guidance for Giotto using Santa Croce restoration documentation:
https://www.santacroceopera.it/en/giotto-and-the-bardi-chapel-restoration/reconstruction_workshop/

Retain the bounded commit prompt, strict JSON validation/repair, safe local Git sync and
09:00 KST cron. Verify selection cycles, distinct style prompts and credits, caption block
ordering/fallback, quote match-set changes and the full existing suite before deployment.
