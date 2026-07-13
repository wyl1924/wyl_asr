# Magic Box AI

[中文](README.md) · [English](README_EN.md)

Magic Box AI is a local speech-content processing service built on FunASR. It provides real-time WebSocket transcription, uploaded audio/video recognition, and supporting meeting, speaker, hotword, subtitle, and document features.

The project consists of a Python backend, a Vue 3 management UI, and optional .NET subtitle clients. The backend starts the WebSocket server and Flask REST API in the same process. The UI runs through Vite in development or is built as static files and served by the backend in the Docker image.

> Models, runtime data, uploaded media, and build outputs are not versioned. The service loads local model directories only, so prepare models before the first run.

## Scope

| Use case | Current implementation |
| --- | --- |
| Real-time transcription | Receives binary PCM audio through `ws://<host>:10095/` and returns online, offline, and 2pass recognition results. |
| File recognition | Uploads audio or video through REST APIs and processes conversion, recognition, segmentation, speaker handling, and result lookup as background tasks. |
| Meeting data | Stores meetings, audio, transcripts, translations, minutes versions, and related documents. |
| Speakers and hotwords | Provides APIs for speaker registration, identification, uploaded-segment correction, and hotword management. |
| Subtitles | The web UI configures subtitles; `VoiceRecognitionDisplay/` and `subtitle_display/` contain .NET client projects. |
| Local-service integration | Includes LLM/minutes task APIs, health checks, CORS, API-key, serial-port, and SSL configuration entry points. |

## Services and default ports

| Service | Default address | Code entry point |
| --- | --- | --- |
| WebSocket transcription | `ws://127.0.0.1:10095/` | `main.py`, `src/modules/network/websocket_service.py` |
| REST API | `http://127.0.0.1:8080/api` | `src/modules/database/database_api.py` |
| Health check | `http://127.0.0.1:8080/api/health` | `GET /api/health` |
| Web UI (development) | `http://127.0.0.1:5173` | `ui/` |

Default frontend endpoints are defined in `ui/src/config/api.ts`. When opened from a remote host, the UI uses the browser's current hostname while retaining ports `10095` and `8080`.

## Requirements

- Python 3.8 or newer (the Docker image uses Python 3.11).
- Node.js and npm for the web UI; Docker builds with Node.js 20.
- `ffmpeg` for uploaded-media conversion and audio extraction. If `tools/bin/ffmpeg` exists, `start.sh` uses it first.
- Optional: .NET 8 SDK for subtitle clients.
- Local FunASR models. Models are not downloaded when the service starts.

## Quick start

Run the following from the project root.

### 1. Create a Python environment and install dependencies

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Install web UI dependencies

```bash
cd ui
npm ci
cd ..
```

### 3. Download and organize base models

`organize_models.py` downloads base models through ModelScope and places them under `models/`. Model files are large and intentionally excluded from Git.

```bash
python organize_models.py
```

Before the first start, confirm that `models/SenseVoiceSmall` is available. If uploaded-file recognition uses built-in diarization, also provide its configured VAD, CAM++, and punctuation models.

### 4. Start the services

```bash
./start.sh start
```

By default this starts both the backend and the Vite UI. The script checks for `curl`, `nc`, Python, and frontend dependencies, then stores PIDs and logs in `.runtime/wyl-asr/`.

```bash
./start.sh status
./start.sh logs backend
./start.sh logs ui
./start.sh stop
```

Verify the REST API:

```bash
curl http://127.0.0.1:8080/api/health
```

### Recommended first start

`WYL_ASR_ENABLE_2PASS` defaults to `auto`. If its configured online Paraformer directory is unavailable, `start.sh` starts with `--disable_2pass`. To explicitly run offline/upload recognition only:

```bash
WYL_ASR_ENABLE_2PASS=0 ./start.sh start
```

To enable 2pass, point `WYL_ASR_ONLINE_ASR_MODEL` to a prepared, compatible local online model directory.

## Configuration

`start.sh` reads environment variables and automatically loads `.env.local` from the project root. Do not commit that file. Common settings are listed below.

| Variable | Default | Description |
| --- | --- | --- |
| `WYL_ASR_HOST` | `0.0.0.0` | WebSocket and API bind address. |
| `WYL_ASR_WS_PORT` | `10095` | WebSocket port. |
| `WYL_ASR_API_PORT` | `8080` | REST API port. |
| `WYL_ASR_ENABLE_UI` | `1` | Set to `0` to skip the Vite UI. |
| `WYL_ASR_UI_HOST` / `WYL_ASR_UI_PORT` | `127.0.0.1` / `5173` | Vite development-server address. |
| `WYL_ASR_MODEL_DEVICE` | `auto` | `auto`, `cpu`, `cuda`, or `mps`; `auto` prefers CUDA, then MPS. |
| `WYL_ASR_NGPU` / `WYL_ASR_NCPU` | automatic / `4` | GPU and CPU values passed to FunASR. |
| `WYL_ASR_ASR_MODEL` | `models/SenseVoiceSmall` | Local offline ASR model directory for real-time transcription. |
| `WYL_ASR_UPLOAD_ASR_MODEL` | same as ASR model | Dedicated local ASR model directory for uploaded files. |
| `WYL_ASR_ENABLE_2PASS` | `auto` | `auto`, `1`, or `0`. |
| `WYL_ASR_ONLINE_ASR_MODEL` | Paraformer path from the script | Local online model directory for 2pass. |
| `WYL_ASR_ENABLE_SERIAL` | `0` | Set to `1` to enable serial input. |
| `WYL_ASR_SERIAL_PORT` / `WYL_ASR_SERIAL_BAUDRATE` | empty / `9600` | Serial device and baud rate. |
| `WYL_ASR_UPLOAD_ASR_LANGUAGE` | `zh` | Uploaded-file language: `auto`, `zh`, `en`, `yue`, `ja`, `ko`, or `nospeech`. |

