#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$ROOT_DIR/.env.local" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$ROOT_DIR/.env.local"
    set +a
fi

TOOLS_BIN="$ROOT_DIR/tools/bin"
if [ -d "$TOOLS_BIN" ]; then
    PATH="$TOOLS_BIN:$PATH"
    export PATH
    if [ -x "$TOOLS_BIN/ffmpeg" ]; then
        FFMPEG_BINARY="${FFMPEG_BINARY:-$TOOLS_BIN/ffmpeg}"
        export FFMPEG_BINARY
    fi
fi

STATE_DIR="${WYL_ASR_STATE_DIR:-$ROOT_DIR/.runtime/wyl-asr}"
LOG_DIR="$STATE_DIR/logs"
PID_DIR="$STATE_DIR/pids"
START_TIMEOUT="${WYL_ASR_START_TIMEOUT:-180}"

WS_HOST="${WYL_ASR_HOST:-0.0.0.0}"
WS_PORT="${WYL_ASR_WS_PORT:-10095}"
API_PORT="${WYL_ASR_API_PORT:-8080}"
UI_HOST="${WYL_ASR_UI_HOST:-127.0.0.1}"
UI_PORT="${WYL_ASR_UI_PORT:-5173}"
ENABLE_UI="${WYL_ASR_ENABLE_UI:-1}"
ENABLE_SERIAL="${WYL_ASR_ENABLE_SERIAL:-0}"
SERIAL_PORT="${WYL_ASR_SERIAL_PORT:-}"
SERIAL_BAUDRATE="${WYL_ASR_SERIAL_BAUDRATE:-9600}"
ENABLE_2PASS="${WYL_ASR_ENABLE_2PASS:-auto}"
ASR_MODEL="${WYL_ASR_ASR_MODEL:-$ROOT_DIR/models/SenseVoiceSmall}"
UPLOAD_ASR_MODEL="${WYL_ASR_UPLOAD_ASR_MODEL:-$ASR_MODEL}"
ONLINE_ASR_MODEL="${WYL_ASR_ONLINE_ASR_MODEL:-$ROOT_DIR/models/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch}"
UPLOAD_ASR_VAD_MODEL="${WYL_ASR_UPLOAD_ASR_VAD_MODEL:-$ROOT_DIR/models/speech_fsmn_vad_zh-cn-16k-common-pytorch}"
UPLOAD_ASR_SPK_MODEL="${WYL_ASR_UPLOAD_ASR_SPK_MODEL:-$ROOT_DIR/models/speech_campplus_sv_zh-cn_16k-common}"
UPLOAD_ASR_SPK_MODE="${WYL_ASR_UPLOAD_ASR_SPK_MODE:-vad_segment}"
UPLOAD_ASR_ENABLE_INTERNAL_SPEAKER="${WYL_ASR_UPLOAD_ASR_ENABLE_INTERNAL_SPEAKER:-1}"
UPLOAD_ASR_BATCH_SIZE_S="${WYL_ASR_UPLOAD_ASR_BATCH_SIZE_S:-60}"
UPLOAD_ASR_MERGE_VAD="${WYL_ASR_UPLOAD_ASR_MERGE_VAD:-0}"
UPLOAD_ASR_MERGE_LENGTH_S="${WYL_ASR_UPLOAD_ASR_MERGE_LENGTH_S:-8}"
UPLOAD_ASR_LANGUAGE="${WYL_ASR_UPLOAD_ASR_LANGUAGE:-zh}"
UPLOAD_ASR_VAD_MAX_SINGLE_SEGMENT_TIME="${WYL_ASR_UPLOAD_ASR_VAD_MAX_SINGLE_SEGMENT_TIME:-15000}"
DEFAULT_UPLOAD_ASR_PUNC_MODEL="$ROOT_DIR/models/punc_ct-transformer_zh-cn-common-vocab272727-pytorch"
if [ -d "$DEFAULT_UPLOAD_ASR_PUNC_MODEL" ]; then
    UPLOAD_ASR_PUNC_MODEL="${WYL_ASR_UPLOAD_ASR_PUNC_MODEL:-$DEFAULT_UPLOAD_ASR_PUNC_MODEL}"
