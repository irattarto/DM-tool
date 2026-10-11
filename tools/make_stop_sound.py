"""Generate data/sounds/recording_stopped.wav: two short soft tones (880 Hz then 660 Hz)."""
import math
import struct
import wave
from pathlib import Path

RATE = 44100


def tone(freq: float, seconds: float, volume: float = 0.65):
    n = int(RATE * seconds)
    fade = int(RATE * 0.01)
    for i in range(n):
        env = min(1.0, i / fade, (n - i) / fade)  # 10 ms fade in/out: no clicks
        yield int(32767 * volume * env * math.sin(2 * math.pi * freq * i / RATE))


def main():
    out = Path(__file__).resolve().parent.parent / "data" / "sounds" / "recording_stopped.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    samples = list(tone(880, 0.14)) + [0] * int(RATE * 0.05) + list(tone(660, 0.18))
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    print(out, out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
