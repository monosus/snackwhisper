# -*- mode: python ; coding: utf-8 -*-
"""macOS 用 PyInstaller spec。`.app` バンドルを生成する。

build.sh から `pyinstaller snackwhisper_mac.spec` で呼び出される想定。
icon.icns が存在すればアイコンとして利用、なければアイコン無しでビルド。
"""
import os
from PyInstaller.utils.hooks import collect_all, collect_data_files


here = os.path.abspath(os.getcwd())

icns_path = os.path.join(here, "icon.icns")
app_icon = icns_path if os.path.exists(icns_path) else None

datas = []
binaries = []
hiddenimports = []

# 既存 ico も同梱（アプリ内コードからの参照に備える）
if os.path.exists(os.path.join(here, "icon.ico")):
    datas.append(("icon.ico", "."))

datas += collect_data_files("sv_ttk")
datas += collect_data_files("tkinterdnd2")

tmp_ret = collect_all("google.genai")
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["."],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="snackwhisper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="snackwhisper",
)

app = BUNDLE(
    coll,
    name="SnackWhisper.app",
    icon=app_icon,
    bundle_identifier="com.monosus.snackwhisper",
    info_plist={
        "CFBundleName": "SnackWhisper",
        "CFBundleDisplayName": "SnackWhisper",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "10.13",
    },
)
