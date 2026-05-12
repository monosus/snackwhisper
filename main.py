import argparse
import sys

# Windows コンソール（cp932）でも絵文字が出せるよう UTF-8 に切り替える
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

import _version

__version__ = _version.__version__

from transcription_app import TranscriptionApp
from tkinterdnd2 import TkinterDnD


def parse_args():
    parser = argparse.ArgumentParser(description="SnackWhisper - 音声文字起こしツール")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="デバッグモードで起動（コンソールに進行状況を逐次出力）",
    )
    return parser.parse_args()


args = parse_args()

window = TkinterDnD.Tk()
app = TranscriptionApp(window, debug_mode=args.debug)
window.update()
window.mainloop()
