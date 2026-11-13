#!/usr/bin/env python3
"""Hani & Mako audio pipeline.

Subcommands
  tts    Generate / refresh dialogue clips (cached by content hash) and
         write src/generated/audio-manifest.json (durations + mouth envelopes).
         A file in audio-src/overrides/<LINE_ID>.wav (e.g. a recorded voice
         actor) always replaces the synthetic voice for that line.
  sfx    Synthesize the original sound-effect library into public/audio/sfx/.
  mix    Read build/timeline.json (from `npm run export`) and build
         public/audio/mix.wav: dialogue + original music + ambience + SFX.
  master <in.mp4> <out.mp4>
         Two-pass EBU R128 loudness normalisation (-16 LUFS, <= -1 dBTP);
         video re-encoded to H.264 yuv420p BT.709 (limited range) for YouTube.
  asr    Transcribe each dialogue clip with faster-whisper and report
         similarity to the script (intelligibility smoke test).

All synthesis is deterministic (fixed seeds) so rebuilds are reproducible.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DIALOGUE = ROOT / "src/episode01/dialogue.json"
MANIFEST = ROOT / "src/generated/audio-manifest.json"
CLIP_DIR = ROOT / "public/audio/dialogue"
RAW_CACHE = ROOT / "build/tts-cache"
OVERRIDES = ROOT / "audio-src/overrides"
SFX_DIR = ROOT / "public/audio/sfx"
TIMELINE = ROOT / "build/timeline.json"
MIX = ROOT / "public/audio/mix.wav"
SR = 48000
FPS = 30
TTS_VERSION = "v3"  # bump to force regeneration of every clip


# --------------------------------------------------------------------------- io
def read_wav(path: Path) -> tuple[np.ndarray, int]:
    import soundfile as sf

    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return data.mean(axis=1), sr


def write_wav(path: Path, x: np.ndarray, sr: int = SR, stereo: bool = False) -> None:
    import soundfile as sf

    path.parent.mkdir(parents=True, exist_ok=True)
    if stereo and x.ndim == 1:
        x = np.stack([x, x], axis=1)
    sf.write(str(path), x.astype(np.float32), sr, subtype="PCM_16" if not stereo else "PCM_24")


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


# --------------------------------------------------------------------------- tts
def tts_text(text: str, pron: dict[str, str]) -> str:
    out = text
    for k, v in pron.items():
        out = out.replace(k, v)
    return out


def piper_synth(text: str, voice: dict, out: Path) -> None:
    from piper import PiperVoice, SynthesisConfig

    key = voice["model"]
    if key not in _VOICE_CACHE:
        _VOICE_CACHE[key] = PiperVoice.load(str(ROOT / key))
    v = _VOICE_CACHE[key]
    cfg = SynthesisConfig(
        length_scale=voice["length_scale"],
        noise_scale=voice["noise_scale"],
        noise_w_scale=voice["noise_w_scale"],
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as wf:
        v.synthesize_wav(text, wf, syn_config=cfg)


_VOICE_CACHE: dict = {}


def trim_and_level(x: np.ndarray, sr: int, target_lufs: float = -20.0) -> np.ndarray:
    import pyloudnorm as pyln

    # trim leading/trailing silence (-45 dB relative to peak)
    peak = np.max(np.abs(x)) + 1e-9
    thr = peak * 10 ** (-45 / 20)
    idx = np.where(np.abs(x) > thr)[0]
    if len(idx):
        a = max(0, idx[0] - int(0.03 * sr))
        b = min(len(x), idx[-1] + int(0.06 * sr))
        x = x[a:b]
    # short fades
    n = int(0.012 * sr)
    if len(x) > 2 * n:
        ramp = np.linspace(0, 1, n)
        x[:n] *= ramp
        x[-n:] *= ramp[::-1]
    meter = pyln.Meter(sr, block_size=min(0.4, max(0.1, len(x) / sr * 0.9)))
    try:
        loud = meter.integrated_loudness(x)
        if np.isfinite(loud):
            x = x * 10 ** ((target_lufs - loud) / 20)
    except Exception:
        x = x * (0.5 / peak)
    pk = np.max(np.abs(x))
    if pk > 0.89:
        x = x * (0.89 / pk)
    return x


def envelope(x: np.ndarray, sr: int, frames: int) -> list[float]:
    hop = sr / FPS
    env = []
    for f in range(frames):
        a = int(f * hop)
        b = int((f + 1) * hop)
        seg = x[a:b]
        if len(seg) == 0:
            env.append(0.0)
            continue
        rms = float(np.sqrt(np.mean(seg ** 2)) + 1e-9)
        db = 20 * math.log10(rms)
        v = (db + 44) / 28  # -44 dB -> 0, -16 dB -> 1
        env.append(round(float(min(1, max(0, v))), 3))
    # light smoothing (keeps syllable articulation)
    sm = env[:]
    for i in range(1, len(env) - 1):
        sm[i] = round(0.25 * env[i - 1] + 0.5 * env[i] + 0.25 * env[i + 1], 3)
    return sm


def render_speaker_clip(line: dict, speaker: str, cfg: dict) -> tuple[np.ndarray, str, str]:
    """Return (samples@48k, source, hash)."""
    voice = dict(cfg["voices"][speaker])
    voice["length_scale"] = round(voice["length_scale"] * line.get("stretch", 1.0), 4)
    suffix = "" if line["speaker"] != "both" else f"_{speaker}"
    override = OVERRIDES / f"{line['id']}{suffix}.wav"
    if override.exists():
        x, sr = read_wav(override)
        tmp = RAW_CACHE / f"ovr_{line['id']}{suffix}.wav"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg("-i", str(override), "-ac", "1", "-ar", str(SR), str(tmp))
        x, sr = read_wav(tmp)
        return trim_and_level(x, sr), "override", hashlib.sha1(override.read_bytes()).hexdigest()[:12]
    text = tts_text(line["text"], cfg["pronunciation"])
    h = hashlib.sha1(json.dumps([TTS_VERSION, text, voice], sort_keys=True).encode()).hexdigest()[:12]
    raw = RAW_CACHE / f"{h}_raw.wav"
    proc = RAW_CACHE / f"{h}_proc.wav"
    if not proc.exists():
        if not raw.exists():
            piper_synth(text, voice, raw)
        ratio = 2 ** (voice["pitch_semitones"] / 12)
        # pitch shift (formants follow -> a slightly smaller/larger "character" voice),
        # gentle high-pass and warmth, resample to 48 kHz mono
        ffmpeg(
            "-i", str(raw),
            "-af",
            f"rubberband=pitch={ratio:.5f}:transients=smooth:detector=soft,"
            "highpass=f=90,lowpass=f=9500,equalizer=f=3000:t=q:w=1.2:g=2",
            "-ac", "1", "-ar", str(SR), str(proc),
        )
    x, sr = read_wav(proc)
    return trim_and_level(x, sr), "tts-temp", h


def cmd_tts() -> None:
    cfg = json.loads(DIALOGUE.read_text())
    CLIP_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {"fps": FPS, "sampleRate": SR, "lines": {}}
    regenerated = 0
    for line in cfg["lines"]:
        speakers = ["hani", "mako"] if line["speaker"] == "both" else [line["speaker"]]
        parts = {}
        sources = set()
        hashes = []
        for sp in speakers:
            before = len(list(RAW_CACHE.glob("*_proc.wav"))) if RAW_CACHE.exists() else 0
            x, src, h = render_speaker_clip(line, sp, cfg)
            after = len(list(RAW_CACHE.glob("*_proc.wav")))
            regenerated += after - before
            parts[sp] = x
            sources.add(src)
            hashes.append(h)
        n = max(len(v) for v in parts.values())
        mix = np.zeros(n, dtype=np.float32)
        for v in parts.values():
            mix[: len(v)] += v * (0.75 if len(parts) > 1 else 1.0)
        out = CLIP_DIR / f"{line['id']}.wav"
        write_wav(out, mix)
        frames = int(math.ceil(n / SR * FPS))
        manifest["lines"][line["id"]] = {
            "speaker": line["speaker"],
            "text": line["text"],
            "file": f"audio/dialogue/{line['id']}.wav",
            "duration": round(n / SR, 3),
            "frames": frames,
            "source": "+".join(sorted(sources)),
            "hash": "+".join(hashes),
            "env": {sp: envelope(v, SR, frames) for sp, v in parts.items()},
        }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")))
    total = sum(l["duration"] for k, l in manifest["lines"].items())
    print(f"tts: {len(manifest['lines'])} lines, {regenerated} newly synthesized, "
          f"{total:.1f}s of dialogue audio -> {MANIFEST.relative_to(ROOT)}")


# --------------------------------------------------------------------------- synthesis helpers
def t_axis(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


def adsr(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    env = np.ones(n) * s
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    na = min(na, n)
    env[:na] = np.linspace(0, 1, na) if na else env[:na]
    nd = min(nd, max(0, n - na))
    env[na:na + nd] = np.linspace(1, s, nd) if nd else env[na:na + nd]
    if nr and n > nr:
        env[-nr:] *= np.linspace(1, 0, nr)
    return env


def mtof(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def marimba(freq: float, dur: float = 0.9, vel: float = 1.0) -> np.ndarray:
    t = t_axis(dur)
    x = (np.sin(2 * np.pi * freq * t) * np.exp(-t * 6.0)
         + 0.35 * np.sin(2 * np.pi * freq * 4.0 * t) * np.exp(-t * 18.0)
         + 0.12 * np.sin(2 * np.pi * freq * 10.0 * t) * np.exp(-t * 40.0))
    x *= adsr(len(t), 0.003, 0.0, 1.0, 0.05)
    return x * vel * 0.5


def pluck(freq: float, dur: float = 1.4, vel: float = 1.0, seed: int = 0) -> np.ndarray:
    """Karplus-Strong plucked string (ukulele-like)."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    period = max(2, int(SR / freq))
    buf = rng.uniform(-1, 1, period) * 0.5
    # soften the excitation
    buf = np.convolve(buf, np.ones(4) / 4, mode="same")
    reps = n // period + 1
    chunks = []
    for _ in range(reps):  # period-wise Karplus-Strong (vectorised)
        chunks.append(buf.copy())
        buf = 0.5 * (buf + np.roll(buf, -1)) * 0.9985
    out = np.concatenate(chunks)[:n]
    out *= adsr(n, 0.002, 0.0, 1.0, 0.08)
    return out * vel * 0.6


