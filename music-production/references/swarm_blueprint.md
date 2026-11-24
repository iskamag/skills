# Multi-Agent Swarm Music Production Blueprint

For complex multi-stem tracks (using the `swarm` tool / `/teamwork`), split the
pipeline across **5 specialists** with strict non-overlapping write ownership,
parallel Phase 1 execution, and **3 hard coordinator ear gates**.

---

## 1. Roster & Non-Overlapping Directory Ownership

| Agent | Write Scope | Core Deliverable |
|---|---|---|
| `researcher` | `research/` | `reference_clips/*.mp3`, `reference_analysis.md` |
| `sound-engineer` | `rig/` | `render_stems.py`, `reaper_session.py`, `rig_doc.md`, `proof/{solo_<primary>,full_band}_proof.mp3` |
| `composer` | `composition/` | `arrangement.md`, `compose.py`, `midi/*.mid` (shared Track 0 tempo map), `preview_sketch.wav`, `preview_chunks/*.mp3` |
| `mixer` | `mix/`, `output/` | `mix/stems/`, `mix/processed_stems/`, `mix/build_mix.py`, `mix/mix_report.md`, `output/<track>.{wav,mp3,rpp}` |
| `critic` | `reviews/` | `stage1_critique.md` (optional cold-ear Gate 2), `final_critique.md`, `master_chunks/*.mp3` |

**Golden Rule:** Two agents never write to the same directory. Upstream outputs
are read-only inputs for downstream agents.

---

## 2. Execution DAG & 3 Coordinator Ear Gates

```text
Phase 1 (Parallel):
  @researcher     ──► research/reference_clips/ + reference_analysis.md
  @sound-engineer ──► rig/render_stems.py + rig/reaper_session.py + rig/rig_doc.md
                      + rig/proof/solo_<primary>_proof.mp3 + rig/proof/full_band_proof.mp3
                             │
                             ▼
GATE 1 (Coordinator Ear Gate — STOP BEFORE COMPOSING):
  @coordinator A/Bs rig/proof/* via read_file against research/reference_clips/.
  (Fake/timid/MIDI tone? Loop back to @sound-engineer before writing a single bar.)
                             │
                             ▼
Phase 2:
  @composer       ──► composition/arrangement.md + compose.py + midi/*.mid
                      + preview_sketch.wav + preview_chunks/*.mp3
                             │
                             ▼
GATE 2 (Coordinator Ear Gate + Optional Cold-Ear @critic — STOP BEFORE MIXING):
  @coordinator listens to 100% of composition/preview_chunks/ via read_file.
  Optionally invoke @critic for a zero-context taste critique (reviews/stage1_critique.md).
  (Weak groove/monotony? Loop back to @composer before mixing.)
                             │
                             ▼
Phase 3:
  @mixer          ──► mix/build_mix.py + mix/mix_report.md + output/<track>.{wav,mp3,rpp}
                      (Self-audits overlapping chunks + solo processed primary stem via read_file.)
                             │
                             ▼
GATE 3 (Taste Critique + Mandatory Coordinator Final Ear Check):
  @critic         ──► reviews/master_chunks/ + reviews/final_critique.md
  @coordinator    ──► personally auditions 100% of final chunks + solo primary stem + MP3
                      via read_file before delivery.
```

---

## 3. Handoff Contracts (Exact Paths)

1. **`researcher` → Everyone:** `research/reference_clips/*.mp3` (including any
   isolated solo passage) and `research/reference_analysis.md`.
2. **`sound-engineer` → `composer` & `mixer`:**
   - `rig/rig_doc.md` specifying **exact canonical MIDI filenames**, GM drum
     mappings, playable pitch ranges, and copy-paste CLI commands for rough
     preview vs `--split-drums` rendering.
   - Sample-aligned `rig/render_stems.py` + headless `rig/reaper_session.py`.
   - Gate 1 proofs in `rig/proof/`.
3. **`composer` → `critic` & `mixer`:**
   - `composition/arrangement.md` (bar/timestamp map, harmony, mix cues),
     `composition/midi/<canonical_role>.mid` (identical Track 0 tempo map),
     `composition/preview_sketch.wav`, and `composition/preview_chunks/*.mp3`.
4. **`critic` (Gate 2, optional) → `mixer`:** `reviews/stage1_critique.md` with
   honest musical/sonic notes (bounce back to `composer` for songwriting/groove
   flaws; pass to `mixer` for balance/space fixes).
5. **`mixer` → `critic` (Gate 3):** `output/<track>.{wav,mp3,rpp}` and
   `mix/mix_report.md`.

---

## 4. Compact Role Brief Starters

- **`@researcher`:** *"Own `research/`. Slice 4–6 representative 20–35s clips (including any exposed solo instrument passage) into `research/reference_clips/`, audition every clip via `read_file`, and write `research/reference_analysis.md` covering musical feel, arrangement contrast, timbre/space character, and authenticity pitfalls."*
- **`@sound-engineer`:** *"Own `rig/` (read-only on system/user audio libraries). Discover local multi-RR DI/SFZ/drum kits, IRs, SoundFonts, and REAPER/JSFX/LV2 plugins; build sample-synced `rig/render_stems.py` (`--split-drums`, dry FluidSynth `-R 0 -C 0`, oversampled DSP + IRs) and headless `rig/reaper_session.py`; render Gate 1 proofs (`rig/proof/solo_<primary>_proof.mp3` + `rig/proof/full_band_proof.mp3`), ear-test them via `read_file`, and document the MIDI/CLI contract in `rig/rig_doc.md`."*
- **`@composer`:** *"Own `composition/`. Listen to `research/reference_clips/` and read `research/reference_analysis.md` + `rig/rig_doc.md`. Write `composition/arrangement.md` and `composition/compose.py` outputting humanized per-stem SMF Type 1 `.mid` files sharing an identical Track 0 tempo map. Render `composition/preview_sketch.wav` via `rig/render_stems.py`, slice overlapping 35–45s `composition/preview_chunks/*.mp3`, and audition 100% via `read_file`."*
- **`@mixer`:** *"Own `mix/` and `output/`. Render `--split-drums` stems into `mix/stems/`, build reproducible `mix/build_mix.py` (64-bit stem prep in `mix/processed_stems/` + editable multi-bus REAPER `.rpp` with folder buses, stereo `AUXRECV` returns, and pre-FX `<VOLENV>` automation), iterate by ear via `read_file` on overlapping chunks + isolated primary stem, and deliver `output/<track>.{wav,mp3,rpp}` + `mix/mix_report.md`."*
- **`@critic`:** *"Own `reviews/`. Act as an independent, cold-ear music critic with high taste — not a metric linter. At Gate 2 (if invoked), listen to 100% of `composition/preview_chunks/` via `read_file` and write `reviews/stage1_critique.md` judging groove, hooks, phrasing, monotony, and tone authenticity. At Gate 3, independently slice `output/<track>.wav` into overlapping `reviews/master_chunks/`, A/B 100% of chunks + solo primary stem + MP3 spot-check against `research/reference_clips/` via `read_file`, and write `reviews/final_critique.md` judging mix cohesion, energy arc, tone, and whether it genuinely holds up as a record."*
