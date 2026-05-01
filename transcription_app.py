import configparser
import os
import subprocess
import sys

import tkinter as tk
from lib.debug_options import DebugOptions
from lib.status_bar import StatusBar

from tkinterdnd2 import DND_FILES

from tkinter import filedialog, messagebox, ttk
from lib.my_icon import get_photo_image4icon
from lib.transcription_controller import TranscriptionController
from lib.constants import ButtonState
from lib.model_profile import ProfileRegistry
from lib.output_options import (
    OUTPUT_FORMATS,
    SUBTITLE_CAPABLE_MODELS,
    FORMAT_TXT,
    OutputOptions,
)
from lib.settings_dialog import SettingsDialog


class TranscriptionApp:

    def __init__(self, window):
        self.config = configparser.ConfigParser()
        self.config.read("config.ini", encoding="utf-8")

        self.window = window
        self.window.title("Snackゐsper")

        self.result_encoding = self.config.get(
            "DEFAULT", "result_encoding", fallback="utf-8"
        )

        x = self.config.get("DEFAULT", "x", fallback="100")
        y = self.config.get("DEFAULT", "y", fallback="100")
        self.window.geometry(f"+{x}+{y}")

        width = self.config.get("DEFAULT", "width", fallback="780")
        height = self.config.get("DEFAULT", "height", fallback="300")
        self.window.geometry(f"{width}x{height}")

        self.window.resizable(True, True)
        self.window.minsize(640, 260)

        self.output_options = OutputOptions.load(self.config)
        self.saved_timestamp_flag = self.output_options.timestamp

        self.main_frame = tk.Frame(self.window, padx=20, pady=20)
        self.main_frame.pack(expand=True, fill=tk.BOTH)

        setting_flag_silence = self.config.get(
            "DEFAULT", "flag_silence_removal", fallback="True"
        )
        self.flag_silence_removal: bool = setting_flag_silence == "True"

        setting_keep_silence_removed = self.config.get(
            "DEFAULT", "keep_silence_removed", fallback="False"
        )
        self.keep_silence_removed: bool = setting_keep_silence_removed == "True"

        self.debug_options = DebugOptions(self.config)

        # モデルプロファイルを読み込む（旧 api_token があれば自動で1件移行される）
        self.profile_registry = ProfileRegistry.load(self.config)

        self.create_widgets()
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

        self._refresh_profile_dropdown()
        self._sync_option_states()
        self._update_status_for_selected_profile()

        self.prompt = self.load_dictionary()

        if sys.flags.debug:
            print(self.prompt)

        self.check_ffmpeg_exists()

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

        if os.name == "nt":
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

        self.ffmpeg_installed = result.returncode == 0

    def set_status(self, message, button_state=ButtonState.NONE):
        self.status_bar.set_message(message)

        if button_state == ButtonState.RELEASE:
            self.transcribe_button.config(state=tk.NORMAL)
        elif button_state == ButtonState.DISABLE:
            self.transcribe_button.config(state=tk.DISABLED)

        self.window.update()

    def create_widgets(self):
        label_width = 20

        try:
            icon = get_photo_image4icon()
            self.window.iconphoto(False, icon)
        except tk.TclError:
            self.set_status("😫 アイコンの読み込みに失敗しました")

        # モデル選択行
        profile_frame = tk.Frame(self.main_frame)
        profile_frame.pack(anchor="w")

        tk.Label(profile_frame, text="使用モデル:", width=label_width).grid(
            row=0, column=0, padx=5, pady=5
        )

        self.profile_var = tk.StringVar()
        self.profile_dropdown = ttk.Combobox(
            profile_frame,
            textvariable=self.profile_var,
            state="readonly",
            width=40,
        )
        self.profile_dropdown.grid(row=0, column=1, padx=5, pady=5)
        self.profile_dropdown.bind("<<ComboboxSelected>>", self._on_profile_change)

        tk.Button(
            profile_frame, text="設定...", width=8, command=self.open_settings
        ).grid(row=0, column=2, padx=5, pady=5)

        # ファイル選択行
        file_frame = tk.Frame(self.main_frame)
        file_frame.pack()

        select_file_button = tk.Button(
            file_frame,
            text="ファイルを選択",
            command=self.open_file_dialog,
            width=label_width,
        )
        select_file_button.grid(row=1, column=0, padx=5, pady=5)

        self.file_path_display = tk.Text(
            file_frame, height=1, width=50, font=("Arial", 8)
        )
        self.file_path_display.drop_target_register(DND_FILES)  # type: ignore
        self.file_path_display.dnd_bind("<<Drop>>", self.drop)  # type: ignore
        self.file_path_display.grid(row=1, column=1, padx=5, pady=5, columnspan=2)

        self.transcribe_button = tk.Button(
            file_frame, text="実行", command=self.run_transcribe, width=label_width
        )
        self.transcribe_button.grid(row=3, column=1, padx=5, pady=5)

        self.timestamp_flag = tk.BooleanVar(value=self.saved_timestamp_flag)
        timestamp_checkbox = tk.Checkbutton(
            file_frame,
            text="タイムスタンプ付与",
            variable=self.timestamp_flag,
            onvalue=True,
            offvalue=False,
        )
        timestamp_checkbox.grid(row=2, column=2, padx=5, pady=5)

        self.silence_removal_flag = tk.BooleanVar(value=self.flag_silence_removal)
        self.silence_removal_checkbox = tk.Checkbutton(
            file_frame,
            text="静音除去",
            variable=self.silence_removal_flag,
            onvalue=True,
            offvalue=False,
        )
        self.silence_removal_checkbox.grid(row=2, column=1, padx=5, pady=5)

        # 出力オプション行
        output_frame = tk.LabelFrame(self.main_frame, text="出力オプション", padx=8, pady=4)
        output_frame.pack(anchor="w", fill=tk.X, pady=(8, 0))

        tk.Label(output_frame, text="形式:").grid(row=0, column=0, padx=4, pady=2, sticky="w")
        self.output_format_var = tk.StringVar(value=self.output_options.output_format)
        self.output_format_combo = ttk.Combobox(
            output_frame,
            textvariable=self.output_format_var,
            values=OUTPUT_FORMATS,
            state="readonly",
            width=6,
        )
        self.output_format_combo.grid(row=0, column=1, padx=4, pady=2, sticky="w")
        self.output_format_combo.bind("<<ComboboxSelected>>", self._on_format_change)

        self.speaker_var = tk.BooleanVar(value=self.output_options.speaker_diarization)
        self.speaker_checkbox = tk.Checkbutton(
            output_frame, text="話者識別 (Gemini)", variable=self.speaker_var
        )
        self.speaker_checkbox.grid(row=0, column=2, padx=8, pady=2, sticky="w")

        self.structured_var = tk.BooleanVar(value=self.output_options.structured)
        self.structured_checkbox = tk.Checkbutton(
            output_frame, text="章立て + Markdown (Gemini)", variable=self.structured_var
        )
        self.structured_checkbox.grid(row=0, column=3, padx=8, pady=2, sticky="w")

        self.summary_var = tk.BooleanVar(value=self.output_options.summary)
        self.summary_checkbox = tk.Checkbutton(
            output_frame, text="要約・TODO付与 (Gemini)", variable=self.summary_var
        )
        self.summary_checkbox.grid(row=0, column=4, padx=8, pady=2, sticky="w")

        self.status_bar = StatusBar(self.window, "😀 準備完了")

    def _on_format_change(self, _event=None):
        """字幕形式を選んだら、対応モデルが選択中か警告（バリデーションは実行時に行う）"""
        fmt = self.output_format_var.get()
        if fmt == FORMAT_TXT:
            return
        profile = self.profile_registry.find(self.profile_var.get())
        if profile is None:
            return
        if profile.model not in SUBTITLE_CAPABLE_MODELS:
            self.set_status(
                f"⚠ {fmt.upper()}形式は whisper-1 のみ対応です（実行時にエラーになります）"
            )

    def _on_profile_change(self, _event=None):
        self._sync_option_states()

    def _sync_option_states(self):
        """選択中プロファイルに応じて出力オプションのウィジェットを有効/無効にする"""
        profile = self.profile_registry.find(self.profile_var.get())
        is_google = profile is not None and profile.provider == "google"
        subtitle_capable = profile is not None and profile.model in SUBTITLE_CAPABLE_MODELS

        # 字幕形式（SRT/VTT）は whisper-1 のみ。それ以外では候補から除外し、
        # 既に選択されていた場合は txt に戻す
        allowed_formats = list(OUTPUT_FORMATS) if subtitle_capable else [FORMAT_TXT]
        self.output_format_combo.config(values=allowed_formats)
        if self.output_format_var.get() not in allowed_formats:
            self.output_format_var.set(FORMAT_TXT)

        # Gemini限定オプションは google プロバイダ以外でグレーアウト
        gemini_state = "normal" if is_google else "disabled"
        self.speaker_checkbox.config(state=gemini_state)
        self.structured_checkbox.config(state=gemini_state)
        self.summary_checkbox.config(state=gemini_state)

    def _collect_output_options(self) -> OutputOptions:
        return OutputOptions(
            output_format=self.output_format_var.get() or FORMAT_TXT,
            timestamp=self.timestamp_flag.get(),
            speaker_diarization=self.speaker_var.get(),
            structured=self.structured_var.get(),
            summary=self.summary_var.get(),
        )

    def _validate_output_options(self, profile, options: OutputOptions) -> str | None:
        """組み合わせの妥当性を確認。問題があれば警告メッセージを返す"""
        if options.is_subtitle() and profile.model not in SUBTITLE_CAPABLE_MODELS:
            return (
                f"{options.output_format.upper()} 形式は whisper-1 のみ対応です。"
                f"現在のモデル「{profile.model}」では生成できません。"
            )

        gemini_only_flags = []
        if options.speaker_diarization:
            gemini_only_flags.append("話者識別")
        if options.structured:
            gemini_only_flags.append("章立て + Markdown")
        if options.summary:
            gemini_only_flags.append("要約・TODO付与")

        if gemini_only_flags and profile.provider != "google":
            return (
                "次のオプションは Gemini プロバイダ専用です: "
                + ", ".join(gemini_only_flags)
                + f"\n現在のプロバイダ「{profile.provider}」では無視されます。続行しますか？"
            )
        return None

    def _refresh_profile_dropdown(self):
        names = self.profile_registry.names()
        self.profile_dropdown["values"] = names

        if names:
            current = self.profile_registry.selected if self.profile_registry.selected in names else names[0]
            self.profile_var.set(current)
        else:
            self.profile_var.set("")

    def _update_status_for_selected_profile(self):
        profile = self.profile_registry.selected_profile()
        if profile is None or not profile.api_key:
            self.set_status("😗 設定からモデルとAPIキーを登録してください")
        else:
            self.set_status(f"😀 モデル「{profile.name}」を読み込みました")

    def open_settings(self):
        SettingsDialog(self.window, self.profile_registry, on_save=self._on_settings_saved)

    def _on_settings_saved(self, registry: ProfileRegistry):
        self.profile_registry = registry
        self._refresh_profile_dropdown()
        # 旧 selected が消えていたら現在の選択値で更新
        self.profile_registry.select(self.profile_var.get() or None)
        self._sync_option_states()
        self._update_status_for_selected_profile()
        self.save_settings(persist_only=True)

    def drop(self, event):
        if sys.flags.debug:
            print(event)
        self.file_path_display.delete("1.0", tk.END)
        replaced = self.replace_irregular_char(event.data)
        self.file_path_display.insert(tk.END, replaced)

        filebody = replaced.split("/")[-1]
        self.set_status(f"😀 ファイルを選択しました: {filebody}")

    def replace_irregular_char(self, text):
        text = text.replace("\\", "/")
        text = text.replace("{", "")
        text = text.replace("}", "")
        return text

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

    def save_settings(self, persist_only: bool = False) -> bool:
        if not persist_only:
            self.load_from_widgets()

        # ウィンドウ位置・サイズ
        self.config["DEFAULT"]["x"] = str(self.window.winfo_x())
        self.config["DEFAULT"]["y"] = str(self.window.winfo_y())
        self.config["DEFAULT"]["width"] = str(self.window.winfo_width())
        self.config["DEFAULT"]["height"] = str(self.window.winfo_height())

        self.config["DEFAULT"]["flag_silence_removal"] = str(self.flag_silence_removal)
        self.config["DEFAULT"]["keep_silenced"] = str(self.keep_silence_removed)
        self.config["DEFAULT"]["result_encoding"] = self.result_encoding

        # 出力オプションを保存（timestamp_flag を含む）
        self._collect_output_options().save(self.config)

        # 選択中プロファイルを反映してから保存
        selected_name = self.profile_var.get().strip()
        if selected_name:
            self.profile_registry.select(selected_name)
        self.profile_registry.save(self.config)

        with open("config.ini", "w", encoding="UTF-8") as configfile:
            self.config.write(configfile)

        return True

    def run_transcribe(self):
        if self.ffmpeg_installed is False:
            self.set_status("😮 ffmpegをインストールしてください")
            return

        if self.file_path_display.get("1.0", tk.END).strip() == "":
            self.set_status("😮 ファイルが未選択です")
            return

        selected_name = self.profile_var.get().strip()
        if not selected_name:
            self.set_status("😮 設定からモデルを登録してください")
            messagebox.showwarning("モデル未設定", "「設定...」からモデルとAPIキーを登録してください。", parent=self.window)
            return

        self.profile_registry.select(selected_name)
        profile = self.profile_registry.selected_profile()
        if profile is None or not profile.api_key:
            self.set_status("😮‍💨 選択されたモデルのAPIキーが未設定です")
            return

        options = self._collect_output_options()
        warning = self._validate_output_options(profile, options)
        if warning is not None:
            if options.is_subtitle() and profile.model not in SUBTITLE_CAPABLE_MODELS:
                self.set_status("😮 " + warning.split("\n")[0])
                messagebox.showerror("出力形式エラー", warning, parent=self.window)
                return
            if not messagebox.askyesno("確認", warning, parent=self.window):
                return

        self.output_options = options
        self.save_settings()
        self.load_from_widgets()

        file_path = self.get_filepath()

        controller = self.make_transcription_controller(profile, file_path, options)
        controller.result_encoding = self.result_encoding
        controller.set_debug_options(self.debug_options)

        if controller.check_api_token() is False:
            self.set_status("😮‍💨 APIトークンが無効です")
            return

        filebody = file_path.split("/")[-1]
        self.set_status(f"😆 開始します: {filebody}", ButtonState.DISABLE)

        controller.transcribe_audio(self.flag_silence_removal)

    def get_filepath(self):
        file_path_display_content = self.file_path_display.get("1.0", tk.END)
        file_path = file_path_display_content.strip()
        return file_path

    def make_transcription_controller(self, profile, file_path, output_options):
        controller = TranscriptionController(profile, file_path, output_options=output_options)

        if self.config["DEFAULT"].get("keep_silenced", "False") == "True":
            controller.keep_silence_removed_files = True

        if self.prompt is not None:
            controller.set_prompt(self.prompt)

        controller.set_status_function = self.set_status

        return controller

    def on_closing(self):
        self.save_settings()
        self.window.destroy()

    def error_process(self, error):
        status_code = error.status_code
        message = error.body["message"]

        if status_code == 401:
            self.set_status("😫 APIトークンが無効です")
        else:
            self.set_status(f"😫 エラーです: {message}")
            if self.debug_options.export_errorlog:
                file_path = self.get_filepath()
                TranscriptionController.output(
                    file_path,
                    transcription=message,
                    encoding=self.result_encoding,
                    postfix="_errorlog",
                    extension="txt",
                )

    def load_from_widgets(self):
        self.flag_silence_removal = self.silence_removal_flag.get()
