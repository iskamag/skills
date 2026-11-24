#!/usr/bin/env python3
"""Portable Overlapping Ear-Chunk Slicer & Optional Audio Analyzer.

Minimal-dependency CLI (numpy + ffmpeg; optional soundfile) for ear-verified
music production:
  - Automatic overlapping MP3 chunk slicing for direct ear listening via read_file
  - Optional acoustic summary (EBU R128, crest, 7-band PSD, band correlation,
    centroid/tilt, BPM, chroma, and full-track or per-section reference comparison)

Usage examples:
  # Slice overlapping ear-audit chunks (fast, no analysis needed):
  python3 audio_telemetry.py --input output/master.wav --slice-chunks reviews/master_chunks

  # Optional section comparison against a saved reference clip JSON:
  python3 audio_telemetry.py --input output/master.wav \
      --segments Intro:0:27 Main:27:95 Bridge:95:127 Outro:198:225 \
      --compare research/ref_clip01.json --compare-section Main
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import soundfile as sf  # type: ignore
except ImportError:
    sf = None

BANDS: List[Tuple[str, float, float]] = [
    ("sub", 20.0, 60.0),
    ("bass", 60.0, 150.0),
    ("low_mid", 150.0, 400.0),
    ("mid", 400.0, 1200.0),
    ("upper_mid", 1200.0, 3500.0),
    ("presence", 3500.0, 8000.0),
    ("air", 8000.0, 18000.0),
]

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def decode_stereo(
    path: Path, sr: int = 44100, start: Optional[float] = None, end: Optional[float] = None
) -> Tuple[np.ndarray, int]:
    """Decode any ffmpeg-supported audio file (or slice) into float32 stereo (N, 2)."""
    if sf is not None and start is None and end is None and path.suffix.lower() in {".wav", ".flac", ".aiff", ".aif"}:
        data, file_sr = sf.read(str(path), always_2d=True, dtype="float32")
        if data.shape[1] == 1:
            data = np.repeat(data, 2, axis=1)
        elif data.shape[1] > 2:
            data = data[:, :2]
        if file_sr == sr:
            return data, file_sr

    cmd = ["ffmpeg", "-v", "error", "-i", str(path)]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    if end is not None and start is not None:
        cmd += ["-t", f"{max(0.01, end - start):.3f}"]
    elif end is not None:
        cmd += ["-t", f"{end:.3f}"]
    cmd += ["-ac", "2", "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.check_output(cmd)
    data = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)
    return data, sr


def _parse_float_or_none(val: str) -> Optional[float]:
    if val.lower() in {"-inf", "inf", "nan"}:
        return None
    return float(val)


def measure_ebur128(
    path: Path, start: Optional[float] = None, end: Optional[float] = None
) -> Dict[str, Optional[float]]:
    """Measure integrated LUFS, LRA (LU), and True Peak (dBTP) via ffmpeg ebur128."""
    cmd = ["ffmpeg", "-nostats", "-i", str(path)]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    if end is not None and start is not None:
        cmd += ["-t", f"{max(0.01, end - start):.3f}"]
    elif end is not None:
        cmd += ["-t", f"{end:.3f}"]
    cmd += ["-af", "ebur128=peak=true", "-f", "null", "-"]
    proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
    if proc.returncode != 0:
        print(f"WARNING: ffmpeg ebur128 failed (rc={proc.returncode})", file=sys.stderr)
        return {"lufs": None, "lra_lu": None, "true_peak_dbtp": None}
    text = proc.stderr
    lufs = lra = tp = None
    m = re.search(r"Integrated loudness:\s*\n\s*I:\s*([-\d.]+|-inf)\s*LUFS", text, re.IGNORECASE)
    if m:
        lufs = _parse_float_or_none(m.group(1))
    m = re.search(r"Loudness range:\s*\n\s*LRA:\s*([-\d.]+|-inf)\s*LU", text, re.IGNORECASE)
    if m:
        lra = _parse_float_or_none(m.group(1))
    m = re.search(r"True peak:\s*\n\s*Peak:\s*([-\d.]+|-inf)\s*dBFS", text, re.IGNORECASE)
    if m:
        tp = _parse_float_or_none(m.group(1))
    return {"lufs": lufs, "lra_lu": lra, "true_peak_dbtp": tp}


def estimate_bpm(mono: np.ndarray, sr: int = 44100) -> List[Dict[str, float]]:
    """Estimate top BPM candidates (70-230 BPM) via low/high onset flux autocorrelation."""
    nfft = 1024
    hop = 256
    fps = sr / hop
    n_frames = (len(mono) - nfft) // hop
    if n_frames < 50:
        return []
    win = np.hanning(nfft)
    freqs = np.fft.rfftfreq(nfft, 1.0 / sr)
    low_m = (freqs >= 50.0) & (freqs <= 220.0)
    high_m = (freqs >= 1200.0) & (freqs <= 7000.0)

    prev_lo = prev_hi = None
    flux_lo = np.zeros(n_frames)
    flux_hi = np.zeros(n_frames)
    for i in range(n_frames):
        frame = mono[i * hop : i * hop + nfft] * win
        mag = np.log1p(10.0 * np.abs(np.fft.rfft(frame)))
        ml, mh = mag[low_m], mag[high_m]
        if prev_lo is not None:
            flux_lo[i] = float(np.sum(np.maximum(0.0, ml - prev_lo)))
            flux_hi[i] = float(np.sum(np.maximum(0.0, mh - prev_hi)))
        prev_lo, prev_hi = ml, mh

    fl = (flux_lo - np.mean(flux_lo)) / (np.std(flux_lo) + 1e-12)
    fh = (flux_hi - np.mean(flux_hi)) / (np.std(flux_hi) + 1e-12)
    env = 0.55 * fl + 0.45 * fh
    env -= np.mean(env)

    ac = np.correlate(env, env, mode="full")[len(env) - 1 :]
    ac /= ac[0] + 1e-12

    lag_min = max(1, int(fps * 60.0 / 230.0))
    lag_max = min(len(ac) - 2, int(fps * 60.0 / 70.0))
    if lag_max <= lag_min + 2:
        return []
    region = ac[lag_min : lag_max + 1]

    peaks: List[Tuple[float, float]] = []
    for k in range(1, len(region) - 1):
        if region[k] > region[k - 1] and region[k] > region[k + 1] and region[k] > 0.05:
            lag = lag_min + k
            y0, y1, y2 = region[k - 1], region[k], region[k + 1]
            denom = y0 - 2.0 * y1 + y2
            delta = 0.5 * (y0 - y2) / denom if abs(denom) > 1e-12 else 0.0
            bpm = 60.0 * fps / (lag + delta)
            peaks.append((float(region[k]), round(float(bpm), 1)))
    peaks.sort(reverse=True)

    out: List[Tuple[float, float]] = []
    for score, bpm in peaks:
        if all(abs(bpm - b) > 3.0 for _, b in out):
            out.append((round(score, 3), bpm))
        if len(out) >= 4:
            break
    return [{"bpm": b, "strength": s} for s, b in out]


def compute_chroma(psd: np.ndarray, freqs: np.ndarray) -> List[Dict[str, object]]:
    """Estimate top 5 pitch classes across 75-1400 Hz (A4 = 440 Hz)."""
    chroma = np.zeros(12)
    mask = (freqs >= 75.0) & (freqs <= 1400.0)
    for f, p in zip(freqs[mask], psd[mask]):
        midi = 69.0 + 12.0 * np.log2(f / 440.0)
        pc = int(np.round(midi)) % 12
        chroma[pc] += p
    chroma /= float(np.sum(chroma)) + 1e-18
    ranked = sorted(
        [(round(float(v * 100.0), 1), NOTE_NAMES[i]) for i, v in enumerate(chroma)],
        reverse=True,
    )
    return [{"note": n, "pct": v} for v, n in ranked[:5]]


def analyze_audio(stereo: np.ndarray, sr: int = 44100, with_bpm: bool = True) -> Dict[str, object]:
    """Compute dynamics, stereo, 7-band Welch PSD, centroid, 1/3-oct tilt, BPM, and chroma."""
    L = stereo[:, 0].astype(np.float64)
    R = stereo[:, 1].astype(np.float64)
    M = 0.5 * (L + R)
    S = 0.5 * (L - R)

    rms = float(np.sqrt(np.mean(stereo.astype(np.float64) ** 2)) + 1e-12)
    peak = float(np.max(np.abs(stereo)) + 1e-12)
    rms_db = 20.0 * np.log10(rms)
    peak_db = 20.0 * np.log10(peak)
    crest_db = peak_db - rms_db

    hop = int(sr * 0.4)
    n_frames = len(M) // hop if hop > 0 else 0
    if n_frames >= 4:
        st_rms = np.array([
            20.0 * np.log10(float(np.sqrt(np.mean(stereo[i * hop : (i + 1) * hop] ** 2))) + 1e-12)
            for i in range(n_frames)
        ])
        dr_p95_p10 = float(np.percentile(st_rms, 95) - np.percentile(st_rms, 10))
    else:
        dr_p95_p10 = 0.0

    corr = float(np.corrcoef(L, R)[0, 1]) if np.std(L) > 0 and np.std(R) > 0 else 1.0
    m_rms = float(np.sqrt(np.mean(M ** 2)) + 1e-12)
    s_rms = float(np.sqrt(np.mean(S ** 2)) + 1e-12)
    side_to_mid_db = 20.0 * np.log10(s_rms / m_rms)

    nfft = 8192
    step = nfft // 2
    win = np.hanning(nfft)
    win_norm = float(np.sum(win ** 2))
    psd_L = np.zeros(nfft // 2 + 1)
    psd_R = np.zeros(nfft // 2 + 1)
    psd_cross = np.zeros(nfft // 2 + 1, dtype=np.complex128)
    count = 0
    for i in range(0, len(L) - nfft + 1, step):
        XL = np.fft.rfft(L[i : i + nfft] * win)
        XR = np.fft.rfft(R[i : i + nfft] * win)
        psd_L += np.abs(XL) ** 2
        psd_R += np.abs(XR) ** 2
        psd_cross += XL * np.conj(XR)
        count += 1
    if count == 0:
        pad_L = np.pad(L, (0, max(0, nfft - len(L))))[:nfft]
        pad_R = np.pad(R, (0, max(0, nfft - len(R))))[:nfft]
        XL = np.fft.rfft(pad_L * win)
        XR = np.fft.rfft(pad_R * win)
        psd_L = np.abs(XL) ** 2
        psd_R = np.abs(XR) ** 2
        psd_cross = XL * np.conj(XR)
        count = 1
    psd_L /= count * win_norm
    psd_R /= count * win_norm
    psd_cross /= count * win_norm
    psd = 0.5 * (psd_L + psd_R)
    freqs = np.fft.rfftfreq(nfft, 1.0 / sr)

    total_power = float(np.sum(psd[(freqs >= 20.0) & (freqs <= 18000.0)]) + 1e-18)
    band_rel_db: Dict[str, float] = {}
    band_corr: Dict[str, float] = {}
    for name, f0, f1 in BANDS:
        mask = (freqs >= f0) & (freqs < f1)
        bp = float(np.sum(psd[mask]) + 1e-18)
        band_rel_db[name] = round(10.0 * np.log10(bp / total_power), 2)
        num = float(np.real(np.sum(psd_cross[mask])))
        den = float(np.sqrt(np.sum(psd_L[mask]) * np.sum(psd_R[mask])) + 1e-18)
        band_corr[name] = round(num / den, 3)

    mag = np.sqrt(psd)
    valid = (freqs >= 20.0) & (freqs <= 18000.0)
    centroid_hz = float(np.sum(freqs[valid] * mag[valid]) / (np.sum(mag[valid]) + 1e-12))
    cum_p = np.cumsum(psd[valid])
    rolloff_idx = int(np.searchsorted(cum_p, 0.85 * cum_p[-1]))
    rolloff85_hz = float(freqs[valid][min(rolloff_idx, int(np.sum(valid)) - 1)])

    # 1/3-octave integrated band energy tilt (pink noise ~= 0 dB/oct)
    oct_centers = 100.0 * (2.0 ** (np.arange(0, 21) / 3.0))
    oct_x, oct_y = [], []
    for fc in oct_centers:
        f_lo, f_hi = fc / (2.0 ** (1.0 / 6.0)), fc * (2.0 ** (1.0 / 6.0))
        m_oct = (freqs >= f_lo) & (freqs < f_hi)
        if np.any(m_oct):
            p_oct = float(np.sum(psd[m_oct]) + 1e-18)
            oct_x.append(float(np.log2(fc)))
            oct_y.append(float(10.0 * np.log10(p_oct)))
    tilt = float(np.polyfit(oct_x, oct_y, 1)[0]) if len(oct_x) > 2 else 0.0

    result: Dict[str, object] = {
        "duration_s": round(len(M) / sr, 2),
        "rms_dbfs": round(rms_db, 2),
        "peak_dbfs": round(peak_db, 2),
        "crest_factor_db": round(crest_db, 2),
        "short_term_dr_db": round(dr_p95_p10, 2),
        "stereo_corr": round(corr, 3),
        "side_to_mid_db": round(side_to_mid_db, 2),
        "band_corr": band_corr,
        "spectral_centroid_hz": round(centroid_hz, 1),
        "spectral_rolloff85_hz": round(rolloff85_hz, 1),
        "spectral_tilt_db_per_oct": round(tilt, 2),
        "band_rel_db": band_rel_db,
        "top_pitch_classes": compute_chroma(psd, freqs),
    }
    if with_bpm:
        result["bpm_candidates"] = estimate_bpm(M, sr)
    return result


def slice_overlapping_chunks(
    audio_path: Path, out_dir: Path, duration_s: float, chunk_sec: float = 38.0, overlap_sec: float = 5.0
) -> List[str]:
    """Slice audio into overlapping MP3 chunks covering 100% of duration for read_file listening."""
    out_dir.mkdir(parents=True, exist_ok=True)
    step = max(5.0, chunk_sec - overlap_sec)
    created: List[str] = []
    idx = 1
    t = 0.0
    while t < duration_s:
        end = min(duration_s, t + chunk_sec)
        if end - t < 2.0 and idx > 1:
            break
        out_file = out_dir / f"chunk_{idx:02d}_{int(t):03d}s_to_{int(math.ceil(end)):03d}s.mp3"
        cmd = [
            "ffmpeg", "-v", "error", "-y",
            "-ss", f"{t:.3f}", "-i", str(audio_path), "-t", f"{end - t:.3f}",
            "-b:a", "192k", str(out_file),
        ]
        subprocess.run(cmd, check=True)
        created.append(str(out_file))
        if end >= duration_s - 0.1:
            break
        t += step
        idx += 1
    return created


def parse_segment_spec(spec: str) -> Tuple[str, float, float]:
    parts = spec.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid --segments item '{spec}'; expected name:start_sec:end_sec")
    return parts[0], float(parts[1]), float(parts[2])


def load_compare_target(compare_path: Path) -> Optional[Dict[str, object]]:
    """Load a reference summary block from this script's JSON or custom reference JSON."""
    data = json.loads(compare_path.read_text(encoding="utf-8"))
    for key in ("reference_target", "reference_average", "full_track"):
        if key in data and isinstance(data[key], dict) and "band_rel_db" in data[key]:
            return data[key]
    if "band_rel_db" in data:
        return data
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Portable overlapping ear-chunk slicer and optional audio analyzer."
    )
    parser.add_argument("--input", required=True, help="Input audio file (WAV, MP3, FLAC, OPUS, WEBM, etc.)")
    parser.add_argument("--sr", type=int, default=44100, help="Analysis sample rate (default: 44100)")
    parser.add_argument(
        "--segments", nargs="*", default=[],
        help="Optional named segments as name:start_sec:end_sec (e.g. Intro:0:27 Main:27:95)",
    )
    parser.add_argument("--segments-json", default=None, help="Optional JSON list of [name, start_s, end_s]")
    parser.add_argument("--compare", default=None, help="Optional reference JSON to print deltas against")
    parser.add_argument(
        "--compare-section", default=None,
        help="Compare a named --segments section instead of full_track against --compare",
    )
    parser.add_argument("--slice-chunks", default=None, help="Output directory for overlapping ear-check MP3s")
    parser.add_argument("--chunk-sec", type=float, default=38.0, help="Ear chunk length in seconds (default: 38)")
    parser.add_argument("--overlap-sec", type=float, default=5.0, help="Ear chunk overlap in seconds (default: 5)")
    parser.add_argument("--no-bpm", action="store_true", help="Skip BPM autocorrelation for faster runs")
    parser.add_argument("--json-out", default=None, help="Optional output JSON report path")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"ERROR: Input file not found: {in_path}", file=sys.stderr)
        return 1

    stereo, sr = decode_stereo(in_path, sr=args.sr)
    if len(stereo) == 0:
        print(f"ERROR: Decoded 0 audio samples from {in_path}", file=sys.stderr)
        return 1
    dur_s = len(stereo) / float(sr)

    full = analyze_audio(stereo, sr=sr, with_bpm=not args.no_bpm)
    full.update(measure_ebur128(in_path))

    seg_specs: List[Tuple[str, float, float]] = [parse_segment_spec(s) for s in args.segments]
    if args.segments_json:
        raw_segs = json.loads(Path(args.segments_json).read_text(encoding="utf-8"))
        for name, t0, t1 in raw_segs:
            seg_specs.append((str(name), float(t0), float(t1)))

    sections: Dict[str, Dict[str, object]] = {}
    for name, t0, t1 in seg_specs:
        t0c = max(0.0, t0)
        t1c = min(dur_s, t1)
        if t1c <= t0c + 0.5:
            continue
        seg = stereo[int(t0c * sr) : int(t1c * sr)]
        m = analyze_audio(seg, sr=sr, with_bpm=not args.no_bpm)
        m.update(measure_ebur128(in_path, t0c, t1c))
        sections[name] = m

    report: Dict[str, object] = {
        "input_path": str(in_path.resolve()),
        "sample_rate": sr,
        "full_track": full,
        "sections": sections,
    }

    if args.slice_chunks:
        report["ear_chunks"] = slice_overlapping_chunks(
            in_path, Path(args.slice_chunks), dur_s, chunk_sec=args.chunk_sec, overlap_sec=args.overlap_sec
        )

    # Human-readable summary table
    print("=" * 104)
    print(f"AUDIO SUMMARY: {in_path.name} ({dur_s:.2f}s @ {sr} Hz)")
    print("=" * 104)
    print(
        f"Full Track | LUFS={full['lufs']}  LRA={full['lra_lu']}  TP={full['true_peak_dbtp']} dBTP  "
        f"RMS={full['rms_dbfs']} dBFS  Crest={full['crest_factor_db']} dB  "
        f"Corr={full['stereo_corr']:+.3f}  S/M={full['side_to_mid_db']} dB"
    )
    print(
        f"Spectrum   | Centroid={full['spectral_centroid_hz']} Hz  Rolloff85={full['spectral_rolloff85_hz']} Hz  "
        f"Tilt={full['spectral_tilt_db_per_oct']:+.2f} dB/oct  "
        f"TopNotes={[x['note'] for x in full['top_pitch_classes'][:4]]}"
    )
    if "bpm_candidates" in full:
        print(f"BPM Est    | {[(x['bpm'], x['strength']) for x in full['bpm_candidates'][:3]]}")

    print("-" * 104)
    bd = full["band_rel_db"]
    bc = full["band_corr"]
    print(f"{'Band':12s} {'Level (dB)':>11s} {'Band Corr':>11s}")
    for bname, _, _ in BANDS:
        print(f"{bname:12s} {bd[bname]:11.2f} {bc[bname]:+11.3f}")

    if sections:
        print("-" * 104)
        print(
            f"{'Section':16s} {'LUFS':>6s} {'Crest':>6s} {'Corr':>6s} {'Cent':>6s} {'Tilt':>6s} | "
            f"{'sub':>5s} {'bass':>5s} {'lmid':>5s} {'mid':>5s} {'umid':>5s} {'pres':>5s} {'air':>5s}"
        )
        for name, m in sections.items():
            sbd = m["band_rel_db"]
            lufs_s = f"{m['lufs']:6.1f}" if m["lufs"] is not None else "   N/A"
            print(
                f"{name:16s} {lufs_s} {m['crest_factor_db']:6.1f} {m['stereo_corr']:+6.2f} "
                f"{m['spectral_centroid_hz']:6.0f} {m['spectral_tilt_db_per_oct']:+6.2f} | "
                f"{sbd['sub']:5.1f} {sbd['bass']:5.1f} {sbd['low_mid']:5.1f} {sbd['mid']:5.1f} "
                f"{sbd['upper_mid']:5.1f} {sbd['presence']:5.1f} {sbd['air']:5.1f}"
            )

    if args.compare:
        ref = load_compare_target(Path(args.compare))
        if ref is not None:
            if args.compare_section and args.compare_section in sections:
                src_label = f"Section '{args.compare_section}'"
                src_metrics = sections[args.compare_section]
            else:
                src_label = "Full Track"
                src_metrics = full
            src_bd = src_metrics["band_rel_db"]
            deltas = {
                b: round(float(src_bd[b]) - float(ref["band_rel_db"][b]), 2)
                for b, _, _ in BANDS
                if b in ref["band_rel_db"]
            }
            report["compare_deltas_db"] = deltas
            print("-" * 104)
            print(f"COMPARISON VS {Path(args.compare).name} ({src_label} vs Ref Target):")
            print(
                f"  LUFS: {src_metrics['lufs']} vs {ref.get('lufs')} | "
                f"Crest: {src_metrics['crest_factor_db']} vs {ref.get('crest_factor_db')} dB | "
                f"Corr: {src_metrics['stereo_corr']:+.3f} vs {ref.get('stereo_corr')} | "
                f"Cent: {src_metrics['spectral_centroid_hz']} vs {ref.get('spectral_centroid_hz')} Hz"
            )
            print("  7-Band Deltas (dB):", deltas)

    if args.slice_chunks:
        print("-" * 104)
        print(f"Sliced {len(report['ear_chunks'])} overlapping ear chunks into {args.slice_chunks}")

    if args.json_out:
        out_p = Path(args.json_out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote JSON report: {out_p}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
