"""tkinterdnd2 のロードを試みて、失敗時は素の tkinter にフォールバックする。

macOS の Homebrew Python は Tcl/Tk 9 とリンクしており、現在 PyPI で配布されている
tkinterdnd2 の dylib (Tcl 8 ABI) はロードできない。その場合でも、アプリ全体が
起動できるようにドラッグ&ドロップだけ無効化する。
"""
from __future__ import annotations

import tkinter
from typing import Any


DND_AVAILABLE = False
DND_FILES = "DND_Files"  # 識別子。利用不可時はダミー値で OK

try:
    from tkinterdnd2 import TkinterDnD as _TkinterDnD, DND_FILES as _DND_FILES  # type: ignore

    # 実際に Tk() を作って tkdnd ライブラリのロードまで通るか確かめる
    _probe = _TkinterDnD.Tk()
    _probe.destroy()

    Tk = _TkinterDnD.Tk
    DND_FILES = _DND_FILES
    DND_AVAILABLE = True
except Exception:
    # tkinterdnd2 未インストール、または tkdnd dylib ロード失敗 (Tcl 9 不整合など)
    Tk = tkinter.Tk


def register_drop_target(widget: Any, on_drop) -> bool:
    """ウィジェットに D&D を登録する。利用不可なら何もせず False を返す。"""
    if not DND_AVAILABLE:
        return False
    try:
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<Drop>>", on_drop)
        return True
    except Exception:
        return False
