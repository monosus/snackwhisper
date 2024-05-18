import _version

__version__ = _version.__version__

# from tkinter import ttk
from transcription_app import TranscriptionApp
from tkinterdnd2 import TkinterDnD


# ウィンドウの作成とアプリケーションの開始
window = TkinterDnD.Tk()
app = TranscriptionApp(window)
window.update()
window.mainloop()
