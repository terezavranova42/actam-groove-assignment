"""The lesson 04 drum kit.

Every function below comes from the lesson 04 notebook, except the two
helpers at the end (ring_track and save_wav).
"""
from math import exp
from random import random
import struct
import wave

SR = 48000


def vca(wave, signal):
    if len(wave) != len(signal):
        raise ValueError("The sound and control signal must have equal lengths.")
    return [x * gain for x, gain in zip(wave, signal)]


def noise(duration=0.05, amplitude=0.15, sample_rate=SR):
    n = round(duration * sample_rate)
    return [amplitude * (2 * random() - 1) for _ in range(n)]


def square_wave_f(f, sample_rate=SR, amplitude=0.15):
    phase = 0.0
    wave = []
    for frequency in f:
        if not 0 < frequency < sample_rate / 2:
            raise ValueError("Each frequency must be positive and below half the sample rate.")
        wave.append(-amplitude if phase < 0.5 else amplitude)
        phase = (phase + frequency / sample_rate) % 1
    return wave


def edge_fade(wave, attack=0.001, release=0.005, sample_rate=SR):
    n = len(wave)
    attack_samples = max(1, round(attack * sample_rate))
    release_samples = max(1, round(release * sample_rate))
    edge = [
        min(1.0, i / attack_samples, (n - 1 - i) / release_samples)
        for i in range(n)
    ]
    return vca(wave, edge)


def envelope_exp(duration=0.05, tau=0.012, sample_rate=SR):
    if tau <= 0:
        raise ValueError("tau must be positive.")
    n = round(duration * sample_rate)
    return [exp(-(i / sample_rate) / tau) for i in range(n)]


def closed_hat(duration=0.06, tau=0.010, amplitude=0.15, sample_rate=SR):
    source = noise(duration, amplitude=amplitude, sample_rate=sample_rate)
    shape = envelope_exp(duration, tau=tau, sample_rate=sample_rate)
    return edge_fade(vca(source, shape), sample_rate=sample_rate)


def open_hat(duration=0.30, tau=0.070, amplitude=0.15, sample_rate=SR):
    source = noise(duration, amplitude=amplitude, sample_rate=sample_rate)
    shape = envelope_exp(duration, tau=tau, sample_rate=sample_rate)
    return edge_fade(vca(source, shape), sample_rate=sample_rate)


def crash(duration=1.0, tau=0.25, amplitude=0.15, sample_rate=SR):
    source = noise(duration, amplitude=amplitude, sample_rate=sample_rate)
    shape = envelope_exp(duration, tau=tau, sample_rate=sample_rate)
    return edge_fade(vca(source, shape), sample_rate=sample_rate)
    

def kick_raw(
    duration=0.25, start_hz=180, end_hz=45,
    pitch_tau=0.025, amp_tau=0.060,
    amplitude=0.20, sample_rate=SR,
):
    pitch_shape = envelope_exp(duration, tau=pitch_tau, sample_rate=sample_rate)
    pitch = [end_hz + (start_hz - end_hz) * value for value in pitch_shape]
    body = square_wave_f(pitch, sample_rate=sample_rate, amplitude=amplitude)
    shape = envelope_exp(duration, tau=amp_tau, sample_rate=sample_rate)
    return vca(body, shape)


def kick(
    duration=0.25, start_hz=180, end_hz=45,
    pitch_tau=0.025, amp_tau=0.060,
    amplitude=0.20, sample_rate=SR,
):
    wave = kick_raw(
        duration=duration, start_hz=start_hz, end_hz=end_hz,
        pitch_tau=pitch_tau, amp_tau=amp_tau,
        amplitude=amplitude, sample_rate=sample_rate,
    )
    return edge_fade(wave, sample_rate=sample_rate)


def mix(a, b, ga=1.0, gb=1.0):
    if len(a) != len(b):
        raise ValueError("Pad the shorter sound with silence before mixing.")
    return [ga * x + gb * y for x, y in zip(a, b)]