else
    UPLOAD_ASR_PUNC_MODEL="${WYL_ASR_UPLOAD_ASR_PUNC_MODEL:-ct-punc}"
fi
MODEL_DEVICE="${WYL_ASR_MODEL_DEVICE:-auto}"
MODEL_NGPU="${WYL_ASR_NGPU:-}"
MODEL_NCPU="${WYL_ASR_NCPU:-4}"

info() {
    printf '[INFO] %s\n' "$*"
}

warn() {
    printf '[WARN] %s\n' "$*" >&2
}

error() {
    printf '[ERROR] %s\n' "$*" >&2
}

usage() {
    cat <<'EOF'
Usage:
  ./start.sh start             Start backend and optional UI (default)
  ./start.sh stop              Stop services started by this script
  ./start.sh restart           Restart services
  ./start.sh status            Show service status
  ./start.sh logs [backend|ui] Tail logs

Environment:
  WYL_ASR_HOST                 WebSocket/API bind host, default 0.0.0.0
  WYL_ASR_WS_PORT              WebSocket port, default 10095
  WYL_ASR_API_PORT             API port, default 8080
  WYL_ASR_ENABLE_UI            1 to start Vite UI, default 1
  WYL_ASR_UI_HOST              UI bind host, default 127.0.0.1
  WYL_ASR_UI_PORT              UI port, default 5173
  WYL_ASR_ENABLE_SERIAL        1 to enable serial support, default 0
  WYL_ASR_SERIAL_PORT          Serial port path, optional
  WYL_ASR_SERIAL_BAUDRATE      Serial baudrate, default 9600
  WYL_ASR_ENABLE_2PASS         auto, 1, or 0. auto disables 2pass if local online model is missing
  WYL_ASR_MODEL_DEVICE         auto, gpu, cuda, mps, or cpu. default auto prefers cuda then mps
  WYL_ASR_NGPU                 GPU/MPS enable flag passed to FunASR. default 1 for cuda/mps, 0 for cpu
  WYL_ASR_ASR_MODEL            Offline ASR model path/name, default models/SenseVoiceSmall
  WYL_ASR_UPLOAD_ASR_MODEL     Upload ASR model path/name, default same as WYL_ASR_ASR_MODEL
  WYL_ASR_UPLOAD_ASR_BATCH_SIZE_S Upload ASR dynamic batch seconds, default 60
  WYL_ASR_UPLOAD_ASR_MERGE_VAD 1 to merge upload VAD segments, default 0 for diarization accuracy
  WYL_ASR_UPLOAD_ASR_MERGE_LENGTH_S Upload ASR VAD merge seconds when merge is enabled, default 8
  WYL_ASR_UPLOAD_ASR_LANGUAGE  Upload ASR language, default zh
  WYL_ASR_UPLOAD_ASR_ENABLE_INTERNAL_SPEAKER
                                1 to enable FunASR built-in upload spk_model path, default 1
  WYL_ASR_UPLOAD_ASR_SPK_MODE  Upload built-in diarization mode, default vad_segment
  WYL_ASR_ONLINE_ASR_MODEL     Online 2pass model path/name, default local paraformer path
  WYL_ASR_START_TIMEOUT        Startup timeout seconds, default 180
EOF
}

pid_file() {
    printf '%s/%s.pid' "$PID_DIR" "$1"
}

log_file() {
    printf '%s/%s.log' "$LOG_DIR" "$1"
}

pid_is_running() {
    kill -0 "$1" 2>/dev/null
}

display_host() {
    if [ "$1" = "0.0.0.0" ]; then
        printf '127.0.0.1'
        return
    fi
    printf '%s' "$1"
}

backend_health_url() {
    printf 'http://127.0.0.1:%s/api/health' "$API_PORT"
}

