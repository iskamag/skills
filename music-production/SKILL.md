---
name: music-production
description: >-
  Real-tooling, ear-verified music production guidelines and technical gotchas
  for composing, sound-designing, mixing, and mastering original tracks in any
  genre using multi-RR sample/DI libraries, measured IRs, FluidSynth, Python
  DSP, headless REAPER DAW sessions, and direct audio listening via read_file.
  Use whenever the user asks to compose, produce, arrange, synthesize, mix,
  master, or recreate a track in any style.
---

# Real-Tooling, Ear-Verified Music Production

Produce release-grade music in **any genre** using real audio tooling (multi-RR
samples/DI, measured IRs, oversampled DSP, editable headless REAPER sessions),
gated by **direct ear-listening (`read_file`) and taste** rather than
metric-chasing.

## Core Guidelines

1. **Listen First (`read_file`) — Judge by Taste, Not Numbers:** Audition
   rendered audio directly via `read_file` at every milestone. Never bury
   lead/rhythm instruments to hit a crest figure or squeeze stereo width to
   match a correlation number. A critic judges musicality, feel, tone
   authenticity, and mix cohesion — not numeric checklists.
2. **Match Sample Engine to Instrument Physics:** Single-sample GM `.sf2` plucks
   and zero-RR GM drum banks cause instant MIDI machine-gunning on rapid guitars
   and acoustic drums. Use multi-velocity, multi-RR DI libraries + 4×-oversampled
   amp/cab IRs and multi-mic/RR drum kits (e.g., DrumGizmo or SFZ kits). Reserve
   dry FluidSynth (`-R 0 -C 0`) for synths, strings, choirs, organs, pads, or
   clean fallback DI when multi-RR libraries aren't installed.
3. **Three Hard Ear Gates (Never Waterfall Blindly):** Do not compose a full
   arrangement into an unverified rig or mix an unverified arrangement. Stop and
   A/B via `read_file` at:
   - **Gate 1 (Tone Proof):** Isolated primary instrument (`solo_<primary>_proof.mp3`)
     + 20–25s full-band proof (`full_band_proof.mp3`) vs. reference. **Stop
     before composing until both pass.**
   - **Gate 2 (Rough Arrangement):** 100% of overlapping 35–45s chunks of the
     real-rig rough render. **Stop before mixing** (use a fresh zero-context
     subagent if monotony or ear fatigue is suspected).
   - **Gate 3 (Final Master):** 100% of overlapping chunks + isolated processed
     primary stem + direct MP3 spot-check before delivering.
4. **Keep Organic Life & Script Everything:** Real recordings breathe with
   subtle room air, noise floor, or analog/performative texture rather than
   sterile digital silence. Keep composition (`composition/compose.py`), rig
   rendering (`rig/render_stems.py`), and REAPER mixing (`mix/build_mix.py`)
   scripted so ear-driven fixes are repeatable and always leave an editable
   `output/<track>.rpp`.

---

## 5-Stage Workflow

1. **Reference Listening (if provided):** Slice 4–6 clips (20–35s) into
   `research/reference_clips/` covering contrasting sections **plus any exposed
   solo instrument passage**. Audition all clips via `read_file` and capture
   artistic notes in `research/reference_analysis.md`.
2. **Rig Engineering & Gate 1:** Inventory local multi-RR DI/SFZ/drum libraries,
   measured IRs, SoundFonts, and REAPER/LV2/JSFX plugins. Build sample-synced
   `rig/render_stems.py` (shared `target_samples`, split drums, dry FluidSynth,
   oversampled DSP + IRs). Render Gate 1 proofs and A/B via `read_file` before
   composing.
3. **Composition & Gate 2:** Generate per-stem SMF Type 1 `.mid` files in
   `composition/midi/` sharing an **identical Track 0 tempo & time-signature
   map**. Render through the Gate 1 rig, slice into overlapping 35–45s chunks,
   and audit 100% via `read_file` before mixing.
4. **Multi-Bus REAPER Mix & Master:** Run surgical 64-bit stem prep in
   `mix/processed_stems/` (mono low-end, complementary L/R EQ, cosine-tapered
   section EQ masks), generate an editable REAPER 7 `.rpp` with folder buses
   (`ISBUS`), stereo `AUXRECV` returns, and pre-FX `<VOLENV>` automation, render
   headlessly to 24-bit WAV + 320 kbps CBR MP3, and iterate by ear.
5. **Taste Critique & Gate 3:** Independently slice the final master into
   overlapping chunks (see [ear_critique.md](./references/ear_critique.md)) and
   listen to 100% of chunks + isolated processed primary stem + direct MP3
   spot-check via `read_file` before delivering.

---

## Non-Obvious Gotchas

- **Starved Amp-Sim Input:** Normalizing DI too low (`~0.16 RMS × small drive`)
  turns fierce high-gain rigs into polite classic-rock overdrive — always
  solo-check distorted instruments against a reference passage.
- **FluidSynth Defaults & Channel 9:** Always pass `-R 0 -C 0` and strip
  incoming `program_change` + `CC0/32/91/93`. On drum channel `9`, emit only
  `program_change` — **do not send `CC0=128`** (FluidSynth auto-maps ch9 to
  bank 128). Pad/trim all stems to one shared `target_samples`.
- **MIDI Note-Overlap Voice Hangs:** Humanization/timing jitter can place a new
  `note_on` before the previous identical pitch's `note_off`. Clamp
  `prev_off = min(prev_off, next_on - 1)` before rendering.
- **DSP Time Units & Pre-DAW Clipping:** Forgetting `* 1e-3` on `release_ms * sr`
  causes multi-second bleed across silent breaks. Keep split-drum/hot stems
  `<= -2.5 dBFS` so bus summing doesn't clip before REAPER.
- **REAPER Headless Traps:**
  - Linux headless render requires `xvfb-run -a reaper -nosplash -newinst -renderproject /abs/path/to/session.rpp`
    with **absolute paths** for both `-renderproject` and `RENDER_FILE`.
  - Use pre-FX linear **`<VOLENV>`** with `PANLAW 1` — **never `<VOLENV2>`**
    for dB-to-linear math curves (REAPER applies a non-linear fader taper).
  - Exact 7-byte `<RENDER_CFG>` base64: `ZXZhdxgAAA==` (24-bit WAV),
    `ZXZhdxAAAA==` (16-bit WAV), `ZXZhdyAAAA==` (32-bit float WAV).
  - Never guess JSFX slider indices or units — read the first ~30 lines of the
    installed `.jsfx` file first.
- **Chunk Seams:** Always overlap ear-audit chunks by 4–6s so section drops,
  fills, and tempo shifts never split across chunk boundaries.

---

## References & Tools

- **DAW, Stems & DSP Specs:** [references/headless_reaper_and_stems.md](./references/headless_reaper_and_stems.md)
- **Taste-Driven Ear Critique:** [references/ear_critique.md](./references/ear_critique.md)
- **Multi-Agent Swarm Blueprint:** [references/swarm_blueprint.md](./references/swarm_blueprint.md)
- **Ear-Chunk Slicer & Optional Analyzer:** [scripts/audio_telemetry.py](./scripts/audio_telemetry.py)
