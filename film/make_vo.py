#!/usr/bin/env python3
"""Generate the demo voiceover with Gemini TTS (the VO itself is Google-stack).

Outputs film/vo/seg{N}.wav + film/vo/timings.json {durations, scene starts}.
Scene N runs for VO duration + PAD seconds; film.html consumes the same timings,
so audio and visuals share one deterministic timeline.
"""
import json
import os
import pathlib
import subprocess
import sys
import wave

from google import genai
from google.genai import types

OUT = pathlib.Path(__file__).resolve().parent / "vo"
PAD = 1.6  # breathing room after each VO segment, seconds

STYLE = ("Narrate in a confident, measured, technical product-demo tone, "
         "medium pace, no theatrics: ")

SEGMENTS = [
    # S1 — title
    "Sentinel Mesh — a verified-memory control plane for A2A agent fleets. "
    "Agent memory is everywhere now. But every memory layer ships gullible — "
    "it stores whatever an agent says. We put a referee in the message path.",
    # S2 — real google stack
    "Three real Google ADK agents, talking over the A2A protocol — live agent "
    "cards. A three-lens adversarial Gemini panel sits in the message path, "
    "grounded in a provenance memory store.",
    # S3 — run 1
    "Run one — cold memory. The first claim survives all three lenses and is "
    "written back, verified. The refund claim is vetoed by a deterministic "
    "tripwire — no model in that decision. And the lie? It contradicts advisory "
    "memory — but advisory memory is unverified, so the panel refuses to kill it. "
    "Suspicion, not certainty. The operator files a correction — and even the "
    "correction must pass the referee before it enters the ledger.",
    # S4 — run 2 reveal
    "Run two. Same agents, same claims. The verified claim is served straight "
    "from memory — zero Gemini calls, half a millisecond. And the same lie is "
    "now vetoed: the referee reads run one's verified correction as ground "
    "truth. Flag became veto. The fleet got more reliable — and cheaper — with "
    "zero retraining. Nothing changed but memory.",
    # S5 — A2A seam
    "And it binds to real Google A2A — the referee hooks A D K's before-tool "
    "callback, so a vetoed claim never even lands.",
    # S6 — eval + live playground
    "We also examined the examiner. A thirty-claim eval set — paraphrase edges, "
    "advisory contradictions, tripwire negatives — run through Google's A D K "
    "eval framework. It caught a real failure mode; we fixed the rubric; one "
    "hundred percent verdict accuracy across three runs. And the referee is "
    "live on Cloud Run — type your own lie, and watch it get stamped.",
    # S7 — herd immunity (cross-fleet trust passport)
    "But verification doesn't have to stop at one fleet. The verified ledger is "
    "portable. One fleet exports a signed Trust Passport — and a second fleet, "
    "which never ran the panel, inherits the immunity. It vetoes a lie it has "
    "never seen, and re-serves a verified fact at zero Gemini calls. A control "
    "fleet without the passport only flags the same lie. One fleet earns the "
    "immunity; every fleet inherits it.",
    # S8 — close
    "Unverified memory can make you suspicious. Only verified memory can make "
    "you certain. Sentinel Mesh — verify in the message path, remember what "
    "survives, get smarter every run.",
]


def synth(client, text, path):
    import re
    import time as _time
    from google.genai import errors
    for attempt in range(5):
        try:
            return _synth_once(client, text, path)
        except errors.ClientError as e:
            if getattr(e, "code", None) != 429 or attempt == 4:
                raise
            m = re.search(r"retry in (\d+(?:\.\d+)?)s", str(e), re.I)
            _time.sleep(float(m.group(1)) + 2 if m else 40)


def _synth_once(client, text, path):
    r = client.models.generate_content(
        model="gemini-2.5-flash-preview-tts",
        contents=STYLE + text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon"))),
        ),
    )
    pcm = r.candidates[0].content.parts[0].inline_data.data
    raw = path.with_suffix(".pcm")
    raw.write_bytes(pcm)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar",
                    "24000", "-ac", "1", "-i", str(raw), str(path)], check=True)
    raw.unlink()
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    client = genai.Client(api_key=os.environ["SENTINEL_GEMINI_KEY"])
    durations, starts, t = [], [], 0.0
    for i, text in enumerate(SEGMENTS, 1):
        p = OUT / f"seg{i}.wav"
        d = synth(client, text, p)
        durations.append(round(d, 3))
        starts.append(round(t, 3))
        t += d + PAD
        print(f"seg{i}: {d:.2f}s (scene starts at {starts[-1]:.2f}s)")
    total = round(t, 3)
    (OUT / "timings.json").write_text(json.dumps(
        {"pad": PAD, "durations": durations, "starts": starts, "total": total}, indent=1))
    print(f"total timeline: {total:.1f}s", "(OK, under 180s)" if total < 180 else "(!! OVER 3:00)")
    sys.exit(0 if total < 180 else 1)
