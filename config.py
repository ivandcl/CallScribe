import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Rutas
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RECORDINGS_DIR = DATA_DIR / "recordings"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
SUMMARIES_DIR = DATA_DIR / "summaries"
DB_PATH = DATA_DIR / "callscribe.db"

# Servidor
HOST = "127.0.0.1"
PORT = 8787

# Audio
SAMPLE_RATE = 16000
CHANNELS = 1
AUDIO_FORMAT = "mp3"

# Whisper
WHISPER_MODEL = os.getenv("CALLSCRIBE_WHISPER_MODEL", "medium")
WHISPER_LANGUAGE = os.getenv("CALLSCRIBE_LANGUAGE", "es")
WHISPER_DEVICE = "auto"  # se autodetecta: "cuda" si hay GPU, sino "cpu"

# LLM
LLM_PROVIDER = os.getenv("CALLSCRIBE_LLM_PROVIDER", "ollama")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"
OLLAMA_MODEL = os.getenv("CALLSCRIBE_OLLAMA_MODEL", "minimax-m2:cloud")
OLLAMA_URL = os.getenv("CALLSCRIBE_OLLAMA_URL", "http://localhost:11434")

# Dispositivos de audio (None = autodetectar)
LOOPBACK_DEVICE_INDEX = None
MIC_DEVICE_INDEX = None