ui_url() {
    printf 'http://%s:%s' "$(display_host "$UI_HOST")" "$UI_PORT"
}

backend_ws_url() {
    printf 'ws://%s:%s' "$(display_host "$WS_HOST")" "$WS_PORT"
}

backend_api_url() {
    printf 'http://%s:%s' "$(display_host "$WS_HOST")" "$API_PORT"
}

endpoint_is_ready() {
    curl -fsS --max-time 2 -o /dev/null "$1" >/dev/null 2>&1
}

port_is_open() {
    nc -z 127.0.0.1 "$1" >/dev/null 2>&1
}

backend_is_ready() {
    endpoint_is_ready "$(backend_health_url)"
}

ui_is_ready() {
    endpoint_is_ready "$(ui_url)"
}

resolve_python_bin() {
    if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
        printf '%s' "$ROOT_DIR/.venv/bin/python"
        return 0
    fi
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return 0
    fi
    if command -v python >/dev/null 2>&1; then
        command -v python
        return 0
    fi
    return 1
}

detect_model_device() {
    local python_bin="${1:-}"
    if [ -z "$python_bin" ] || [ ! -x "$python_bin" ]; then
        printf 'cpu'
        return 0
    fi

    "$python_bin" - <<'PY' 2>/dev/null || printf 'cpu'
try:
    import torch
    if torch.cuda.is_available():
        print("cuda")
    elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        print("mps")
    else:
        print("cpu")
except Exception:
    print("cpu")
PY
}

resolve_model_device_setting() {
    local requested
    local detected
    requested="$(printf '%s' "$MODEL_DEVICE" | tr '[:upper:]' '[:lower:]')"

    case "$requested" in
        auto|gpu)
            detected="$(detect_model_device "$PYTHON_BIN")"
            if [ "$requested" = "gpu" ] && [ "$detected" = "cpu" ]; then
                warn "WYL_ASR_MODEL_DEVICE=gpu was requested, but no CUDA/MPS GPU is available; falling back to cpu"
            fi
            MODEL_DEVICE="$detected"
            ;;
        cuda|mps|cpu)
            MODEL_DEVICE="$requested"
            ;;
        *)
            warn "invalid WYL_ASR_MODEL_DEVICE=$MODEL_DEVICE; using auto"
            MODEL_DEVICE="$(detect_model_device "$PYTHON_BIN")"
            ;;
    esac

    if [ -z "${WYL_ASR_NGPU:-}" ]; then
        case "$MODEL_DEVICE" in
            cuda|mps)
                MODEL_NGPU=1
                ;;
            *)
                MODEL_NGPU=0
                ;;
        esac
    fi

    info "model device: $MODEL_DEVICE, ngpu=$MODEL_NGPU"
}

check_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        error "Missing command: $1"
        return 1
    fi
}

ensure_state_dirs() {
    mkdir -p "$LOG_DIR" "$PID_DIR" || {
        error "Unable to create state directories under $STATE_DIR"
        return 1
    }
}

check_prerequisites() {
    local failed=0

    if [ ! -f "$ROOT_DIR/main.py" ]; then
        error 'main.py not found. Run this script from the wyl_asr project root.'
        failed=1
    fi

    PYTHON_BIN="$(resolve_python_bin || true)"
    if [ -z "${PYTHON_BIN:-}" ]; then
        error 'No usable Python interpreter found. Expected .venv/bin/python or python3.'
        failed=1
    else
        resolve_model_device_setting
    fi

    check_command curl || failed=1
    check_command nc || failed=1

    if [ "$ENABLE_UI" = "1" ]; then
        check_command npm || failed=1
        if [ ! -d "$ROOT_DIR/ui/node_modules" ]; then
            error 'UI dependencies are missing. Run npm install inside ui first, or set WYL_ASR_ENABLE_UI=0.'
            failed=1
        fi
    fi

    return "$failed"
}

