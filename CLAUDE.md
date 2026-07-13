# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WYL ASR is a multi-component real-time speech recognition system built on Alibaba's FunASR framework. The system consists of three main services that work together:

1. **WebSocket Server** (port 10095) - Real-time ASR processing with VAD, speaker recognition, and translation
2. **HTTP API Server** (port 8080) - Database operations, device management, and RESTful endpoints
3. **Vue Frontend** (port 5173/3000) - User interface for recording, meetings, and transcription management

Additionally, there's a C# .NET MAUI cross-platform display application (`VoiceRecognitionDisplay/`) for Android/iOS/Desktop clients.

## Essential Commands

### Starting Services

```bash
# Start WebSocket server (ASR service)
python main.py --host 0.0.0.0 --port 10095

# Start API server (database/device management)
python -m src.modules.network.start_api --host 0.0.0.0 --port 8080

# Start frontend (development)
cd ui && npm run dev

# Start all services (use existing script)
./start_all.sh  # Linux/macOS
start_all.bat   # Windows
```

### Model Management

```bash
# Download and organize all required models (first-time setup)
python organize_models.py

# Check model integrity
python tests/check_models.py

# Force re-download specific model
python organize_models.py --model paraformer-zh --force-download
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
python tests/test_websocket.py              # WebSocket functionality
python tests/test_asr_functions.py          # ASR core functions
python tests/test_database_api.py           # Database API
python tests/test_hotwords.py               # Hotword functionality
python tests/test_speaker_diarization.py    # Speaker recognition

# Web-based testing
open tests/test.html  # Browser-based WebSocket test
```

### Code Quality

```bash
# Format code (configured in pyproject.toml)
black src/ tests/
isort src/ tests/

# Lint code
flake8 src/
mypy src/

# Run with specific linting config
pytest tests/ --cov=src --cov-report=html
```

### Frontend Development

```bash
cd ui

# Install dependencies
npm install

# Development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Architecture Overview

### Service Communication Flow

```
Client → WebSocket (10095) → ASR Processing → Results
Client → HTTP API (8080) → Database/Devices → Response
Frontend (5173) → Both Services → Unified UI
```

### Core Module Structure

The `src/modules/` directory contains the main business logic:

- **audio/**: Audio processing, VAD monitoring, format handling, duration tracking
- **config/**: Argument parsing, logging setup, SSL configuration
- **core/**: Central service coordination, document segmentation, server state management
- **database/**: SQLite operations (meetings, transcripts, users), RESTful API layer
- **network/**: WebSocket service, connection management, translation service, API server
- **speaker/**: Speaker recognition, verification, hotword management, labeling
- **serial/**: Serial port communication for hardware integration
- **text/**: Text processing utilities

### ASR Processing Pipeline

The system supports three recognition modes:

1. **Online Mode** (`mode: "online"`): Low-latency streaming recognition using Paraformer-Online model
2. **Offline Mode** (`mode: "offline"`): High-accuracy batch recognition using SenseVoiceSmall model
3. **2Pass Mode** (`mode: "2pass"`): Hybrid approach combining online speed with offline accuracy

**Key Processing Flow**:
```
Audio Input → VAD Detection → ASR Recognition → Punctuation Restoration →
Speaker Recognition (optional) → Translation (optional) → Result Output
```

### Database Schema

The SQLite database (`data/wyl_asr.db`) manages:
- **meetings**: Meeting metadata, participants, duration
- **transcripts**: Speech recognition results with timestamps
- **users**: User authentication and profiles
- **audio_files**: Original audio storage references
- **documents**: Generated meeting minutes and summaries

Access via API endpoints at `http://localhost:8080/api/*` or directly through `DatabaseManager` class.

### WebSocket Protocol

**Connection**: `ws://localhost:10095` with `binary` subprotocol

**Message Types**:
- `init`: Configuration (mode, language, sample_rate, vad_threshold, enable_vad, hotwords)
- Audio data: Raw PCM binary (16kHz, 16-bit, mono)
- `end`: Signal end of audio stream
- `register_speaker`: Speaker registration with audio sample
- `translate`: Translation request

**Response Format**:
```json
{
  "type": "result",
  "mode": "online|offline|2pass",
  "text": "recognized text",
  "is_final": true|false,
  "timestamp": 1234567890,
  "confidence": 0.95,
  "speaker_id": "user001",  // if speaker recognition enabled
  "translation": "translated text"  // if translation enabled
}
```

## Important Patterns and Conventions

### Model Loading

Models are loaded once at server startup via `load_models()` in `server_state.py`. The system uses lazy loading and caches model instances in `ServerState` class. Models are stored in `./models/` directory and managed by ModelScope.

**Critical**: Always run `python organize_models.py` before first use to download required models (~4GB total).

### Error Handling

The codebase uses custom exception classes for different modules:
- `ArgumentError` - Command-line argument issues
- `AudioProcessingError` - Audio processing failures
- `ModelLoadError` - Model loading problems
- `DatabaseError` - Database operation failures
- `SpeakerManagerError` - Speaker recognition issues

Always catch these specific exceptions rather than generic `Exception`.

### Async/Await Pattern

The WebSocket service is fully asynchronous. Key async functions:
- `async_vad()` - VAD detection
- `async_asr()` - Offline ASR
- `async_asr_online()` - Online streaming ASR
- `ws_serve()` - Main WebSocket handler

Never block the event loop with synchronous I/O operations.

### Configuration Priority

