# Headless REAPER, Synchronized Stems & DSP Specs

Concrete technical recipes and exact file formats for local audio asset
discovery, dry sample-synced stem rendering, oversampled DSP + IR convolution,
and programmatic editable REAPER 7 `.rpp` generation.

---

## 1. Local Audio Asset & Tooling Discovery (Read-Only)

Check installed engines, sample libraries, IRs, and plugins before falling back
to generic GM patches (inspect top-level dirs first; avoid slow recursive scans
of unrelated mounts):

```bash
# 1. Core CLI engines & DAWs
which reaper ardour fluidsynth csound ffmpeg ffprobe yt-dlp xvfb-run python3

# 2. SoundFonts / SFZ / multi-RR sample kits
find /usr/share ~/Music ~/.local/share -maxdepth 4 \
  \( -iname "*.sf2" -o -iname "*.sf3" -o -iname "*.sfz" -o -iname "*drumgizmo*" \) 2>/dev/null

# 3. REAPER built-in IRs, stock JSFX, user JSFX, and native FX
ls /usr/lib/REAPER/InstallData/Data/amp_models/ /opt/REAPER/InstallData/Data/amp_models/ 2>/dev/null
ls /usr/lib/REAPER/InstallData/Effects/ /opt/REAPER/InstallData/Effects/ ~/.config/REAPER/Effects/ 2>/dev/null
ls /usr/lib/REAPER/Plugins/FX/ /opt/REAPER/Plugins/FX/ 2>/dev/null

# 4. LV2 / VST3 / CLAP plugins
ls /usr/lib/lv2 /usr/lib/vst3 /usr/lib/clap ~/.lv2 ~/.vst3 ~/.clap 2>/dev/null
```

### Python DSP Environment
Keep DSP packages isolated in a project-local venv (e.g., `rig/.venv`):
`numpy`, `scipy`, `soundfile`, `mido`, and optionally `pedalboard` (fast C++
compressor/reverb/filter bindings). Note: `scripts/audio_telemetry.py` only
needs `numpy` + `ffmpeg` (optional `soundfile`).

---

## 2. Dry Synchronized FluidSynth Stem Rendering

### Mandatory Dry Flags
Always disable built-in reverb (`-R 0`) and chorus (`-C 0`), run non-interactively
(`-ni -q`), and lock the sample rate (`-r 44100` or `48000`):

```bash
fluidsynth -ni -q -R 0 -C 0 -r 44100 -g 0.85 -F raw_stem.wav /path/to/soundfont.sf2 prepared.mid
```

### Pre-Render MIDI Sanitization (Common Failure Points)
1. **Preserve Track 0 tempo map:** Merge tracks with `mido.merge_tracks(mid.tracks)`
   so tempo changes, rubato, and accelerandos stay exact across all stems.
2. **Strip conflicting GM messages:** Drop incoming `program_change` and
   `control_change` `0` (Bank MSB), `32` (Bank LSB), `91` (GM Reverb), `93` (GM
   Chorus). Preserve `CC7` (Volume), `CC11` (Expression), `CC64` (Sustain), and
   `pitchwheel`.
3. **Deterministic patch selection at tick 0:**
   - Melodic tracks (ch `0`): `CC0 = bank`, `CC32 = 0`, `program_change = program`.
   - Drum tracks (ch `9`): emit **only** `program_change = program` (**do not**
     send `CC0 = 128` — FluidSynth auto-maps channel 9 to bank 128).
   - Micro-detune for double-tracking (assuming ±2 semitone pitchbend range):
     `pitchwheel = round(cents * (8192.0 / 200.0))`.
4. **Sanitize overlapping identical pitches:** Humanization/jitter can put a
   `note_on` before the prior note's `note_off`, hanging voices. Clamp
   `prev_off = min(prev_off, next_on - 1)`.

### Exact Sample-Count Synchronization
1. Compute `max_dur_sec = max(mido.MidiFile(p).length for p in midi_files)`.
2. Lock `target_samples = int(round((max_dur_sec + tail_sec) * sr))` (`tail_sec = 4.5–6.0`).
3. Pass every stem through `_fit_length(audio, target_samples)`: zero-pad if
   short; trim with a ~256-sample linear fade-out if long (zero EOF click).