kill_process_tree() {
    local pid="$1"
    local child

    for child in $(pgrep -P "$pid" 2>/dev/null || true); do
        kill_process_tree "$child"
    done
    kill -TERM "$pid" 2>/dev/null || true
}

service_ready() {
    case "$1" in
        backend) backend_is_ready ;;
        ui) ui_is_ready ;;
        *) return 1 ;;
    esac
}

wait_until_ready() {
    local service="$1"
    local pid="$2"
    local elapsed=0

    while [ "$elapsed" -lt "$START_TIMEOUT" ]; do
        if service_ready "$service"; then
            return 0
        fi
        if ! pid_is_running "$pid"; then
            error "$service exited early. Recent log output:"
            tail -n 30 "$(log_file "$service")" >&2
            return 1
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done

    error "$service did not become ready within ${START_TIMEOUT}s. Check $(log_file "$service")"
    return 1
}

launch_backend() {
    local log
    local upload_internal_speaker_lc
    local upload_merge_vad_lc
    local -a args

    log="$(log_file backend)"
    upload_internal_speaker_lc="$(printf '%s' "$UPLOAD_ASR_ENABLE_INTERNAL_SPEAKER" | tr '[:upper:]' '[:lower:]')"
    upload_merge_vad_lc="$(printf '%s' "$UPLOAD_ASR_MERGE_VAD" | tr '[:upper:]' '[:lower:]')"
    args=(
        "$PYTHON_BIN" "main.py"
        "--host" "$WS_HOST"
        "--port" "$WS_PORT"
        "--api-port" "$API_PORT"
        "--model_type" "sensevoice"
        "--asr_model" "$ASR_MODEL"
        "--upload_asr_model" "$UPLOAD_ASR_MODEL"
        "--upload_asr_vad_model" "$UPLOAD_ASR_VAD_MODEL"
        "--upload_asr_batch_size_s" "$UPLOAD_ASR_BATCH_SIZE_S"
        "--upload_asr_merge_length_s" "$UPLOAD_ASR_MERGE_LENGTH_S"
        "--upload_asr_language" "$UPLOAD_ASR_LANGUAGE"
        "--upload_asr_vad_max_single_segment_time" "$UPLOAD_ASR_VAD_MAX_SINGLE_SEGMENT_TIME"
        "--device" "$MODEL_DEVICE"
        "--ngpu" "$MODEL_NGPU"
        "--ncpu" "$MODEL_NCPU"
    )
    case "$upload_merge_vad_lc" in
        1|true|yes|on)
            args+=("--upload_asr_merge_vad")
            ;;
        *)
            args+=("--no-upload_asr_merge_vad")
            ;;
    esac
    case "$upload_internal_speaker_lc" in
        1|true|yes|on)
            args+=(
                "--upload_asr_enable_internal_speaker"
                "--upload_asr_spk_model" "$UPLOAD_ASR_SPK_MODEL"
                "--upload_asr_punc_model" "$UPLOAD_ASR_PUNC_MODEL"
                "--upload_asr_spk_mode" "$UPLOAD_ASR_SPK_MODE"
            )
            ;;
        *)
            args+=("--no-upload_asr_enable_internal_speaker")
            ;;
    esac

    case "$(printf '%s' "$ENABLE_2PASS" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes|on)
            args+=("--enable_2pass" "--online_model_dir" "$ONLINE_ASR_MODEL" "--asr_model_online" "$ONLINE_ASR_MODEL")
            ;;
        0|false|no|off)
            args+=("--disable_2pass")
            ;;
        auto)
            if [ -d "$ONLINE_ASR_MODEL" ]; then
                args+=("--enable_2pass" "--online_model_dir" "$ONLINE_ASR_MODEL" "--asr_model_online" "$ONLINE_ASR_MODEL")
            else
                warn "online 2pass model not found at $ONLINE_ASR_MODEL; starting with --disable_2pass"
                args+=("--disable_2pass")
            fi
            ;;
        *)
            warn "invalid WYL_ASR_ENABLE_2PASS=$ENABLE_2PASS; using auto"
            if [ -d "$ONLINE_ASR_MODEL" ]; then
                args+=("--enable_2pass" "--online_model_dir" "$ONLINE_ASR_MODEL" "--asr_model_online" "$ONLINE_ASR_MODEL")
            else
                warn "online 2pass model not found at $ONLINE_ASR_MODEL; starting with --disable_2pass"
                args+=("--disable_2pass")
            fi
            ;;
    esac

    if [ "$ENABLE_SERIAL" = "1" ]; then
        args+=("--enable_serial")
        if [ -n "$SERIAL_PORT" ]; then
            args+=("--serial_port" "$SERIAL_PORT")
        fi
        if [ -n "$SERIAL_BAUDRATE" ]; then
            args+=("--serial_baudrate" "$SERIAL_BAUDRATE")
        fi
    else
        args+=("--disable_serial")
    fi

    (
        cd "$ROOT_DIR" || exit 1
        exec nohup "${args[@]}"
    ) >>"$log" 2>&1 &

    printf '%s\n' "$!" >"$(pid_file backend)"
}