Settings are resolved in this order (highest to lowest):
1. Command-line arguments (`--host`, `--port`, etc.)
2. Environment variables (`WYL_ASR_HOST`, `WYL_ASR_PORT`, etc.)
3. Default values in code

### Frontend State Management

The Vue frontend uses Pinia for state management. Main store: `ui/src/stores/asr.ts`

Key state:
- WebSocket connection status
- Recording state
- Recognition results
- Speaker recognition toggle
- Audio device selection

## Critical Gotchas

### Port Confusion

**Common mistake**: Accessing API endpoints on WebSocket port or vice versa.
- WebSocket (ASR): `ws://localhost:10095`
- HTTP API: `http://localhost:8080`
- Frontend: `http://localhost:5173` (dev) or `http://localhost:3000` (prod)

### Audio Format Requirements

The system ONLY accepts:
- Format: PCM (raw audio)
- Sample rate: 16kHz
- Bit depth: 16-bit
- Channels: Mono (1 channel)

Use FFmpeg to convert: `ffmpeg -i input.mp3 -ar 16000 -ac 1 -f s16le output.pcm`

### VAD Threshold Tuning

Default VAD threshold is 0.3. Adjust based on environment:
- Quiet environment: 0.2-0.3 (more sensitive)
- Noisy environment: 0.5-0.8 (less sensitive)

Too low = false positives (noise detected as speech)
Too high = missed speech segments

### Speaker Recognition Mode

Speaker recognition has two modes controlled by frontend toggle:
- **Recognition Mode**: Identifies registered speakers
- **Separation Mode**: Separates multi-speaker audio (diarization)

Both use the same backend but different processing paths. Enable with `--enable_speaker` flag.

### Model Cache Location

Models are cached in `./models/` by default. This directory can grow to 4GB+.

Change location: `export WYL_ASR_CACHE_DIR=/path/to/models` or `--cache_dir` argument.

### Serial Communication

The system supports serial port communication for hardware integration (see `SERIAL_*.md` docs). Serial module is in `src/modules/serial/`.

**Important**: Serial features are optional and require additional hardware setup.

### Translation Performance

Translation uses a 4GB model and is SLOW. The README notes: "经测试模型太大4G,翻译太慢" (translation is too slow due to large model size).

Only enable translation if absolutely necessary: `--enable_translation`

### C# Display App

The `VoiceRecognitionDisplay/` directory contains a separate .NET MAUI application for cross-platform display clients. This is built independently:

```bash
cd VoiceRecognitionDisplay
dotnet build
```

Targets: Android, iOS, macOS, Desktop (Windows/Linux)

## Development Workflow

### Adding New Features

1. Implement core logic in appropriate `src/modules/` subdirectory
2. Add tests in `tests/test_<feature>.py`
3. Update API endpoints in `src/modules/database/database_api.py` if needed
4. Add frontend UI in `ui/src/components/` if user-facing
5. Document in `docs/` directory
6. Update `CHANGELOG.md`

### Debugging ASR Issues

1. Check VAD detection: `python tests/debug_vad_threshold.py`
2. Verify audio format: `python tests/debug_audio_format.py`
3. Test with known good audio: `python tests/test_real_audio.py`
4. Check model loading: `python tests/check_models.py`
5. Enable debug logging: `python main.py --log-level DEBUG`

### Database Migrations

The database schema is managed in `src/modules/database/database_manager.py`. Schema changes require:
1. Update `DatabaseManager._create_tables()` method
2. Add migration logic if needed
3. Test with `python tests/test_database_manager.py`
4. Document schema changes

## Environment Setup

### Python Environment

```bash
# Create conda environment (recommended)
conda create -n funasr python=3.8
conda activate funasr

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install -r requirements-dev.txt
```

### GPU Support

For CUDA acceleration:
```bash
# Install PyTorch with CUDA
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# Run with GPU
python main.py --device cuda --ngpu 1
```

### macOS Audio (PyAudio)

```bash
# Install PortAudio first
brew install portaudio

# Then install PyAudio
pip install pyaudio
```

## Useful Debugging Commands

```bash
# Check if services are running
lsof -i :10095  # WebSocket
lsof -i :8080   # API
lsof -i :5173   # Frontend

# Test WebSocket connection
curl -i http://127.0.0.1:10095  # Should return 426 Upgrade Required

# Test API health
curl http://127.0.0.1:8080/api/health

# Check audio devices
python check_serial_ports.py
python test_audio_device.py

# Monitor logs
tail -f logs/wyl_asr.log
tail -f api_server.log
```

## Configuration Files

- `pyproject.toml` - Python project config, build settings, tool configurations
- `requirements.txt` - Production dependencies
- `requirements-dev.txt` - Development dependencies
- `ui/package.json` - Frontend dependencies
- `ui/vite.config.ts` - Vite build configuration
- `config/config.py` - Application configuration
- `local_models.conf` - Local model paths (if using custom models)

## Additional Documentation

Comprehensive documentation is available in the `docs/` directory:
- `API_DOCUMENTATION.md` - Complete API reference
- `DEPLOYMENT_GUIDE.md` - Production deployment guide
- `DEVELOPER_GUIDE.md` - Detailed development guide
- `QUICK_START.md` - Quick start guide (Chinese)
- Module-specific docs for each component

For serial communication features, see:
- `SERIAL_SETUP.md`
- `SERIAL_TROUBLESHOOTING.md`
- `SERIAL_COMMANDS.md`
