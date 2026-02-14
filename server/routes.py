import logging
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import config
from db.database import Database
from processing.summarizer import Summarizer
from processing.transcriber import Transcriber
from recorder.audio_capture import AudioRecorder

logger = logging.getLogger(__name__)


class StartRecordingRequest(BaseModel):
    title: str | None = None


class UpdateRecordingRequest(BaseModel):
    title: str


def create_router(db: Database, recorder: AudioRecorder,
                   transcriber: Transcriber, summarizer: Summarizer) -> APIRouter:
    router = APIRouter()

    # -- Status --

    @router.get("/status")
    def get_status():
        return {
            "is_recording": recorder.is_recording(),
            "current_recording_id": recorder.current_recording_id,
            "whisper_model_loaded": transcriber.is_loaded,
        }

    # -- Devices --

    @router.get("/devices")
    def list_devices():
        devices = recorder.list_devices()
        loopback = [d for d in devices if d.get("isLoopback")]
        inputs = [d for d in devices if d["maxInputChannels"] > 0 and not d.get("isLoopback")]
        return {"loopback": loopback, "input": inputs}

    # -- Recording control --

    @router.post("/recording/start")
    def start_recording(body: StartRecordingRequest = StartRecordingRequest()):
        if recorder.is_recording():
            raise HTTPException(400, "Ya hay una grabacion en curso")

        # Check disk space
        free = shutil.disk_usage(config.DATA_DIR).free
        if free < 500 * 1024 * 1024:
            raise HTTPException(507, "Espacio en disco insuficiente (menos de 500MB)")

        try:
            recording_id = recorder.start(
                loopback_device_index=config.LOOPBACK_DEVICE_INDEX,
                mic_device_index=config.MIC_DEVICE_INDEX,
            )
        except RuntimeError as e:
            raise HTTPException(500, str(e))

        now = datetime.now(timezone.utc).isoformat()
        title = body.title or f"Grabacion {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        rec = db.insert_recording(recording_id, title, now)
        return {"id": rec["id"], "status": rec["status"]}

    @router.post("/recording/stop")
    def stop_recording():
        if not recorder.is_recording():
            raise HTTPException(400, "No hay grabacion en curso")

        try:
            result = recorder.stop()
        except RuntimeError as e:
            raise HTTPException(500, str(e))

        rec = db.update_recording(
            result["id"],
            status="stopped",
            ended_at=datetime.now(timezone.utc).isoformat(),
            duration_secs=result["duration_secs"],
            audio_path=result["path"],
        )
        return {"id": rec["id"], "status": rec["status"], "duration_secs": rec["duration_secs"]}

    # -- Recordings CRUD --

    @router.get("/recordings")
    def list_recordings():
        recordings = db.list_recordings()
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "started_at": r["started_at"],
                "duration_secs": r["duration_secs"],
                "status": r["status"],
            }
            for r in recordings
        ]

    @router.get("/recordings/{recording_id}")
    def get_recording(recording_id: str):
        rec = db.get_recording(recording_id)
        if not rec:
            raise HTTPException(404, "Grabacion no encontrada")

        result = {
            "id": rec["id"],
            "title": rec["title"],
            "started_at": rec["started_at"],
            "ended_at": rec["ended_at"],
            "duration_secs": rec["duration_secs"],
            "status": rec["status"],
            "error_message": rec["error_message"],
            "audio_url": f"/api/recordings/{rec['id']}/audio" if rec["audio_path"] else None,
            "transcript_text": None,
            "summary_markdown": None,
        }

        if rec["transcript_path"]:
            txt_path = config.BASE_DIR / rec["transcript_path"]
            if txt_path.exists():
                result["transcript_text"] = txt_path.read_text(encoding="utf-8")

        if rec["summary_path"]:
            md_path = config.BASE_DIR / rec["summary_path"]
            if md_path.exists():
                result["summary_markdown"] = md_path.read_text(encoding="utf-8")

        return result

    @router.get("/recordings/{recording_id}/audio")
    def get_audio(recording_id: str):
        rec = db.get_recording(recording_id)
        if not rec or not rec["audio_path"]:
            raise HTTPException(404, "Audio no encontrado")

        audio_path = config.BASE_DIR / rec["audio_path"]
        if not audio_path.exists():
            raise HTTPException(404, "Archivo de audio no encontrado")

        return FileResponse(str(audio_path), media_type="audio/mpeg")

    @router.put("/recordings/{recording_id}")
    def update_recording(recording_id: str, body: UpdateRecordingRequest):
        rec = db.get_recording(recording_id)
        if not rec:
            raise HTTPException(404, "Grabacion no encontrada")
        updated = db.update_recording(recording_id, title=body.title)
        return updated

    @router.delete("/recordings/{recording_id}")
    def delete_recording(recording_id: str):
        rec = db.get_recording(recording_id)
        if not rec:
            raise HTTPException(404, "Grabacion no encontrada")

        # Delete files
        for path_field in ["audio_path", "transcript_path", "summary_path"]:
            if rec[path_field]:
                file_path = config.BASE_DIR / rec[path_field]
                if file_path.exists():
                    file_path.unlink()
                # Also delete companion json for transcripts
                if path_field == "transcript_path":
                    json_path = file_path.with_suffix(".json")
                    if json_path.exists():
                        json_path.unlink()

        db.delete_recording(recording_id)
        return {"deleted": True}

    # -- Processing --

    @router.post("/recordings/{recording_id}/transcribe")
    def transcribe_recording(recording_id: str):
        rec = db.get_recording(recording_id)
        if not rec:
            raise HTTPException(404, "Grabacion no encontrada")
        if not rec["audio_path"]:
            raise HTTPException(400, "No hay archivo de audio")
        if rec["status"] in ("recording", "transcribing", "summarizing"):
            raise HTTPException(400, f"Grabacion en estado '{rec['status']}', no se puede procesar")

        db.update_recording(recording_id, status="transcribing")

        def _do_transcribe():
            try:
                audio_path = config.BASE_DIR / rec["audio_path"]
                result = transcriber.transcribe(str(audio_path), str(config.TRANSCRIPTS_DIR))
                rel_path = str(Path(result["txt_path"]).relative_to(config.BASE_DIR))
                db.update_recording(recording_id, status="transcribed", transcript_path=rel_path)
            except Exception as e:
                logger.error("Error transcribiendo %s: %s", recording_id, e)
                db.update_recording(recording_id, status="error", error_message=str(e))

        threading.Thread(target=_do_transcribe, daemon=True).start()
        return {"status": "transcribing"}

    @router.post("/recordings/{recording_id}/summarize")
    def summarize_recording(recording_id: str):
        rec = db.get_recording(recording_id)
        if not rec:
            raise HTTPException(404, "Grabacion no encontrada")
        if not rec["transcript_path"]:
            raise HTTPException(400, "No hay transcripcion disponible")
        if rec["status"] in ("recording", "transcribing", "summarizing"):
            raise HTTPException(400, f"Grabacion en estado '{rec['status']}', no se puede procesar")

        db.update_recording(recording_id, status="summarizing")

        def _do_summarize():
            try:
                txt_path = config.BASE_DIR / rec["transcript_path"]
                recording_date = rec["started_at"][:10] if rec["started_at"] else "Fecha desconocida"
                result_path = summarizer.summarize(str(txt_path), str(config.SUMMARIES_DIR), recording_date)
                rel_path = str(Path(result_path).relative_to(config.BASE_DIR))
                db.update_recording(recording_id, status="completed", summary_path=rel_path)
            except Exception as e:
                logger.error("Error generando acta %s: %s", recording_id, e)
                db.update_recording(recording_id, status="error", error_message=str(e))

        threading.Thread(target=_do_summarize, daemon=True).start()
        return {"status": "summarizing"}

    @router.post("/recordings/{recording_id}/process")
    def process_recording(recording_id: str):
        rec = db.get_recording(recording_id)
        if not rec:
            raise HTTPException(404, "Grabacion no encontrada")
        if not rec["audio_path"]:
            raise HTTPException(400, "No hay archivo de audio")
        if rec["status"] in ("recording", "transcribing", "summarizing"):
            raise HTTPException(400, f"Grabacion en estado '{rec['status']}', no se puede procesar")

        db.update_recording(recording_id, status="transcribing")

        def _do_process():
            try:
                audio_path = config.BASE_DIR / rec["audio_path"]
                t_result = transcriber.transcribe(str(audio_path), str(config.TRANSCRIPTS_DIR))
                rel_transcript = str(Path(t_result["txt_path"]).relative_to(config.BASE_DIR))
                db.update_recording(recording_id, status="summarizing", transcript_path=rel_transcript)

                recording_date = rec["started_at"][:10] if rec["started_at"] else "Fecha desconocida"
                s_result = summarizer.summarize(t_result["txt_path"], str(config.SUMMARIES_DIR), recording_date)
                rel_summary = str(Path(s_result).relative_to(config.BASE_DIR))
                db.update_recording(recording_id, status="completed", summary_path=rel_summary)
            except Exception as e:
                logger.error("Error procesando %s: %s", recording_id, e)
                db.update_recording(recording_id, status="error", error_message=str(e))

        threading.Thread(target=_do_process, daemon=True).start()
        return {"status": "processing"}

    return router
