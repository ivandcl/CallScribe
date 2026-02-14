# CallScribe

Aplicacion de escritorio para Windows que graba llamadas (TeamViewer, Zoom, Meet, Discord o cualquier otra plataforma), las transcribe y genera actas de resumen automaticamente.

## Requisitos

- Windows 10/11 x64
- Python 3.11+
- [ffmpeg](https://ffmpeg.org/download.html) en el PATH
- [Ollama](https://ollama.com/) (opcional, para generacion de actas local)

## Instalacion

```bash
git clone https://github.com/ivandcl/CallScribe.git
cd CallScribe
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

O simplemente ejecutar `start.bat`, que crea el entorno virtual e instala dependencias automaticamente.

## Configuracion

Crear un archivo `.env` en la raiz del proyecto (opcional):

```
# LLM - usar Ollama (por defecto) o Anthropic
CALLSCRIBE_LLM_PROVIDER=ollama
CALLSCRIBE_OLLAMA_MODEL=minimax-m2:cloud

# O para usar Anthropic Claude:
# CALLSCRIBE_LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-...

# Whisper
CALLSCRIBE_WHISPER_MODEL=medium
CALLSCRIBE_LANGUAGE=es
```

### Modelos de Whisper disponibles

| Modelo | Tamanio | Velocidad | Calidad |
|--------|---------|-----------|---------|
| tiny   | ~75 MB  | Muy rapido | Baja |
| base   | ~140 MB | Rapido | Media-baja |
| small  | ~460 MB | Medio | Media |
| medium | ~1.5 GB | Lento | Alta |
| large  | ~3 GB   | Muy lento | Muy alta |

## Uso

```bash
python main.py
```

O hacer doble click en `start.bat`.

Al iniciar:
1. Se abre el navegador en `http://localhost:8787`
2. Aparece un icono en la bandeja del sistema (system tray)

### Grabar

- Desde la web: click en "Iniciar grabacion"
- Desde el tray: click izquierdo en el icono o menu > "Iniciar grabacion"

La grabacion captura simultaneamente el audio del sistema (loopback WASAPI) y el microfono.

### Procesar

Despues de detener una grabacion, desde la interfaz web:

- **Transcribir**: convierte el audio a texto con Whisper
- **Generar acta**: genera un resumen estructurado con el LLM configurado
- **Procesar todo**: ejecuta ambos pasos en secuencia

### Acta generada

El acta sigue un formato Markdown estructurado:

- Participantes
- Resumen general
- Temas tratados
- Decisiones tomadas
- Tareas pendientes (action items)
- Notas adicionales

## Arquitectura

```
call-recorder/
  main.py              # Punto de entrada
  config.py            # Configuracion global
  start.bat            # Launcher Windows
  recorder/            # Captura de audio WASAPI
  processing/          # Whisper + LLM
  server/              # FastAPI (localhost:8787)
  static/              # Frontend HTML/CSS/JS
  tray/                # Icono system tray
  db/                  # SQLite
  data/                # Grabaciones, transcripciones, actas (runtime)
```

## API REST

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | /api/status | Estado del sistema |
| GET | /api/devices | Dispositivos de audio |
| POST | /api/recording/start | Iniciar grabacion |
| POST | /api/recording/stop | Detener grabacion |
| GET | /api/recordings | Listar grabaciones |
| GET | /api/recordings/{id} | Detalle de grabacion |
| GET | /api/recordings/{id}/audio | Servir archivo de audio |
| PUT | /api/recordings/{id} | Actualizar titulo |
| DELETE | /api/recordings/{id} | Eliminar grabacion |
| POST | /api/recordings/{id}/transcribe | Transcribir |
| POST | /api/recordings/{id}/summarize | Generar acta |
| POST | /api/recordings/{id}/process | Transcribir + generar acta |

## Stack

- **Audio**: pyaudiowpatch (WASAPI loopback), pydub + ffmpeg
- **Transcripcion**: faster-whisper (CTranslate2)
- **LLM**: Ollama (local) o Anthropic Claude (API)
- **Backend**: FastAPI + uvicorn
- **Frontend**: HTML/CSS/JS vanilla + marked.js
- **DB**: SQLite
- **Tray**: pystray + Pillow
