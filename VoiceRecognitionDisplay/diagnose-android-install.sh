#!/bin/bash

set -u

PACKAGE_NAME="com.smartmeeting.display"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TIMESTAMP="$(date +"%Y%m%d-%H%M%S")"
OUTPUT_DIR="$SCRIPT_DIR/android-install-diagnostics/$TIMESTAMP"
APK_PATH="${1:-}"

mkdir -p "$OUTPUT_DIR"

find_default_apk() {
    find "$SCRIPT_DIR/VoiceRecognitionDisplay.Android/bin" -name "com.smartmeeting.display*.apk" 2>/dev/null | sort | tail -n 1
}

write_note() {
    echo "$1"
    echo "$1" >> "$OUTPUT_DIR/summary.txt"
}

if ! command -v adb >/dev/null 2>&1; then
    echo "adb not found. Please install Android platform-tools first."
    exit 1
fi

if [ -z "$APK_PATH" ]; then
    APK_PATH="$(find_default_apk)"
fi

if [ -z "$APK_PATH" ] || [ ! -f "$APK_PATH" ]; then
    echo "APK not found. Pass an APK path, or build the Android project first."
    echo "Expected something like: VoiceRecognitionDisplay.Android/bin/Release/net8.0-android34.0/com.smartmeeting.display-Signed.apk"
    exit 1
fi

: > "$OUTPUT_DIR/summary.txt"

write_note "=== Android install diagnosis ==="
write_note "Package: $PACKAGE_NAME"
write_note "APK: $APK_PATH"
write_note "Output: $OUTPUT_DIR"
write_note ""

adb devices -l > "$OUTPUT_DIR/adb_devices.txt" 2>&1
cat "$OUTPUT_DIR/adb_devices.txt"

if ! grep -qE "device$|device usb:" "$OUTPUT_DIR/adb_devices.txt"; then
    write_note "No online Android device detected."
    exit 1
fi

adb logcat -c > "$OUTPUT_DIR/logcat_clear.txt" 2>&1 || true
adb install -r "$APK_PATH" > "$OUTPUT_DIR/adb_install.txt" 2>&1
INSTALL_EXIT=$?

adb logcat -d > "$OUTPUT_DIR/logcat_full.txt" 2>&1 || true
grep -E "PackageInstaller|PackageManager|INSTALL_|Failure|Parse|AndroidRuntime|smartmeeting|OverlayService|MainActivity" \
    "$OUTPUT_DIR/logcat_full.txt" > "$OUTPUT_DIR/logcat_filtered.txt" || true
adb shell pm path "$PACKAGE_NAME" > "$OUTPUT_DIR/pm_path.txt" 2>&1 || true
adb shell dumpsys package "$PACKAGE_NAME" > "$OUTPUT_DIR/package_dump.txt" 2>&1 || true

write_note ""
write_note "adb install exit code: $INSTALL_EXIT"
write_note "adb install output:"
cat "$OUTPUT_DIR/adb_install.txt" | tee -a "$OUTPUT_DIR/summary.txt"
write_note ""
write_note "Saved files:"
write_note "  $OUTPUT_DIR/adb_install.txt"
write_note "  $OUTPUT_DIR/logcat_filtered.txt"
write_note "  $OUTPUT_DIR/logcat_full.txt"
write_note "  $OUTPUT_DIR/pm_path.txt"
write_note "  $OUTPUT_DIR/package_dump.txt"

if [ "$INSTALL_EXIT" -ne 0 ]; then
    write_note ""
    write_note "Install failed. Check adb_install.txt and logcat_filtered.txt first."
    exit "$INSTALL_EXIT"
fi

write_note ""
write_note "Install finished successfully."
