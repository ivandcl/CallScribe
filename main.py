import logging
import sys
import threading
import webbrowser

import requests
import uvicorn

import config
from db.database import Database
from processing.summarizer import Summarizer
from processing.transcriber import Transcriber
from recorder.audio_capture import AudioRecorder
from server.app import create_app
from tray.tray_icon import TrayIcon

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("callscribe")


def find_available_port(start: int, end: int) -> int:
    import socket
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((config.HOST, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No se encontro un puerto disponible entre {start} y {end}")


def main():
    # Ensure data directories exist
    for d in [config.RECORDINGS_DIR, config.TRANSCRIPTS_DIR, config.SUMMARIES_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    # Find available port
    try:
        port = find_available_port(config.PORT, 8800)
    except RuntimeError as e:
        logger.error(str(e))
        sys.exit(1)

    if port != config.PORT:
        logger.info("Puerto %d en uso, usando %d", config.PORT, port)
    config.PORT = port

    # Initialize components
    db = Database(config.DB_PATH)
    recorder = AudioRecorder(str(config.RECORDINGS_DIR))
    transcriber = Transcriber(
        model_size=config.WHISPER_MODEL,
        language=config.WHISPER_LANGUAGE,
    )
    summarizer = Summarizer(
        provider=config.LLM_PROVIDER,
        api_key=config.ANTHROPIC_API_KEY,
        model=config.ANTHROPIC_MODEL,
        ollama_url=config.OLLAMA_URL,
        ollama_model=config.OLLAMA_MODEL,
    )

    # Load Whisper model in background
    def preload_whisper():
        try:
            logger.info("Pre-cargando modelo Whisper en background...")
            transcriber._load_model()
        except Exception as e:
            logger.warning("No se pudo pre-cargar Whisper: %s", e)

    threading.Thread(target=preload_whisper, daemon=True).start()

    # Create FastAPI app
    app = create_app(db, recorder, transcriber, summarizer)

    # Toggle recording callback for tray
    def toggle_recording():
        base = f"http://{config.HOST}:{config.PORT}/api"
        if recorder.is_recording():
            requests.post(f"{base}/recording/stop", timeout=10)
        else:
            requests.post(f"{base}/recording/start", json={}, timeout=10)
        tray.update_state(recorder.is_recording())

    # Quit callback
    server_should_stop = threading.Event()

    def quit_app():
        logger.info("Cerrando CallScribe...")
        if recorder.is_recording():
            try:
                recorder.stop()
            except Exception:
                pass
        recorder.terminate()
        server_should_stop.set()

    # Setup tray icon
    tray = TrayIcon(on_toggle_recording=toggle_recording, on_quit=quit_app)

    # Periodic tray state update
    def update_tray_state():
        import time
        while not server_should_stop.is_set():
            tray.update_state(recorder.is_recording())
            time.sleep(2)

    threading.Thread(target=update_tray_state, daemon=True).start()

    # Start server in background thread
    server_config = uvicorn.Config(
        app,
        host=config.HOST,
        port=config.PORT,
        log_level="warning",
    )
    server = uvicorn.Server(server_config)

    def run_server():
        server.run()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Open browser
    url = f"http://{config.HOST}:{config.PORT}"
    logger.info("CallScribe iniciado en %s", url)
    webbrowser.open(url)

    # Run tray icon on main thread (blocks until quit)
    try:
        tray.run()
    except KeyboardInterrupt:
        pass
    finally:
        quit_app()
        server.should_exit = True


if __name__ == "__main__":
    main()
