#!/usr/bin/env bash
# macOS 用ビルドスクリプト。SnackWhisper.app を dist/ に生成する。
#
# 前提:
#   - Python 3.10+ で venv を作成し、requirements-mac.txt を入れてある
#   - インターネット接続 (vendor/macos/ffmpeg{,probe} が無ければ自動 DL)
#
# 使い方:
#   $ ./build.sh                    # システム/カレントの python を使用
#   $ ./build.sh ../venv/bin/python # 任意の python を指定

set -euo pipefail

cd "$(dirname "$0")"

PYTHON_BIN="${1:-python3}"
VENDOR_DIR="vendor/macos"

# --- ffmpeg / ffprobe の静的バイナリを vendor/macos に揃える ----------------
mkdir -p "$VENDOR_DIR"

fetch_evermeet() {
  local tool="$1"
  local url
  if [ "$tool" = "ffmpeg" ]; then
    url="https://evermeet.cx/ffmpeg/getrelease/zip"
  else
    url="https://evermeet.cx/ffmpeg/getrelease/${tool}/zip"
  fi
  echo "[build.sh] downloading ${tool} from evermeet.cx ..."
  local tmpdir
  tmpdir="$(mktemp -d)"
  curl -fsSL "$url" -o "$tmpdir/${tool}.zip"
  unzip -oq "$tmpdir/${tool}.zip" -d "$tmpdir"
  # 解凍後に出てくるバイナリ (フォルダ階層がある場合に備え find)
  local bin
  bin="$(find "$tmpdir" -type f -name "$tool" -perm +111 | head -n1)"
  if [ -z "$bin" ]; then
    bin="$(find "$tmpdir" -type f -name "$tool" | head -n1)"
  fi
  if [ -z "$bin" ]; then
    echo "[build.sh] ERROR: ${tool} binary not found in downloaded zip" >&2
    exit 1
  fi
  mv "$bin" "$VENDOR_DIR/$tool"
  chmod +x "$VENDOR_DIR/$tool"
  rm -rf "$tmpdir"
}

for tool in ffmpeg ffprobe; do
  if [ ! -f "$VENDOR_DIR/$tool" ]; then
    fetch_evermeet "$tool"
  else
    echo "[build.sh] ${tool} already vendored at ${VENDOR_DIR}/${tool}"
  fi
done

# 簡易検証: vendor の ffmpeg が実行可能か (アーキ違いはここで弾ける)
if ! "$VENDOR_DIR/ffmpeg" -version >/dev/null 2>&1; then
  echo "[build.sh] WARNING: $VENDOR_DIR/ffmpeg が実行できません (アーキ違い?)"
  "$VENDOR_DIR/ffmpeg" -version || true
fi

# --- アイコン (任意) ----------------------------------------------------------
if [ ! -f icon.icns ] && [ -f icon.ico ] && command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
  echo "[build.sh] icon.icns が見つからないため icon.ico から変換を試みます"
  TMP_ICONSET="$(mktemp -d)/icon.iconset"
  mkdir -p "$TMP_ICONSET"
  TMP_PNG="$(mktemp -d)/icon.png"
  if sips -s format png icon.ico --out "$TMP_PNG" >/dev/null 2>&1; then
    for sz in 16 32 64 128 256 512; do
      sips -z $sz $sz "$TMP_PNG" --out "$TMP_ICONSET/icon_${sz}x${sz}.png" >/dev/null 2>&1 || true
      sips -z $((sz*2)) $((sz*2)) "$TMP_PNG" --out "$TMP_ICONSET/icon_${sz}x${sz}@2x.png" >/dev/null 2>&1 || true
    done
    iconutil -c icns "$TMP_ICONSET" -o icon.icns && echo "[build.sh] icon.icns を生成しました" \
      || echo "[build.sh] icon.icns の生成に失敗。アイコン無しで続行します"
  else
    echo "[build.sh] icon.ico の PNG 変換に失敗。アイコン無しで続行します"
  fi
fi

# --- ビルド情報 ----------------------------------------------------------------
"$PYTHON_BIN" make_buildinfo.py

# --- PyInstaller --------------------------------------------------------------
rm -rf build dist/SnackWhisper.app dist/snackwhisper

"$PYTHON_BIN" -m PyInstaller snackwhisper_mac.spec --noconfirm

# --- ffmpeg / ffprobe を .app に同梱 ----------------------------------------
APP_BIN_DIR="dist/SnackWhisper.app/Contents/MacOS"
if [ -d "$APP_BIN_DIR" ]; then
  cp "$VENDOR_DIR/ffmpeg"  "$APP_BIN_DIR/ffmpeg"
  cp "$VENDOR_DIR/ffprobe" "$APP_BIN_DIR/ffprobe"
  chmod +x "$APP_BIN_DIR/ffmpeg" "$APP_BIN_DIR/ffprobe"
  echo "[build.sh] ffmpeg / ffprobe を $APP_BIN_DIR/ に同梱しました"
else
  echo "[build.sh] WARNING: $APP_BIN_DIR が見つかりません。.app ビルドに失敗?"
fi

echo
echo "[build.sh] 完了: dist/SnackWhisper.app"
echo "[build.sh] 起動: open dist/SnackWhisper.app"
