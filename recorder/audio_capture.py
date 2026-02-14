import logging
import threading
import time
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path

import pyaudiowpatch as pyaudio

import config
from recorder.mixer import mix_to_stereo, wav_to_mp3

logger = logging.getLogger(__name__)

CHUNK_DURATION_MS = 30
FLUSH_INTERVAL_SECS = 5


class AudioRecorder:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._pa: pyaudio.PyAudio | None = None
        self._recording = False
        self._recording_id: str | None = None
        self._started_at: str | None = None
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._loopback_wav: Path | None = None
        self._mic_wav: Path | None = None
        self._loopback_wf: wave.Wave_write | None = None
        self._mic_wf: wave.Wave_write | None = None

    def _get_pa(self) -> pyaudio.PyAudio:
        if self._pa is None:
            self._pa = pyaudio.PyAudio()
        return self._pa

    def list_devices(self) -> list[dict]:
        pa = self._get_pa()
        devices = []
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            devices.append({
                "index": i,
                "name": info["name"],
                "maxInputChannels": info["maxInputChannels"],
                "maxOutputChannels": info["maxOutputChannels"],
                "defaultSampleRate": info["defaultSampleRate"],
                "isLoopback": info.get("isLoopbackDevice", False),
            })
        return devices

    def _find_loopback_device(self) -> dict | None:
        pa = self._get_pa()
        try:
            wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError:
            logger.warning("WASAPI no disponible")
            return None

        default_output_idx = wasapi_info["defaultOutputDevice"]
        default_output = pa.get_device_info_by_index(default_output_idx)

        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if (
                info.get("isLoopbackDevice", False)
                and info["name"].startswith(default_output["name"].split(" (")[0])
            ):
                return info

        # Fallback: any loopback device
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("isLoopbackDevice", False):
                return info

        return None

    def _find_mic_device(self) -> dict | None:
        pa = self._get_pa()
        try:
            wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_input_idx = wasapi_info["defaultInputDevice"]
            if default_input_idx >= 0:
                return pa.get_device_info_by_index(default_input_idx)
        except OSError:
            pass

        default_idx = pa.get_default_input_device_info()
        if default_idx:
            return default_idx
        return None

    def _record_stream(self, device_info: dict, wav_path: Path, is_loopback: bool):
        pa = self._get_pa()
        sample_rate = int(device_info["defaultSampleRate"])

        # Para loopback, usar canales de salida; para mic, canales de entrada
        if is_loopback:
            channels = int(device_info.get("maxInputChannels") or device_info.get("maxOutputChannels") or 2)
        else:
            channels = int(device_info["maxInputChannels"])
        channels = max(1, channels)

        chunk_size = max(1, int(sample_rate * CHUNK_DURATION_MS / 1000))
        target_rate = config.SAMPLE_RATE

        wf = wave.open(str(wav_path), "wb")
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(target_rate)

        if is_loopback:
            self._loopback_wf = wf
        else:
            self._mic_wf = wf

        stream = None
        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=device_info["index"],
                frames_per_buffer=chunk_size,
            )
        except Exception as e:
            logger.error("No se pudo abrir stream para %s: %s", device_info["name"], e)
            wf.close()
            return

        frames_since_flush = 0
        flush_frames = int(target_rate * FLUSH_INTERVAL_SECS)

        try:
            while self._recording:
                try:
                    data = stream.read(chunk_size, exception_on_overflow=False)
                except Exception:
                    continue

                # Convert to mono if multichannel
                if channels > 1:
                    import struct
                    samples = struct.unpack(f"<{len(data) // 2}h", data)
                    mono = []
                    for i in range(0, len(samples), channels):
                        frame_samples = samples[i : i + channels]
                        mono.append(int(sum(frame_samples) / channels))
                    data = struct.pack(f"<{len(mono)}h", *mono)

                # Resample if needed
                if sample_rate != target_rate:
                    import struct
                    samples = struct.unpack(f"<{len(data) // 2}h", data)
                    ratio = target_rate / sample_rate
                    new_len = int(len(samples) * ratio)
                    if new_len > 0:
                        resampled = []
                        for i in range(new_len):
                            src_idx = min(int(i / ratio), len(samples) - 1)
                            resampled.append(samples[src_idx])
                        data = struct.pack(f"<{len(resampled)}h", *resampled)

                wf.writeframes(data)
                frames_since_flush += len(data) // 2
                if frames_since_flush >= flush_frames:
                    wf._ensure_header_written(0)  # noqa: SLF001
                    frames_since_flush = 0
        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            wf.close()

    def start(self, loopback_device_index: int | None = None,
              mic_device_index: int | None = None) -> str:
        with self._lock:
            if self._recording:
                raise RuntimeError("Ya hay una grabacion en curso")

            self._recording_id = str(uuid.uuid4())
            self._started_at = datetime.now(timezone.utc).isoformat()
            self._recording = True

            self._loopback_wav = self.output_dir / f"{self._recording_id}_loopback.wav"
            self._mic_wav = self.output_dir / f"{self._recording_id}_mic.wav"

            pa = self._get_pa()
            loopback_info = None
            mic_info = None

            if loopback_device_index is not None:
                loopback_info = pa.get_device_info_by_index(loopback_device_index)
            else:
                loopback_info = self._find_loopback_device()

            if mic_device_index is not None:
                mic_info = pa.get_device_info_by_index(mic_device_index)
            else:
                mic_info = self._find_mic_device()

            self._threads = []

            if loopback_info:
                logger.info("Loopback: %s", loopback_info["name"])
                t = threading.Thread(
                    target=self._record_stream,
                    args=(loopback_info, self._loopback_wav, True),
                    daemon=True,
                )
                t.start()
                self._threads.append(t)
            else:
                logger.warning("No se encontro dispositivo loopback, grabando silencio en ese canal")
                self._create_silent_wav(self._loopback_wav)

            if mic_info:
                logger.info("Microfono: %s", mic_info["name"])
                t = threading.Thread(
                    target=self._record_stream,
                    args=(mic_info, self._mic_wav, False),
                    daemon=True,
                )
                t.start()
                self._threads.append(t)
            else:
                logger.warning("No se encontro microfono, grabando silencio en ese canal")
                self._create_silent_wav(self._mic_wav)

            if not loopback_info and not mic_info:
                self._recording = False
                raise RuntimeError("No se encontro ningun dispositivo de audio")

            return self._recording_id

    def _create_silent_wav(self, path: Path):
        wf = wave.open(str(path), "wb")
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(config.SAMPLE_RATE)
        wf.close()

    def stop(self) -> dict:
        with self._lock:
            if not self._recording:
                raise RuntimeError("No hay grabacion en curso")

            self._recording = False
            recording_id = self._recording_id
            started_at = self._started_at

        # Wait for threads to finish
        for t in self._threads:
            t.join(timeout=5)
        self._threads = []

        # Force close any lingering WAV file handles
        for wf_ref in [self._loopback_wf, self._mic_wf]:
            if wf_ref is not None:
                try:
                    wf_ref.close()
                except Exception:
                    pass
        self._loopback_wf = None
        self._mic_wf = None

        # Mix to stereo WAV
        stereo_wav = self.output_dir / f"{recording_id}_stereo.wav"
        try:
            mix_to_stereo(self._loopback_wav, self._mic_wav, stereo_wav)
        except Exception as e:
            logger.error("Error mezclando audio: %s", e)
            # Fallback: use whichever file exists and has content
            if self._loopback_wav.exists() and self._loopback_wav.stat().st_size > 44:
                stereo_wav = self._loopback_wav
            elif self._mic_wav.exists() and self._mic_wav.stat().st_size > 44:
                stereo_wav = self._mic_wav
            else:
                raise

        # Convert to MP3
        mp3_path = self.output_dir / f"{recording_id}.mp3"
        wav_to_mp3(stereo_wav, mp3_path)

        # Calculate duration
        try:
            with wave.open(str(stereo_wav), "rb") as wf:
                duration_secs = wf.getnframes() // wf.getframerate()
        except Exception:
            duration_secs = 0

        # Cleanup temp files
        for tmp in [self._loopback_wav, self._mic_wav]:
            if tmp and tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
        if stereo_wav.exists() and stereo_wav != mp3_path:
            try:
                stereo_wav.unlink()
            except OSError:
                pass

        self._recording_id = None
        self._started_at = None

        return {
            "id": recording_id,
            "path": str(mp3_path.relative_to(config.BASE_DIR)),
            "duration_secs": duration_secs,
            "started_at": started_at,
        }

    def is_recording(self) -> bool:
        return self._recording

    @property
    def current_recording_id(self) -> str | None:
        return self._recording_id

    def terminate(self):
        if self._recording:
            self._recording = False
            for t in self._threads:
                t.join(timeout=3)
        if self._pa:
            self._pa.terminate()
            self._pa = None