launch_ui() {
    local log

    log="$(log_file ui)"
    (
        cd "$ROOT_DIR/ui" || exit 1
        exec nohup npm run dev -- --host "$UI_HOST" --port "$UI_PORT"
    ) >>"$log" 2>&1 &

    printf '%s\n' "$!" >"$(pid_file ui)"
}

start_backend() {
    local file
    local pid

    file="$(pid_file backend)"
    if [ -f "$file" ]; then
        pid="$(cat "$file")"
        if pid_is_running "$pid"; then
            if backend_is_ready; then
                info "backend already running, PID=$pid, API=$(backend_api_url)"
                return 0
            fi
            error "backend PID file exists but service is not ready. Check $(log_file backend)"
            return 1
        fi
        rm -f "$file"
    fi

    if backend_is_ready; then
        info "backend already running outside this script, API=$(backend_api_url)"
        return 0
    fi

    if port_is_open "$WS_PORT" || port_is_open "$API_PORT"; then
        error "backend ports $WS_PORT/$API_PORT are occupied, but health checks failed."
        return 1
    fi

    info "starting backend, log=$(log_file backend)"
    launch_backend
    pid="$(cat "$file")"
    if wait_until_ready backend "$pid"; then
        info "backend started, PID=$pid"
        return 0
    fi
    if pid_is_running "$pid"; then
        kill_process_tree "$pid"
    fi
    rm -f "$file"
    return 1
}

start_ui() {
    local file
    local pid

    if [ "$ENABLE_UI" != "1" ]; then
        info 'UI startup is disabled (WYL_ASR_ENABLE_UI=0).'
        return 0
    fi

    file="$(pid_file ui)"
    if [ -f "$file" ]; then
        pid="$(cat "$file")"
        if pid_is_running "$pid"; then
            if ui_is_ready; then
                info "ui already running, PID=$pid, URL=$(ui_url)"
                return 0
            fi
            error "ui PID file exists but service is not ready. Check $(log_file ui)"
            return 1
        fi
        rm -f "$file"
    fi

    if ui_is_ready; then
        info "ui already running outside this script, URL=$(ui_url)"
        return 0
    fi

    if port_is_open "$UI_PORT"; then
        error "ui port $UI_PORT is occupied, but the page is not responding."
        return 1
    fi

    info "starting ui, log=$(log_file ui)"
    launch_ui
    pid="$(cat "$file")"
    if wait_until_ready ui "$pid"; then
        info "ui started, PID=$pid"
        return 0
    fi
    if pid_is_running "$pid"; then
        kill_process_tree "$pid"
    fi
    rm -f "$file"
    return 1
}

