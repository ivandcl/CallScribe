import struct
import wave
from pathlib import Path

from pydub import AudioSegment

import config


def _read_wav_samples(wav_path: Path) -> tuple[list[int], int]:
    """Lee un WAV mono y retorna (samples, framerate).
    Si el archivo no existe, tiene 0 bytes o 0 frames, retorna lista vacia.
    """
    if not wav_path.exists() or wav_path.stat().st_size < 44:
        return [], config.SAMPLE_RATE

    try:
        with wave.open(str(wav_path), "rb") as wf:
            rate = wf.getframerate()
            n_frames = wf.getnframes()
            if n_frames == 0:
                return [], rate
            raw = wf.readframes(n_frames)
            samples = list(struct.unpack(f"<{n_frames}h", raw))
            return samples, rate
    except Exception:
        return [], config.SAMPLE_RATE


def mix_to_stereo(loopback_wav: Path, mic_wav: Path, output_wav: Path):
    """Mezcla dos archivos WAV mono en un solo WAV stereo.
    Canal izquierdo = loopback (sistema), canal derecho = microfono.
    Si uno de los archivos esta vacio, rellena con silencio.
    """
    samples_l, rate_l = _read_wav_samples(loopback_wav)
    samples_r, rate_r = _read_wav_samples(mic_wav)
    rate = rate_l if samples_l else rate_r

    if not samples_l and not samples_r:
        raise ValueError("Ambos archivos WAV estan vacios")

    n_frames = max(len(samples_l), len(samples_r))

    # Pad shorter channel with silence
    if len(samples_l) < n_frames:
        samples_l.extend([0] * (n_frames - len(samples_l)))
    if len(samples_r) < n_frames:
        samples_r.extend([0] * (n_frames - len(samples_r)))

    # Interleave: L, R, L, R, ...
    stereo = []
    for l_sample, r_sample in zip(samples_l, samples_r):
        stereo.append(l_sample)
        stereo.append(r_sample)

    with wave.open(str(output_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(struct.pack(f"<{len(stereo)}h", *stereo))


def wav_to_mp3(wav_path: Path, mp3_path: Path):
    """Convierte un archivo WAV a MP3 usando pydub/ffmpeg."""
    audio = AudioSegment.from_wav(str(wav_path))
    audio.export(str(mp3_path), format="mp3", bitrate="128k")
