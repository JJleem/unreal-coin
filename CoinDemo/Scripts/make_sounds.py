"""
Synthesizes the game's sound effects as 16-bit mono WAV files (no external assets needed).

  coin.wav    bright two-note chime when a coin is collected
  clear.wav   rising arpeggio when a stage is cleared
  smash.wav   noisy crunch when a barrier breaks
  record.wav  sparkle for a new best time

Output: ../SourceAssets/Sounds/*.wav, imported by import_sounds.py. Needs numpy:
  python make_sounds.py
"""

import os
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "SourceAssets", "Sounds"))
RATE = 44100


def tone(freq, duration, decay, harmonics=((1, 1.0), (2, 0.35), (3, 0.15), (4.2, 0.08))):
    """Bell-like tone: a few harmonics with an exponential decay and a short attack."""
    t = np.arange(int(RATE * duration)) / RATE
    wave_ = sum(amp * np.sin(2 * np.pi * freq * mult * t) for mult, amp in harmonics)
    envelope = np.exp(-t * decay) * np.minimum(1.0, t / 0.004)
    return wave_ * envelope


def place(buffer, sound, start):
    i = int(RATE * start)
    end = min(len(buffer), i + len(sound))
    buffer[i:end] += sound[:end - i]


def coin():
    out = np.zeros(int(RATE * 0.6))
    place(out, tone(987.77, 0.15, 30), 0.0)      # B5
    place(out, tone(1318.51, 0.55, 9), 0.07)     # E6
    return out


def clear():
    out = np.zeros(int(RATE * 1.6))
    for i, freq in enumerate((523.25, 659.25, 783.99, 1046.50)):  # C5 E5 G5 C6
        place(out, tone(freq, 1.2 - i * 0.1, 4 + i), i * 0.11)
    place(out, 0.5 * tone(1567.98, 0.9, 5), 0.44)  # G6 sparkle on top
    return out


def smash():
    rng = np.random.default_rng(7)
    t = np.arange(int(RATE * 0.5)) / RATE
    noise = rng.standard_normal(len(t))
    # low thump plus a burst of filtered noise
    thump = np.sin(2 * np.pi * 70 * t * np.exp(-t * 6)) * np.exp(-t * 14)
    crunch = np.convolve(noise, np.ones(6) / 6, mode="same") * np.exp(-t * 11)
    return thump * 0.9 + crunch * 0.7


def record():
    out = np.zeros(int(RATE * 1.2))
    for i, freq in enumerate((1318.51, 1567.98, 1975.53, 2637.02, 3135.96)):
        place(out, 0.6 * tone(freq, 0.6, 8), i * 0.07)
    return out


def write(name, samples):
    samples = samples / max(1e-9, np.abs(samples).max()) * 0.8
    with wave.open(os.path.join(OUT_DIR, f"{name}.wav"), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes((samples * 32767).astype("<i2").tobytes())
    print(f"{name}.wav  {len(samples) / RATE:.2f}s")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, make in (("coin", coin), ("clear", clear), ("smash", smash), ("record", record)):
        write(name, make())


main()