Example: run the backend on CPU with 2pass and the web UI disabled.

```bash
WYL_ASR_MODEL_DEVICE=cpu \
WYL_ASR_ENABLE_2PASS=0 \
WYL_ASR_ENABLE_UI=0 \
./start.sh start
```

## API overview

All application APIs are under `/api`. For exact request and response schemas, refer to `src/modules/database/database_api.py` and the frontend calls.

| Group | Representative endpoints | Purpose |
| --- | --- | --- |
| Health | `GET /api/health` | Checks database, segmentation service, and task queues. |
| Upload recognition | `POST /api/upload/audio/recognize`, `GET /api/upload/audio/tasks/<task_id>` | Creates and retrieves uploaded audio/video recognition tasks. |
| Upload correction | `/api/upload/audio/tasks/<task_id>/corrections`, `/speakers/*` | Corrects speakers and segments in uploaded results. |
| Meetings | `/api/meetings`, `/api/meetings/<id>/speech-results` | Manages meetings, recordings, and transcript data. |
| Minutes and documents | `/api/meetings/<id>/minutes`, `/api/summary/tasks` | Stores minutes, versions, documents, and asynchronous minutes tasks. |
| Speakers | `/api/speakers/register`, `/api/speakers/list`, `/api/speakers/identify` | Registers, lists, and identifies speakers. |
| Hotwords | `/api/hotwords`, `/api/hotwords/import` | Manages and imports hotwords. |
| LLM | `/api/llm/config`, `/api/llm/chat`, `/api/llm/tasks` | Manages local LLM settings and tasks. |

The upload API accepts: `wav`, `mp3`, `flac`, `m4a`, `aac`, `ogg`, `webm`, `mp4`, `mov`, `mkv`, `avi`, `wmv`, `m4v`, `amr`, `opus`, and `wma`. Flask accepts requests up to 2 GB.

### API access control and CORS

- When `WYL_ASR_API_KEY` is set, every `/api/*` request must include `X-API-Key` or `Authorization: Bearer <key>`.
- `WYL_ASR_CORS_ORIGINS` is a comma-separated list of allowed origins. Its default is `*`; production deployments should use explicit frontend origins.
- Configure HTTPS/WSS through `--certfile` and `--keyfile` arguments to `main.py`.

## Docker

The Dockerfile builds the Vue UI and serves its static files from the REST application in the final Python image. The default image command disables 2pass and serial input and expects local models under `/app/models`.

```bash
docker build -t magic-box-ai .

docker run --rm \
  -p 10095:10095 \
  -p 8080:8080 \
  -v "$PWD/models:/app/models:ro" \
  -v "$PWD/data:/app/data" \
  magic-box-ai
```

Ensure that the mounted `models/` directory contains the model paths referenced by the Dockerfile before starting the container.

## Optional subtitle clients

- `VoiceRecognitionDisplay/VoiceRecognitionDisplay.sln`: cross-platform subtitle client solution with Desktop, Android, iOS, macOS, Linux, and test projects.
- `subtitle_display/`: a lightweight scrolling subtitle client.

Both use .NET 8. For the lightweight client:

```bash
cd subtitle_display
dotnet restore
dotnet run
```

## Project layout

```text
.
├── main.py                         # Process entry point for WebSocket and Flask API
├── start.sh                        # Local start, stop, log, and status commands
├── organize_models.py              # ModelScope download and organization tool
├── requirements.txt                # Python dependencies
├── src/modules/
│   ├── audio/                      # Audio processing, conversion, and VAD
│   ├── config/                     # Arguments, logging, and SSL
│   ├── core/                       # Service state and model loading
│   ├── database/                   # Flask API, SQLite data, and upload tasks
│   ├── network/                    # WebSocket and translation services
│   ├── serial/                     # Serial input
│   └── speaker/                    # Speaker identification, labeling, and voiceprints
├── ui/                             # Vue 3 + Vite management UI
├── VoiceRecognitionDisplay/        # .NET cross-platform subtitle clients
├── subtitle_display/               # .NET lightweight scrolling subtitle client
├── tests/                          # Python tests
└── Dockerfile                      # Multi-stage frontend/backend container build
```

## Development checks

```bash
# Python tests; model-dependent tests may require local models and audio hardware
pytest

# Frontend type check and production build
cd ui
npm run build

# Optional .NET subtitle-client tests
dotnet test VoiceRecognitionDisplay/VoiceRecognitionDisplay.sln
```

## License

This project is released under the [MIT License](LICENSE).
