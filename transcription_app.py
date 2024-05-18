import configparser
import os

# import os
import subprocess
import sys

import tkinter as tk
from lib.status_bar import StatusBar

# from tkinter import ttk
from tkinterdnd2 import DND_FILES

from tkinter import filedialog
from lib.my_icon import get_photo_image4icon
from lib.transcription_controller import TranscriptionController
from lib.constants import ButtonState


class TranscriptionApp:

    def __init__(self, window):
        self.config = configparser.ConfigParser()
        self.config.read("config.ini", encoding="utf-8")

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

        # 静音除去を実行するかどうかのフラグ
        setting_flag_silence = self.config.get(
            "DEFAULT", "flag_silence_removal", fallback="True"
        )
        self.flag_silence_removal: bool = setting_flag_silence == "True"

        setting_keep_silence_removed = self.config.get(
            "DEFAULT", "keep_silence_removed", fallback="False"
        )
        self.keep_silence_removed: bool = setting_keep_silence_removed == "True"

        self.create_widgets()
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.api_token = self.config.get("DEFAULT", "api_token", fallback="")
        if self.api_token == "":
            self.set_status("😗 APIトークンが未設定です")
        else:
            self.set_status("😀 APIトークンを読み込みました")

        # プロンプト用の辞書の取得
        self.prompt = self.load_dictionary()

        if sys.flags.debug:
            print(self.prompt)

        # ffmpegがインストールされているか確認
        self.check_ffmpeg_exists()

    # 辞書ファイルを読み込んで、改行を半角スペースで連結し、一行の文字列として返す。
    def load_dictionary(self) -> str | None:
        prompt: str | None = self.config.get("DEFAULT", "prompt", fallback=None)
        if prompt is None:
            prompt = ""
        else:
            prompt = prompt.replace("\\n", "\n")

        filename = self.config.get("DEFAULT", "dictionary", fallback="")

        if filename == "":
            return prompt

        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()
            dictionary = "".join(lines).replace("\n", " ")

        return prompt + dictionary

    def check_ffmpeg_exists(self):
        cmd = "ffmpeg"
        startupinfo = None

        if os.name == "nt":  # Windowsの場合
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        result = subprocess.run(
            ["where", cmd],
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        # エラーレベル（exit code）を取得、0 ならffmpegが存在する / 1 なら存在しない
        error_level = result.returncode
        if error_level == 0:
            self.ffmpeg_installed = True
        else:
            self.ffmpeg_installed = False

    # ステータスバーの表示を変更
    def set_status(self, message, button_state=ButtonState.NONE):
        self.status_bar.set_message(message)

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

        # 静音除去チェックボックス
        self.silence_removal_flag = tk.BooleanVar(value=self.flag_silence_removal)
        self.silence_removal_checkbox = tk.Checkbutton(
            file_frame,
            text="静音除去",
            variable=self.silence_removal_flag,
            onvalue=True,
            offvalue=False,
        )
        self.silence_removal_checkbox.grid(row=2, column=1, padx=5, pady=5)

        # ステータス表示エリア
        self.status_bar = StatusBar(self.window, "😀 準備完了")

    def drop(self, event):
        """
        ドラッグアンドドロップイベントを処理し、ドロップされたファイルのパスをテキストエリアに表示します。

        Args:
            event: ドラッグアンドドロップイベントに関する情報を含むオブジェクト。
        """
        if sys.flags.debug:
            print(event)
        self.file_path_display.delete("1.0", tk.END)
        replaced = self.replace_irregular_char(event.data)
        self.file_path_display.insert(tk.END, replaced)

        # replacedからファイル名の本体部分と拡張子を取り出す
        filebody = replaced.split("/")[-1]
        self.set_status(f"😀 ファイルを選択しました: {filebody}")

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

        self.load_from_widgets()

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

        # 静音除去フラグを保存
        self.config["DEFAULT"]["flag_silence_removal"] = str(self.flag_silence_removal)

        # プロンプトは保存しない（UI上で編集させない前提）
        # if self.prompt is not None:
        #     self.config["DEFAULT"]["prompt"] = self.prompt.replace("\\n", "\n")

        # 静音化ファイル保存フラグを保存
        self.config["DEFAULT"]["keep_silenced"] = str(self.keep_silence_removed)

        # 設定をファイルに書き込む
        with open("config.ini", "w", encoding="UTF-8") as configfile:
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

        # UIの情報を読み込む
        self.load_from_widgets()

        # ファイルパスを取得
        file_path_display_content = self.file_path_display.get("1.0", tk.END)
        file_path = file_path_display_content.strip()
        timestamp = self.timestamp_flag.get()

        # TranscriptionControllerを作成
        controller = self.make_transcription_controller(file_path, timestamp)

        # APIトークンの有効性を確認
        if controller.check_api_token() is False:
            self.set_status("😮‍💨 APIトークンが無効です")
            return

        # ファイル名を取得してステータスバーに表示
        filebody = file_path.split("/")[-1]
        self.set_status(f"😆 開始します: {filebody}", ButtonState.DISABLE)

        # 音声書き起こしを実行
        controller.transcribe_audio(self.flag_silence_removal)

    # TranscriptionControllerを作成
    def make_transcription_controller(self, file_path, timestamp):
        controller = TranscriptionController(
            self.api_token, file_path, timestamp_flag=timestamp
        )

        # 設定ファイルに記載があれば静音除去ファイルの保存フラグを設定する
        if self.config["DEFAULT"]["keep_silenced"] == "True":
            controller.keep_silence_removed_files = True

        if self.prompt is not None:
            controller.set_prompt(self.prompt)

        controller.set_status = self.set_status

        return controller

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

    # UIの情報を読み込む
    def load_from_widgets(self):
        self.api_token = self.api_token_entry.get()
        self.flag_silence_removal = self.silence_removal_flag.get()
