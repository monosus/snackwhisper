"""subprocess を OS 非依存に呼ぶための小ヘルパ。

Windows では子プロセスのコンソールウィンドウを抑制するために
`creationflags=CREATE_NO_WINDOW` と `STARTUPINFO` を渡す必要があるが、
macOS / Linux にはそれらの属性自体が存在しない。
"""
import os
import subprocess


def hidden_window_kwargs() -> dict:
    """Windows では非表示ウィンドウ用の subprocess kwargs を返す。
    Mac / Linux では空 dict（追加引数なし）。"""
    if os.name != "nt":
        return {}

    startupinfo = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
    startupinfo.wShowWindow = subprocess.SW_HIDE  # type: ignore[attr-defined]
    return {
        "creationflags": subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
        "startupinfo": startupinfo,
    }
