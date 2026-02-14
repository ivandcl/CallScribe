import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_model_cache = {}


class Transcriber:
    def __init__(self, model_size: str = "medium", language: str = "es"):
        self.model_size = model_size
        self.language = language
        self._model = None

    def _load_model(self):
        if self.model_size in _model_cache:
            self._model = _model_cache[self.model_size]
            return

        from faster_whisper import WhisperModel

        # Detect best device
        device = "cpu"
        compute_type = "int8"
        try:
            import torch
            if torch.cuda.is_available():
                device = "cuda"
                compute_type = "float16"
        except ImportError:
            pass

        logger.info(
            "Cargando modelo Whisper '%s' en %s (compute_type=%s)...",
            self.model_size, device, compute_type,
        )
        self._model = WhisperModel(
            self.model_size,
            device=device,
            compute_type=compute_type,
        )
        _model_cache[self.model_size] = self._model
        logger.info("Modelo Whisper cargado")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None or self.model_size in _model_cache

    def transcribe(self, audio_path: str, output_dir: str) -> dict:
        if self._model is None:
            self._load_model()

        audio_path = Path(audio_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        stem = audio_path.stem
        txt_path = output_dir / f"{stem}.txt"
        json_path = output_dir / f"{stem}.json"

        logger.info("Transcribiendo %s...", audio_path.name)
        segments, info = self._model.transcribe(
            str(audio_path),
            language=self.language,
            beam_size=5,
            vad_filter=True,
        )

        all_segments = []
        full_text_parts = []

        for segment in segments:
            seg_data = {
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip(),
            }
            all_segments.append(seg_data)
            full_text_parts.append(segment.text.strip())

        full_text = "\n".join(full_text_parts)
        txt_path.write_text(full_text, encoding="utf-8")

        json_data = {
            "language": info.language,
            "duration": round(info.duration, 2),
            "segments": all_segments,
        }
        json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info("Transcripcion completada: %d segmentos", len(all_segments))

        return {
            "txt_path": str(txt_path),
            "json_path": str(json_path),
            "language": info.language,
            "duration_secs": round(info.duration),
        }
