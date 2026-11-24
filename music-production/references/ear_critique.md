# Taste-Driven Ear Critique Protocol

A critic exists to judge **musical taste, feel, and sonic authenticity** — not
to act as a metric linter. Always listen directly via `read_file` and compare
against real music in the target style.

---

## 1. Slicing Audio for `read_file` Listening

### Reference Clips (Stage 1)
Slice **4–6 clips (20–35s)** into `research/reference_clips/`:
```bash
ffmpeg -v error -ss 00:00:50 -t 35 -i full_ref.webm -b:a 192k research/reference_clips/01_intro_to_drop.mp3
```
Include contrasting energy states **plus any exposed solo instrument passage**
(naked riff, bare drums, solo synth/vocal) so Gate 1 tone proofs can be A/B'd
directly against exposed reference tone.

### Overlapping Ear-Audit Chunks (Gates 2 & 3)
Never critique a full track from just the intro and chorus, and **never slice
back-to-back without overlap** (drops, fills, and tempo changes hide on chunk
seams). Slice 100% of the render into **35–45s chunks with 4–6s overlap**:

```bash
python3 <skill-dir>/scripts/audio_telemetry.py \
  --input output/master.wav \
  --slice-chunks reviews/master_chunks \
  --chunk-sec 38 \
  --overlap-sec 5
```

Listen to **every chunk via `read_file`** from `0:00` through the final decay.
At Gate 3, also listen to:
- An **isolated processed primary stem** (e.g., solo rhythm/lead instrument) to
  confirm mixing didn't thin out or kill the tone that passed Gate 1.
- A **direct MP3 spot-check** (lossless `-c copy` slice of `output/<track>.mp3`).

---

## 2. What to Critique at Each Gate (Taste, Not Checklists)

- **Gate 1 — Tone Proof (`solo_<primary>_proof.mp3` + `full_band_proof.mp3`):**
  Does the primary instrument sound like a real recorded performance or a polite
  MIDI/GM imitation? Does it have weight, bite, organic noise/room life, and
  conviction next to the reference? Stop here until tone feels undeniable.
- **Gate 2 — Rough Arrangement (`composition/preview_chunks/`):**
  Listen cold (ideally with a zero-context critic). Does the groove lock in? Do
  riffs/melodies stick, or does it feel aimless, loopy, or mechanical? Do
  transitions earn their energy shifts? Distinguish songwriting/MIDI issues
  (send back to composer) from pure balance/space issues (hand off to mixer).
- **Gate 3 — Final Master (`reviews/master_chunks/`):**
  Does the whole track feel like one cohesive record in one acoustic space, or
  do dry elements sound pasted on top of wet ones? Does the climax hit harder
  than the verse without turning muddy or fatiguing? Does the ending decay
  naturally? Would you actually want to replay it?

---

## 3. Optional Diagnostic Comparison (`audio_telemetry.py`)

Only reach for numbers when your ears already hear a problem (e.g., "the chorus
feels darker or narrower than the reference — where?") and want a quick read:

```bash
python3 <skill-dir>/scripts/audio_telemetry.py \
  --input output/master.wav \
  --segments Intro:0:27 Main:27:95 Bridge:95:127 Outro:198:225 \
  --compare research/ref_clip01.json \
  --compare-section Main
```