def snare(
    duration=0.20, amplitude=0.15, noise_gain=0.5,
    sample_rate=SR,
):
    pitch = [
        180 + 120 * value
        for value in envelope_exp(duration, tau=0.010, sample_rate=sample_rate)
    ]
    body = vca(
        square_wave_f(pitch, amplitude=amplitude, sample_rate=sample_rate),
        envelope_exp(duration, tau=0.025, sample_rate=sample_rate),
    )
    wires = vca(
        noise(duration, amplitude=amplitude, sample_rate=sample_rate),
        envelope_exp(duration, tau=0.055, sample_rate=sample_rate),
    )
    return edge_fade(
        mix(body, wires, ga=1.0, gb=noise_gain),
        sample_rate=sample_rate,
    )


def fit(wave, n_samples):
    padding = max(0, n_samples - len(wave))
    return wave[:n_samples] + [0] * padding


def read_pattern(pattern):
    steps = []
    for symbol in pattern:
        if symbol == "x":
            steps.append(1)
        elif symbol == ".":
            steps.append(0)
        else:
            raise ValueError("Use only x for a hit and . for a rest.")
    return steps


def render_pattern(pattern, instrument, step_s, sample_rate=SR):
    n = round(step_s * sample_rate)

    steps = read_pattern(pattern)
    slots = []
    for hit in steps:
        if hit == 1:
            wave = instrument(sample_rate=sample_rate)
        else:
            wave = []
        slots.append(fit(wave, n))
    return sum(slots, [])


def mix_tracks(waves):
    if len(waves) == 0:
        return []
    longest = max([len(wave) for wave in waves])
    result = [0] * longest
    for wave in waves:
        result = mix(result, fit(wave, longest))
    return result


def render_track(track, sample_rate=SR):
    pattern, instrument, step_s = track
    return render_pattern(pattern, instrument, step_s, sample_rate=sample_rate)


def render_tracks(tracks, sample_rate=SR):
    waves = [render_track(track, sample_rate=sample_rate) for track in tracks]
    return mix_tracks(waves)


def render_timed_pattern(pattern, instrument, step_lengths, sample_rate=SR):
    steps = read_pattern(pattern)
    if len(steps) != len(step_lengths):
        raise ValueError("Give each pattern step one slot length.")
    slots = []
    for hit, n in zip(steps, step_lengths):
        if hit == 1:
            wave = instrument(sample_rate=sample_rate)
        else:
            wave = []
        slots.append(fit(wave, n))
    return sum(slots, [])


def render_timed_tracks(tracks, sample_rate=SR):
    waves = []
    for pattern, instrument, step_lengths in tracks:
        wave = render_timed_pattern(
            pattern, instrument, step_lengths, sample_rate=sample_rate
        )
        waves.append(wave)
    return mix_tracks(waves)


# --- Not in the notebook -------------------------------------------------


def ring_track(pattern, instrument, step_samples):
    """Turn a pattern into a timed track whose hits ring until the next hit.

    render_pattern cuts every hit to one step. Here each slot lasts until the
    next "x" of the same track, so long sounds keep their tails.
    Use the result with render_timed_tracks.
    """
    hits = ""
    lengths = []
    for symbol in pattern:
        if symbol == "x":
            hits = hits + "x"
            lengths.append(step_samples)
        elif symbol == ".":
            if len(lengths) == 0:
                hits = "."
                lengths.append(0)
            lengths[-1] = lengths[-1] + step_samples
        else:
            raise ValueError("Use only x for a hit and . for a rest.")
    return (hits, instrument, lengths)


def save_wav(path, wave_samples, sample_rate=SR):
    """Write a mono 16-bit WAV. Refuses to clip instead of normalising."""
    peak = max(abs(x) for x in wave_samples)
    if peak > 1:
        raise ValueError(f"Peak {peak:.2f} exceeds 1: lower the gains.")
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(struct.pack(
            "<" + "h" * len(wave_samples),
            *(round(x * 32767) for x in wave_samples),
        ))
