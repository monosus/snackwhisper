import tkinter as tk
from tkinter import ttk


class StatusBar:
    status_bar = None

    def __init__(self, window, text="Ready"):
        self.frame = ttk.Frame(window, padding=(10, 4))
        self.frame.pack(side=tk.BOTTOM, fill=tk.X)

        sep = ttk.Separator(window, orient=tk.HORIZONTAL)
        sep.pack(side=tk.BOTTOM, fill=tk.X, before=self.frame)

        self.status_bar = ttk.Label(self.frame, text=text, anchor="w")
        self.status_bar.pack(fill=tk.X)

    def set_message(self, message):
        if self.status_bar is not None:
            self.status_bar.config(text=message)
            self.status_bar.update_idletasks()

    def clear_message(self):
        self.set_message("")