def soft_bass(freq: float, dur: float, vel: float = 1.0) -> np.ndarray:
    t = t_axis(dur)
    x = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(2 * np.pi * 2 * freq * t)
    return x * adsr(len(t), 0.01, 0.2, 0.6, 0.15) * vel * 0.45


def add(*xs: np.ndarray) -> np.ndarray:
    """Sum signals of different lengths (zero-padded)."""
    out = np.zeros(max(len(x) for x in xs))
    for x in xs:
        out[: len(x)] += x
    return out


def place(buf: np.ndarray, x: np.ndarray, at: float, gain: float = 1.0) -> None:
    i = int(at * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(x))
    buf[i:j] += x[: j - i] * gain


def one_pole_lp(x: np.ndarray, cutoff: float) -> np.ndarray:
    from scipy.signal import butter, lfilter

    b, a = butter(2, cutoff / (SR / 2), btype="low")
    return lfilter(b, a, x)


def band(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    from scipy.signal import butter, lfilter

    b, a = butter(2, [lo / (SR / 2), hi / (SR / 2)], btype="band")
    return lfilter(b, a, x)


# --------------------------------------------------------------------------- sfx
def make_sfx() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(7)
    s: dict[str, np.ndarray] = {}
    # soft "plop" of a strawberry landing on a plate: pitch-dropping sine + tiny ceramic tick
    t = t_axis(0.22)
    f = 520 * np.exp(-t * 9) + 180
    plop = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 22)
    tick = band(rng.normal(0, 1, len(t)), 2500, 6000) * np.exp(-t * 90) * 0.25
    s["plop"] = (plop + tick) * 0.32
    # gentle whoosh for a light toss
    t = t_axis(0.42)
    nz = band(rng.normal(0, 1, len(t)), 500, 2400)
    s["whoosh"] = nz * np.sin(np.pi * t / t[-1]) ** 2 * 0.16
    # soft hop (padded bounce)
    t = t_axis(0.2)
    f = 180 + 160 * np.exp(-t * 25)
    s["hop"] = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 18) * 0.45
    # little spring for the ear
    t = t_axis(0.5)
    f = 420 + 90 * np.sin(2 * np.pi * 9 * t) * np.exp(-t * 4)
    s["boing"] = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6) * 0.22
    # counting chimes: rising C major notes (gentle)
    for i, m in enumerate([72, 74, 76, 77, 79, 81], start=1):
        x = add(marimba(mtof(m), 1.0, 0.9), 0.3 * marimba(mtof(m + 12), 0.6, 0.5))
        s[f"count{i}"] = x * 0.55
    # success sparkle: soft arpeggio
    buf = np.zeros(int(1.6 * SR))
    for k, m in enumerate([79, 84, 88, 91]):
        place(buf, marimba(mtof(m), 1.0, 0.6), 0.09 * k)
    s["sparkle"] = buf * 0.5
    # "idea" ding
    s["idea"] = add(marimba(mtof(84), 1.2, 0.7), marimba(mtof(91), 1.0, 0.4)) * 0.5
    # pick-up blip (very soft)
    t = t_axis(0.1)
    s["pick"] = np.sin(2 * np.pi * (700 + 900 * t / 0.1) * t) * np.exp(-t * 35) * 0.18
    # pat / handoff tap
    t = t_axis(0.12)
    s["tap"] = band(rng.normal(0, 1, len(t)), 300, 1500) * np.exp(-t * 45) * 0.35
    # bird chirp for the ambience
    t = t_axis(0.16)
    f = 3200 + 1400 * np.sin(np.pi * t / 0.16)
    s["chirp"] = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / 0.16) * 0.10
    return s


