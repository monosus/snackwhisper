import tkinter as tk
from tkinter import font as tkfont, ttk

import _version

try:
    from _buildinfo import BUILD_TIMESTAMP
except Exception:
    BUILD_TIMESTAMP = ""


APP_NAME = "Snackゐsper"
APP_DESCRIPTION = "OpenAI Whisper / Google Gemini を利用した音声文字起こしツール"


class AboutDialog:
    """このアプリについてダイアログ"""

    def __init__(self, parent: tk.Misc):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("このアプリについて")
        self.window.transient(parent)  # type: ignore[arg-type]
        self.window.resizable(False, False)
        self.window.withdraw()

        self._build_ui()
        self._center_on_parent()
        self.window.deiconify()
        self.window.grab_set()

    def _center_on_parent(self):
        self.window.update_idletasks()
        try:
            parent_x = self.parent.winfo_rootx()
            parent_y = self.parent.winfo_rooty()
            parent_w = self.parent.winfo_width()
            parent_h = self.parent.winfo_height()
        except Exception:
            return
        dialog_w = self.window.winfo_reqwidth()
        dialog_h = self.window.winfo_reqheight()
        x = parent_x + max(0, (parent_w - dialog_w) // 2)
        y = parent_y + max(0, (parent_h - dialog_h) // 2)
        self.window.geometry(f"+{x}+{y}")

    def _build_ui(self):
        try:
            base_family = tkfont.nametofont("TkDefaultFont").actual("family")
        except Exception:
            base_family = "Segoe UI"

        outer = ttk.Frame(self.window, padding=(28, 24))
        outer.pack(fill=tk.BOTH, expand=True)

        # アプリ名
        ttk.Label(
            outer,
            text=APP_NAME,
            font=(base_family, 20, "bold"),
        ).pack(anchor="center")

        # バージョン
        ttk.Label(
            outer,
            text=f"version {_version.__version__}",
            font=(base_family, 10),
            foreground="#666666",
        ).pack(anchor="center", pady=(4, 0))

        # ビルド日時
        build_label = BUILD_TIMESTAMP if BUILD_TIMESTAMP else "開発ビルド"
        ttk.Label(
            outer,
            text=f"build: {build_label}",
            font=(base_family, 9),
            foreground="#888888",
        ).pack(anchor="center", pady=(2, 14))

        ttk.Separator(outer, orient="horizontal").pack(fill=tk.X, pady=(0, 14))

        # 説明
        ttk.Label(
            outer,
            text=APP_DESCRIPTION,
            font=(base_family, 9),
            foreground="#444444",
            justify="center",
            wraplength=320,
        ).pack(anchor="center")

        # OK
        btn_row = ttk.Frame(outer)
        btn_row.pack(pady=(20, 0))
        ttk.Button(
            btn_row,
            text="OK",
            style="Accent.TButton",
            command=self.window.destroy,
        ).pack()