---

## 3. Split-Drum & Multi-Stem Percussion Layout

Prefer multi-mic/multi-RR drum engines (e.g., DrumGizmo or SFZ kits) for rapid
acoustic drumming. When splitting MIDI by GM note buckets into synced sub-stems
(gain-staged `<= -2.5 dBFS` each so bus sums don't clip before REAPER):

| Sub-Stem | Typical GM Notes | Purpose |
|---|---|---|
| `drums_kick.wav` | `35, 36` | Independent sub HPF, punch, beater-click EQ |
| `drums_snare.wav` | `37, 38, 40` | Independent crack/wire EQ, section room send |
| `drums_toms.wav` | `41, 43, 45, 47, 48, 50` | Constant-power pan spread (High L → Mid C → Floor R) |
| `drums_cymbals.wav` | `42, 44, 46, 49, 51, 52, 53, 55, 57, 59` | High-pass (`350–500 Hz`), sheen without harshing mids |

For electronic/orchestral percussion, mirror the same split (`perc_low`,
`perc_snare_clap`, `perc_hats`, `perc_fx_toms` or `timpani`, `orch_perc`).

---

## 4. Oversampled Amp/Saturation & Real IR Convolution

Raw SoundFont distorted guitars sound thin and artificial, and single-sample GM
`.sf2` plucks machine-gun on rapid riffs. **Prefer multi-velocity, multi-RR DI
libraries / SFZ** through real DSP + measured IRs (use Clean DI `.sf2` only as a
fallback for sustained parts or when no multi-RR DI library is available):

1. **Pre-EQ & Input Drive:** High-pass (`80–130 Hz`) before distortion so sub
   mud doesn't intermodulate. Feed realistic hot input levels into the amp stage
   — starved DI (`~0.16 RMS × low gain`) sounds polite instead of saturated.
2. **4× Oversampling:** Run asymmetric triode (`tanh`), diode clippers, or tape
   saturation at `4× sr` via `scipy.signal.resample_poly(x, 4, 1)` → non-linearity
   → `resample_poly(y, 1, 4)` to eliminate aliasing fizz.
3. **Measured Cab / Space IR Convolution:**
   - Resample IR if `ir_sr != sr`, energy-normalize (`ir /= sqrt(sum(ir**2))`),
     and convolve with `scipy.signal.fftconvolve(x, ir, mode="full")[:len(x)]`.
   - For wide double-tracked guitars that collapse cleanly in mono, pair
     distinct L/R takes/RR seeds with **two different cab IRs** + `±4c` detune +
     `2–4 ms` timing offset.
4. **Split-Band Bass:** Split at `180–250 Hz` (`butter` LP + HP). Keep the low
   band clean and mono; run only the high band through 2×-OS grit + bass cab IR.

---

## 5. Surgical 64-Bit Stem Prep (Before DAW Summing)

Handling deterministic surgical cleanup in Python (`float64`) before REAPER
keeps the `.rpp` readable and fast:
- **Mono-Below Anchoring:** Mono-sum stereo pads/keys/reverbs below `180–240 Hz`
  (`M = 0.5 * (L + R)`) so sub/bass stays phase-coherent.
- **Time-Localized EQ Masks:** Crossfade between two EQ variants using a smooth
  cosine-tapered window (`0.15–0.35s`) when one section needs different carving
  (e.g., stricter HPF in a dense climax without thinning a quiet intro).
- **Complementary L/R EQ:** Offset gentle peak/notch centers by `150–400 Hz`
  between L/R pairs for natural width without phase smear.

---

## 6. Programmatic REAPER 7 `.rpp` & Headless Rendering

### Verified Headless Render Command
```bash
# Linux (headless X11):
xvfb-run -a reaper -nosplash -newinst -renderproject /absolute/path/to/session.rpp

# macOS / Windows (no xvfb-run needed):
reaper -nosplash -newinst -renderproject /absolute/path/to/session.rpp
```
- **Always use absolute paths** for both `-renderproject` and `RENDER_FILE`.
- `-newinst` prevents colliding with an already-open REAPER GUI instance.

### Critical `.rpp` Header & Exact WAV `<RENDER_CFG>` Base64
```text
<REAPER_PROJECT 0.1 "7.0" 1700000000
  PANLAW 1
  MAXPROJLEN 0 225.500000
  SAMPLERATE 44100 0 0
  RENDER_FILE "/abs/path/to/output/master.wav"
  RENDER_PATTERN ""
  RENDER_FMT 0 2 44100
  RENDER_1X 0
  RENDER_RANGE 1 0 0 18 1000
  RENDER_RESAMPLE 3 0 0
  RENDER_ADDTOPROJ 0
  RENDER_STEMS 0
  RENDER_DITHER 0
  <RENDER_CFG
    ZXZhdxgAAA==
  >
```
- `RENDER_FMT 0 2 44100` → WAV (`0`), 2 channels, sample rate (`44100`/`48000`).
- **Exact 7-byte WAV `<RENDER_CFG>` base64 (`b"evaw" + bytes([bits, 0, 0])`):**
  - 16-bit PCM WAV (`\x10`): `ZXZhdxAAAA==`
  - 24-bit PCM WAV (`\x18`): `ZXZhdxgAAA==`
  - 32-bit float WAV (`\x20`): `ZXZhdyAAAA==`
- `PANLAW 1` keeps gain math predictable alongside linear pre-FX automation.

### Folder Buses (`ISBUS`)
REAPER encodes folder hierarchy via `ISBUS <flag> <depth_delta>`:
- **Folder Parent (Bus):** `ISBUS 1 1`
- **Child Track inside Folder:** `ISBUS 0 0`
- **Last Child Track closing Folder:** `ISBUS 2 -1`
- **Standalone Track (e.g., Bass / FX Return):** `ISBUS 0 0`

### True-Stereo FX Sends (`AUXRECV`)
Place `AUXRECV` on the **receiving FX return track**, pointing to the **0-indexed
source track index** in order of appearance in the `.rpp`:
```text
    AUXRECV <src_track_idx> 0 <send_gain_linear> 0 0 0 0 0 0 -1:U 0 -1 ''
```
- `send_gain_linear = 10.0 ** (send_db / 20.0)`
- Set the reverb/delay plugin on the return track to 100% wet, and confirm the
  return stays stereo rather than collapsing to mono.

### Volume Automation (`<VOLENV>`, Never `<VOLENV2>`)
Use **`<VOLENV>` (pre-FX linear gain)**, not `<VOLENV2>` (which applies REAPER's
non-linear fader taper curve):
```text
    <VOLENV
      EGUID {UUID-HERE}
      ACT 1 -1
      VIS 1 1 1
      LANEHEIGHT 0 0
      ARM 0
      DEFSHAPE 0 -1 -1
      PT 0.0000 0.251189 0
      PT 26.8000 0.251189 0
      PT 27.0000 1.000000 0
    >
```
- Format: `PT <time_sec> <linear_gain> <shape>` (`0` = linear ramp).
- Because `<VOLENV>` is pre-FX / pre-fader, post-fader `AUXRECV` sends track it
  automatically.

### REAPER JSFX Blocks (`<FXCHAIN>` & `<MASTERFXLIST>`)
**Always read the first ~30 lines of the installed `.jsfx` file** before writing
slider values to verify exact slider order and units (`dB` vs `%` vs enum).
Verified stock REAPER limiter (`loser/MGA_JSLimiterST`: `slider1` Threshold dB,
`slider2` Release ms, `slider3` Link Stereo %, `slider4` Ceiling dB):
```text
      BYPASS 0 0 0
      <JS loser/MGA_JSLimiterST ""
        -2.0 120 100 -1.0 - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
      >
      WAK 0 0
      FXID {UUID-HERE}
```
- Pad unused slider slots (up to 64 tokens total) with `-` so REAPER preserves
  plugin defaults.