def cmd_sfx() -> dict[str, np.ndarray]:
    s = make_sfx()
    for k, v in s.items():
        write_wav(SFX_DIR / f"{k}.wav", v.astype(np.float32))
    print(f"sfx: {len(s)} effects -> {SFX_DIR.relative_to(ROOT)}")
    return s


# --------------------------------------------------------------------------- music
# Original arrangement: I - vi - IV - V in F major, 100 BPM, ukulele-like plucks,
# marimba melody, soft bass. Sections are faded in/out according to the timeline.
MUSIC_VERSION = 2  # bump when the arrangement code changes
BPM = 100
BEAT = 60 / BPM
CHORDS = {  # midi notes
    "F": [53, 57, 60, 65], "Dm": [50, 57, 62, 65], "Bb": [46, 58, 62, 65], "C": [48, 55, 60, 64],
    "Gm": [55, 58, 62, 67], "A7": [57, 61, 64, 67],
}
PROG_A = ["F", "Dm", "Bb", "C"]
PROG_B = ["Bb", "C", "F", "Dm", "Gm", "C", "F", "F"]
MELODY_A = [  # (beat offset within 4-bar phrase, midi, beats)
    (0, 72, 1), (1, 74, 0.5), (1.5, 72, 0.5), (2, 69, 1), (3, 67, 1),
    (4, 69, 1), (5, 72, 1), (6, 74, 1.5), (7.5, 72, 0.5),
    (8, 70, 1), (9, 69, 0.5), (9.5, 70, 0.5), (10, 74, 1), (11, 72, 1),
    (12, 72, 1), (13, 74, 0.5), (13.5, 76, 0.5), (14, 77, 2),
]
MELODY_B = [
    (0, 74, 1), (1, 72, 1), (2, 70, 1), (3, 69, 1),
    (4, 67, 1.5), (5.5, 69, 0.5), (6, 72, 2),
    (8, 77, 1), (9, 76, 1), (10, 74, 1), (11, 72, 1),
    (12, 72, 1), (13, 69, 1), (14, 72, 2),
]


