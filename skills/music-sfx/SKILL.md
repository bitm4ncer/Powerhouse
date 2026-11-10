---
name: music-sfx
description: Create and mix music, sound effects, and voiceover for videos, apps, and games. Use for "soundtrack", "background music", "SFX", "voiceover", "mix", "master", "loudness", "trailer sound", or when a video needs audio that fits its tone. Routes between local generation, voice cloning, and library assets, then delivers at the right loudness.
---

# Music, SFX, voiceover

Pick the tool by what the piece needs, generate options instead of one take, and
deliver at a known loudness. Keep the license of every asset.

## Choose the source

| Need | First choice | Notes |
| --- | --- | --- |
| Original instrumental, no vocals | ACE-Step (local) | Free, offline; describe mood, tempo, key, instrumentation |
| Voiceover, many languages | ElevenLabs | Check the voice license and the plan's commercial terms |
| Cloned voice | Voicebox (local) | Only with the speaker's consent; keep the reference sample private |
| Instant SFX | Library (Kenney, CC0) | Prefer existing, cleared assets over generating noise |
| Music bed with edit points | Library (CC BY) | Keep the attribution next to the file |

Never use a copyrighted track because it "fits". If the rights are unclear, it
does not ship.

## Brief before generating

Write five lines and confirm them with the user:

1. Purpose (launch video, app background, game loop, podcast intro).
2. Mood and references ("warm, analog, 100 BPM, like X but not copying X").
3. Length and structure (hook, build, drop, outro).
4. Instrumentation and what must stay out (no drums under dialogue).
5. Delivery: format, sample rate, loudness target, mono/stereo.

Generate two or three options, not one. Audition them against the picture or the
UI, not in isolation.

## Edit

- Trim to the edit, do not stretch a track that does not fit.
- Fade in/out 0.2–0.5 s for beds; longer for cinematic.
- Duck music under voice with a sidechain or a volume automation curve
  (-8 to -12 dB under speech).
- Cut SFX on the frame, not near it; align transients with the visual hit.

## Mix and master

Targets (integrated LUFS, true peak ≤ -1 dBTP):

| Delivery | Loudness |
| --- | --- |
| Social / streaming video | -14 LUFS |
| Podcast / spoken | -16 LUFS |
| Broadcast | -23 LUFS (EBU R128) |
| Game / app bed | -18 to -20 LUFS, leave headroom |

ffmpeg two-pass loudness normalization:

```sh
ffmpeg -i in.wav -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null -
# then apply the measured values
ffmpeg -i in.wav -af loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=<I>:measured_TP=<TP>:measured_LRA=<LRA>:measured_thresh=<thresh>:offset=<offset>:linear=true -ar 48000 out.wav
```

Do not normalize each stem independently; mix first, then master the mix.

## Deliver

- Master: WAV, 48 kHz, 24-bit.
- Preview/web: MP3 320 kbps or AAC 256 kbps.
- Name files by role and version: `launch-bed_v3_-14lufs.wav`.
- Keep the project file, the stems, and the license note together.

## Check

- Listen on phone speakers and headphones, not only studio monitors.
- Check the first 2 seconds and the last 2 seconds; that is where mistakes live.
- Confirm dialogue intelligibility at -18 dB monitoring.
- No clipping, no DC offset, no abrupt cut at the end.

## Licensing

Record source, author, license, and URL for every asset in the project notes.
CC BY requires attribution in the credits; CC0 does not, but record it anyway.
