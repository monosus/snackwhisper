import configparser
import os
import subprocess
import sys

import tkinter as tk

# from tkinter import ttk
from tkinterdnd2 import TkinterDnD, DND_FILES

from tkinter import filedialog
from lib.my_icon import get_photo_image4icon
from lib.transcription_controller import TranscriptionController
from lib.constants import ButtonState


class TranscriptionApp:

    def __init__(self, window):
        self.config = configparser.ConfigParser()
        self.config.read("config.ini")

        self.window = window
        self.window.title("Snackゐsper")

        # ウィンドウの位置を復元
        x = self.config.get("DEFAULT", "x", fallback="100")
        y = self.config.get("DEFAULT", "y", fallback="100")
        self.window.geometry(f"+{x}+{y}")

        # ウィンドウのサイズを復元
        width = self.config.get("DEFAULT", "width", fallback="600")
        height = self.config.get("DEFAULT", "height", fallback="220")
        self.window.geometry(f"{width}x{height}")

        # ウィンドウサイズを変更できないようにする
        self.window.resizable(False, False)

        # タイムスタンプフラグを復元
        timestamp_flag = self.config.get("DEFAULT", "timestamp_flag", fallback="False")
        self.saved_timestamp_flag = timestamp_flag == "True"

        # 全体を包含するフレームにパディングを追加
        self.main_frame = tk.Frame(self.window, padx=20, pady=20)
        self.main_frame.pack(expand=True, fill=tk.BOTH)

        self.create_widgets()
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.api_token = self.config.get("DEFAULT", "api_token", fallback="")
        if self.api_token == "":
            self.set_status("😗 APIトークンが未設定です")
        else:
            self.set_status("😀 APIトークンを読み込みました")

        # ffmpegがインストールされているか確認
        self.check_ffmpeg_exists()

    def check_ffmpeg_exists(self):
        cmd = "ffmpeg"
        startupinfo = None
        if os.name == "nt":  # Windowsの場合
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        result = subprocess.run(
            ["where", cmd], capture_output=True, text=True, startupinfo=startupinfo
        )

        # エラーレベル（exit code）を取得、0 ならffmpegが存在する / 1 なら存在しない
        error_level = result.returncode
        if error_level == 0:
            self.ffmpeg_installed = True
        else:
            self.ffmpeg_installed = False

    # ステータスバーの表示を変更
    def set_status(self, message, button_state=ButtonState.NONE):
        self.status_bar.config(text=message)

        if button_state == ButtonState.RELEASE:
            # 実行ボタンを押せるように有効化する
            self.transcribe_button.config(state=tk.NORMAL)
        elif button_state == ButtonState.DISABLE:
            # 実行ボタンを押せないように無効化する
            self.transcribe_button.config(state=tk.DISABLED)

        # ウィンドウをリフレッシュ
        self.window.update()

    def create_widgets(self):
        label_width = 20

        # アプリケーションアイコンの設
        try:
            icon = get_photo_image4icon()
            self.window.iconphoto(False, icon)
        except tk.TclError:
            self.set_status("😫 アイコンの読み込みに失敗しました")

        # APIトークン入力フィールド
        token_frame = tk.Frame(self.main_frame)
        token_frame.pack(anchor="w")

        api_token_label = tk.Label(
            token_frame, text="WhisperAPI Token:", width=label_width
        )
        api_token_label.grid(row=0, column=0, padx=5, pady=5)

        # APIトークン入力エリア
        self.api_token_entry = tk.Entry(token_frame, width=50, font=("Arial", 8))
        self.api_token_entry.insert(0, self.config["DEFAULT"].get("api_token", ""))
        self.api_token_entry.grid(row=0, column=1, padx=5, pady=5, columnspan=2)

        # ファイルパス表示エリアと選択ボタンのフレーム
        file_frame = tk.Frame(self.main_frame)
        file_frame.pack()

        # ファイル選択ボタン
        select_file_button = tk.Button(
            file_frame,
            text="ファイルを選択",
            command=self.open_file_dialog,
            width=label_width,
        )
        select_file_button.grid(row=1, column=0, padx=5, pady=5)

        # ファイルパス表示エリア
        self.file_path_display = tk.Text(
            file_frame, height=1, width=50, font=("Arial", 8)
        )
        self.file_path_display.drop_target_register(DND_FILES)  # type: ignore
        self.file_path_display.dnd_bind("<<Drop>>", self.drop)  # type: ignore
        self.file_path_display.grid(row=1, column=1, padx=5, pady=5, columnspan=2)

        # 実行ボタン（横長にサイズ変更）
        self.transcribe_button = tk.Button(
            file_frame, text="実行", command=self.run_transcribe, width=label_width
        )
        self.transcribe_button.grid(row=3, column=1, padx=5, pady=5)

        # タイムスタンプチェックボックス
        self.timestamp_flag = tk.BooleanVar(value=self.saved_timestamp_flag)
        timestamp_checkbox = tk.Checkbutton(
            file_frame,
            text="タイムスタンプ付与",
            variable=self.timestamp_flag,
            onvalue=True,
            offvalue=False,
        )
        timestamp_checkbox.grid(row=2, column=2, padx=5, pady=5)

        # ステータス表示エリア
        self.status_bar = tk.Label(
            self.window, text="😀 準備完了", bd=1, relief=tk.SUNKEN, anchor=tk.W
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def drop(self, event):
        if sys.flags.debug:
            print(event)
        # ドロップされたファイルパスをテキストエリアに表示
        self.file_path_display.delete("1.0", tk.END)
        replaced = self.replace_irregular_char(event.data)
        self.file_path_display.insert(tk.END, replaced)

    # 入力テキストに\が含まれていれば/に変換し、{}を削除する
    def replace_irregular_char(self, text):
        text = text.replace("\\", "/")
        text = text.replace("{", "")
        text = text.replace("}", "")
        return text

    # ファイル選択ダイアログを開く
    def open_file_dialog(self):

        filetypes = [
            ("メディアファイル", "*.mp3"),
            ("メディアファイル", "*.wav"),
            ("メディアファイル", "*.m4a"),
            ("メディアファイル", "*.flac"),
        ]
        if self.ffmpeg_installed:
            filetypes.append(("メディアファイル", "*.mp4"))

        file_path = filedialog.askopenfilename(filetypes=filetypes)
        if file_path:
            self.file_path_display.delete("1.0", tk.END)
            self.file_path_display.insert(tk.END, file_path)

    def save_settings(self):
        api_token = self.api_token_entry.get()
        if api_token == "":
            return False

        # APIトークンを保存
        token = self.api_token_entry.get()
        self.config["DEFAULT"]["API_TOKEN"] = token

        # ウィンドウ位置を保存
        self.config["DEFAULT"]["x"] = str(self.window.winfo_x())
        self.config["DEFAULT"]["y"] = str(self.window.winfo_y())

        # ウィンドウのサイズを保存
        self.config["DEFAULT"]["width"] = str(self.window.winfo_width())
        self.config["DEFAULT"]["height"] = str(self.window.winfo_height())

        # タイムスタンプフラグを保存
        self.config["DEFAULT"]["timestamp_flag"] = str(self.timestamp_flag.get())

        with open("config.ini", "w") as configfile:
            self.config.write(configfile)

        return True

    # 音声書き起こしを実行
    def run_transcribe(self):
        if self.ffmpeg_installed is False:
            self.set_status("😮 ffmpegをインストールしてください")
            return

        if self.file_path_display.get("1.0", tk.END).strip() == "":
            self.set_status("😮 ファイルが未選択です")
            return

        # APIトークンを保存
        if self.save_settings() is False:
            self.set_status("😮‍💨 APIトークンが未設定です")
            return

        # ファイルパスを取得
        file_path_display_content = self.file_path_display.get("1.0", tk.END)
        file_path = file_path_display_content.strip()
        timestamp = self.timestamp_flag.get()

        # 実行直前にもAPIトークンを取得
        self.api_token = self.config.get("DEFAULT", "api_token", fallback="")

        controller = TranscriptionController(
            self.api_token, file_path, timestamp_flag=timestamp
        )
        controller.set_status = self.set_status

        # APIトークンの有効性を確認
        if controller.check_api_token() is False:
            self.set_status("😮‍💨 APIトークンが無効です")
            return

        # ファイル名を取得してステータスバーに表示
        filebody = file_path.split("/")[-1]
        self.set_status(f"😆 開始します: {filebody}", ButtonState.DISABLE)

        # 音声書き起こしを実行
        controller.transcribe_audio()

    def on_closing(self):
        # アプリケーション終了時にAPIトークンを保存
        self.save_settings()
        self.window.destroy()

    def error_process(self, error):
        status_code = error.status_code
        # code = error.code # 'invalid_api_key' などが入る
        message = error.body["message"]

        if status_code == 401:
            self.set_status("😫 APIトークンが無効です")
        else:
            self.set_status(f"😫 エラーです: {message}")


# ウィンドウの作成とアプリケーションの開始
window = TkinterDnD.Tk()
app = TranscriptionApp(window)
window.update()
window.mainloop()