def build_music(total: float, sections: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """Return (chords+bass stem, melody stem)."""
    n = int(total * SR) + SR
    bed = np.zeros(n)
    mel = np.zeros(n)
    bar = 4 * BEAT
    bars = int(total / bar) + 2
    seed = 0
    for b in range(bars):
        t0 = b * bar
        prog = PROG_A if (b // 8) % 2 == 0 else PROG_B
        ch = CHORDS[prog[b % len(prog)]]
        # strum pattern: down on 1, light on 2&, 3, 4
        for off, vel in [(0, 1.0), (1.5, 0.55), (2, 0.8), (3, 0.6)]:
            for k, m in enumerate(ch[1:]):
                seed += 1
                place(bed, pluck(mtof(m + 12), 1.2, vel * 0.5, seed), t0 + off * BEAT + 0.012 * k)
        place(bed, soft_bass(mtof(ch[0] - 12 if ch[0] > 50 else ch[0]), bar * 1.08, 0.7), t0)
        # soft sustained pad glues the bars together
        for m in ch[1:]:
            tt = t_axis(bar + 0.5)
            pad = np.sin(2 * np.pi * mtof(m) * tt) * adsr(len(tt), 0.35, 0.0, 1.0, 0.5) * 0.05
            place(bed, pad, t0)
        phrase = (b // 4) % 4
        melody = MELODY_A if phrase in (0, 2) else MELODY_B
        if b % 4 == 0:
            for off, m, d in melody:
                place(mel, marimba(mtof(m), min(1.2, d * BEAT + 0.4), 0.55), t0 + off * BEAT)
    return bed[:n], mel[:n]


def automation(total: float, sections: list[dict], mode_gain: dict[str, tuple[float, float]]) -> tuple[np.ndarray, np.ndarray]:
    """Piecewise gains with 0.8 s crossfades for the two music stems."""
    n = int(total * SR) + SR
    g_bed = np.zeros(n)
    g_mel = np.zeros(n)
    for s in sections:
        a, b = int(s["start"] * SR), int(s["end"] * SR)
        gb, gm = mode_gain[s["mode"]]
        g_bed[a:b] = gb
        g_mel[a:b] = gm
    k = int(0.8 * SR)
    win = np.hanning(k) / np.hanning(k).sum()
    g_bed = np.convolve(g_bed, win, mode="same")
    g_mel = np.convolve(g_mel, win, mode="same")
    return g_bed, g_mel


def cmd_mix() -> None:
    tl = json.loads(TIMELINE.read_text())
    total = tl["totalFrames"] / tl["fps"]
    n = int(total * SR)
    sfx = cmd_sfx()

    # ---- dialogue bus
    dia = np.zeros(n + SR)
    speech_mask = np.zeros(n + SR)
    for sp in tl["speech"]:
        x, sr = read_wav(ROOT / "public" / sp["file"])
        at = sp["start"] / tl["fps"]
        place(dia, x, at)
        a = int(at * SR)
        speech_mask[a:a + len(x)] = 1.0

    # ---- music bus with ducking under dialogue
    mode_gain = {
        "full": (0.55, 0.55), "light": (0.42, 0.0), "quiet": (0.22, 0.0),
        "silent": (0.0, 0.0), "warm": (0.5, 0.45), "finale": (0.62, 0.6),
    }
    cache = ROOT / f"build/music-cache-{MUSIC_VERSION}-{total:.3f}.npz"
    if cache.exists():
        z = np.load(cache)
        bed, mel = z["bed"], z["mel"]
    else:
        bed, mel = build_music(total, tl["music"])
        np.savez(cache, bed=bed, mel=mel)
    g_bed, g_mel = automation(total, tl["music"], mode_gain)
    k = int(0.35 * SR)
    duck_env = np.convolve(speech_mask, np.ones(k) / k, mode="same")
    duck = 1.0 - 0.55 * np.clip(duck_env * 1.5, 0, 1)  # ~ -7 dB under speech
    music = (bed[: n + SR] * g_bed[: n + SR] + mel[: n + SR] * g_mel[: n + SR]) * duck
    # tail fade
    fade = int(2.0 * SR)
    music[n - fade:n] *= np.linspace(1, 0, fade)
    music[n:] = 0

    # ---- ambience: soft air + occasional birds
    rng = np.random.default_rng(11)
    air = one_pole_lp(rng.normal(0, 1, n + SR), 900) * 0.012
    amb = air.copy()
    t = 2.0
    while t < total - 1:
        place(amb, sfx["chirp"], t, 0.8)
        place(amb, sfx["chirp"], t + 0.22, 0.6)
        t += 5.5 + rng.uniform(0, 4)

    # ---- effects
    fx = np.zeros(n + SR)
    for e in tl["sfx"]:
        name = e["name"]
        if name in sfx:
            place(fx, sfx[name], e["frame"] / tl["fps"], e.get("gain", 1.0))

    mix = dia * 1.0 + music * 0.42 + amb * 1.0 + fx * 0.8
    mix = mix[:n]
    # soft safety limiter (final loudness handled by `master`)
    pk = np.max(np.abs(mix))
    if pk > 0.95:
        mix = mix * (0.95 / pk)
    write_wav(MIX, mix.astype(np.float32), stereo=True)
    # stems for future edits
    write_wav(ROOT / "build/stems/dialogue.wav", dia[:n].astype(np.float32))
    write_wav(ROOT / "build/stems/music.wav", (music[:n] * 0.42).astype(np.float32))
    write_wav(ROOT / "build/stems/fx_amb.wav", (fx[:n] * 0.8 + amb[:n]).astype(np.float32))
    write_wav(ROOT / "public/audio/music/music_bed.wav", (music[:n] * 0.42).astype(np.float32))
    print(f"mix: {total:.2f}s -> {MIX.relative_to(ROOT)} (peak {20*math.log10(pk+1e-9):.1f} dBFS pre-limit)")


# --------------------------------------------------------------------------- master
def cmd_master(src: str, dst: str) -> None:
    probe = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", src, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
         "-f", "null", "-"], capture_output=True, text=True)
    txt = probe.stderr[probe.stderr.rfind("{"):]
    m = json.loads(txt)
    af = ("loudnorm=I=-16:TP=-1.5:LRA=11:"
          f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
          f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
          "aresample=48000")
    ffmpeg("-i", src, "-map", "0:v", "-map", "0:a",
           "-vf", "scale=in_range=full:out_range=tv,format=yuv420p",
           "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high", "-level", "4.1",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
           "-r", "30", "-af", af,
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", dst)
    print(f"master: {dst} (input {m['input_i']} LUFS / {m['input_tp']} dBTP)")


# --------------------------------------------------------------------------- asr
def cmd_asr() -> None:
    from difflib import SequenceMatcher

    from faster_whisper import WhisperModel

    cfg = json.loads(DIALOGUE.read_text())
    model = WhisperModel(os.environ.get("ASR_MODEL", "small"), device="cpu", compute_type="int8")
    rows = []
    for line in cfg["lines"]:
        from scipy.signal import resample_poly

        x, sr = read_wav(CLIP_DIR / f"{line['id']}.wav")
        x16 = resample_poly(x, 1, 3).astype(np.float32)  # 48k -> 16k
        x16 = np.concatenate([np.zeros(8000, np.float32), x16, np.zeros(8000, np.float32)])
        segs, _ = model.transcribe(x16, language="vi", beam_size=5)
        hyp = " ".join(s.text.strip() for s in segs)

        def norm(s: str) -> str:
            return "".join(ch for ch in s.lower() if ch.isalnum() or ch == " ").split().__str__()

        ratio = SequenceMatcher(None, norm(line["text"]), norm(hyp)).ratio()
        rows.append((line["id"], ratio, line["text"], hyp))
        print(f"{line['id']:8s} {ratio:4.2f} | {line['text']} | {hyp}")
    out = ROOT / "build/asr-report.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f"mean similarity {np.mean([r[1] for r in rows]):.2f} -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tts"
    if cmd == "tts":
        cmd_tts()
    elif cmd == "sfx":
        cmd_sfx()
    elif cmd == "mix":
        cmd_mix()
    elif cmd == "master":
        cmd_master(sys.argv[2], sys.argv[3])
    elif cmd == "asr":
        cmd_asr()
    else:
        sys.exit(__doc__)