stop_service() {
    local service="$1"
    local file
    local pid
    local elapsed=0

    file="$(pid_file "$service")"
    if [ ! -f "$file" ]; then
        info "$service is not managed by this script."
        return 0
    fi

    pid="$(cat "$file")"
    if ! pid_is_running "$pid"; then
        rm -f "$file"
        info "$service is already stopped."
        return 0
    fi

    info "stopping $service, PID=$pid"
    kill_process_tree "$pid"
    while pid_is_running "$pid" && [ "$elapsed" -lt 20 ]; do
        sleep 1
        elapsed=$((elapsed + 1))
    done
    if pid_is_running "$pid"; then
        warn "$service did not exit within 20s, sending KILL."
        kill -KILL "$pid" 2>/dev/null || true
    fi
    rm -f "$file"
    info "$service stopped."
}

status_backend() {
    local file
    local pid

    file="$(pid_file backend)"
    if [ -f "$file" ]; then
        pid="$(cat "$file")"
        if pid_is_running "$pid"; then
            if backend_is_ready; then
                printf '%-12s READY    PID=%-8s %s\n' "backend" "$pid" "$(backend_api_url)"
                return 0
            fi
            printf '%-12s STARTING PID=%-8s %s\n' "backend" "$pid" "$(backend_api_url)"
            return 1
        fi
        rm -f "$file"
    fi

    if backend_is_ready; then
        printf '%-12s READY    PID=%-8s %s\n' "backend" "external" "$(backend_api_url)"
    elif port_is_open "$WS_PORT" || port_is_open "$API_PORT"; then
        printf '%-12s ERROR    %-12s ports %s/%s occupied\n' "backend" "" "$WS_PORT" "$API_PORT"
    else
        printf '%-12s STOPPED\n' "backend"
    fi
}

status_ui() {
    local file
    local pid

    if [ "$ENABLE_UI" != "1" ]; then
        printf '%-12s DISABLED\n' "ui"
        return 0
    fi

    file="$(pid_file ui)"
    if [ -f "$file" ]; then
        pid="$(cat "$file")"
        if pid_is_running "$pid"; then
            if ui_is_ready; then
                printf '%-12s READY    PID=%-8s %s\n' "ui" "$pid" "$(ui_url)"
                return 0
            fi
            printf '%-12s STARTING PID=%-8s %s\n' "ui" "$pid" "$(ui_url)"
            return 1
        fi
        rm -f "$file"
    fi

    if ui_is_ready; then
        printf '%-12s READY    PID=%-8s %s\n' "ui" "external" "$(ui_url)"
    elif port_is_open "$UI_PORT"; then
        printf '%-12s ERROR    %-12s port %s occupied\n' "ui" "" "$UI_PORT"
    else
        printf '%-12s STOPPED\n' "ui"
    fi
}

status_all() {
    status_backend
    status_ui
}

print_access_urls() {
    cat <<EOF

Access:
  WebSocket: $(backend_ws_url)
  API:       $(backend_api_url)
  UI:        $(ui_url)

Logs:
  ./start.sh logs backend
  ./start.sh logs ui
EOF
}

show_logs() {
    local service="${1:-}"

    ensure_state_dirs || return 1

    case "$service" in
        backend|ui)
            touch "$(log_file "$service")"
            tail -f "$(log_file "$service")"
            ;;
        "")
            touch "$(log_file backend)" "$(log_file ui)"
            tail -f "$(log_file backend)" "$(log_file ui)"
            ;;
        *)
            error "Unknown service: $service"
            usage
            return 1
            ;;
    esac
}

start_all() {
    local failed=0

    ensure_state_dirs || return 1
    check_prerequisites || return 1
    start_backend || failed=1
    if [ "$failed" -eq 0 ]; then
        start_ui || failed=1
    fi

    printf '\n'
    status_all
    if [ "$failed" -eq 0 ]; then
        print_access_urls
    fi
    return "$failed"
}

stop_all() {
    stop_service ui
    stop_service backend
}

action="${1:-start}"
case "$action" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        start_all
        ;;
    status)
        status_all
        ;;
    logs)
        show_logs "${2:-}"
        ;;
    help|-h|--help)
        usage
        ;;
    *)
        error "Unknown action: $action"
        usage
        exit 1
        ;;
esac
