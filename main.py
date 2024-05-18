# from tkinter import ttk
from transcription_app import TranscriptionApp
from tkinterdnd2 import TkinterDnD

# バージョン番号を指定
__version__ = "0.1.1"

# ウィンドウの作成とアプリケーションの開始
window = TkinterDnD.Tk()
app = TranscriptionApp(window)
window.update()
window.mainloop()
