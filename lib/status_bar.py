import tkinter as tk


class StatusBar:
    status_bar = None

    def __init__(self, window, text="Ready"):

        self.status_bar = tk.Label(
            window, text=text, bd=1, relief=tk.SUNKEN, anchor=tk.W
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def set_message(self, message):
        if self.status_bar is not None:
            self.status_bar.config(text=message)
            self.status_bar.update_idletasks()

    def clear_message(self):
        self.set_message("")
