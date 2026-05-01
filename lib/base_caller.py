import os
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from lib.debug_options import DebugOptions
from lib.output_options import OutputOptions


class Transcription:
    """文字起こし結果を記録するためのクラス"""

    def __init__(self):
        self.transcription = ""
        self.last_timestamp_sec = 0

    def add_transcription(self, text: str, last_timestamp_sec: int):
        self.transcription += text
        self.last_timestamp_sec = last_timestamp_sec


class BaseTranscriptionCaller(ABC):
    """各プロバイダの文字起こしAPI呼び出しの基底クラス"""

    def __init__(self, api_key: str, timestamp_flag: bool):
        self.api_key = api_key
        self.timestamp_flag = timestamp_flag

        self.transcription = Transcription()
        self.language = "ja"
        self.model = ""
        self.prompt = """dictionaryを使って、音声を書き起こしてください。

[dictionary]
清音除去
"""
        self.debug_options = DebugOptions()
        self.output_options = OutputOptions()
        self.split_segment_sec = 0
        self.dry_run = False
        self.console_out = False

    def set_options(self, options: DebugOptions):
        self.debug_options = options
        self.split_segment_sec = options.split_segment_sec
        self.dry_run = options.dry_run
        self.console_out = options.console_out

    def set_output_options(self, options: OutputOptions):
        self.output_options = options

    def set_model(self, model: str):
        self.model = model

    def set_prompt(self, prompt: str):
        if prompt is not None:
            self.prompt = prompt

    def transcribe_audio_files(self, audio_files: list[str]):
        for audio_file in audio_files:
            if sys.flags.debug:
                print("==== split audio file")

            if (
                self.split_segment_sec > 0
                or os.path.getsize(audio_file) > 20 * 1024 * 1024
            ):
                cropped_files = self.split_audio(audio_file, 5 * 1024 * 1024)
            else:
                cropped_files = [audio_file]

            if sys.flags.debug:
                print(cropped_files)

            for cropped_file in cropped_files:
                self._transcribe_single_file(cropped_file)

        self.finalize()
        return self.transcription

    def finalize(self) -> str:
        """全ファイル処理後の後処理（要約集約など）。サブクラスで必要に応じてオーバーライド"""
        return self.transcription.transcription

    @abstractmethod
    def _transcribe_single_file(self, audio_file: str) -> str:
        """1ファイルを文字起こしして self.transcription に追記する"""

    @abstractmethod
    def check_api_token(self) -> bool:
        """APIトークンが有効か確認する"""

    # ffmpegを使ってファイルを分割する
    def split_audio(self, input_file: str, max_size: int):
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        target_duration = self.split_segment_sec

        if self.dry_run:
            target_duration = 5
        elif target_duration == 0:
            duration_command = [
                "ffprobe", "-i", input_file,
                "-show_entries", "format=duration",
                "-v", "quiet", "-of", "csv=p=0",
            ]
            duration = float(
                subprocess.check_output(
                    duration_command,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    startupinfo=startupinfo,
                ).decode("utf-8").strip()
            )
            size = os.path.getsize(input_file)
            target_duration = (duration * max_size) // size

        temp_dir = tempfile.mkdtemp(prefix="splitaudio_")
        output_workpath = os.path.join(temp_dir, "work")
        os.makedirs(output_workpath, exist_ok=True)
        output_filepath = os.path.join(output_workpath, "split-%03d.mp3")

        if self.console_out:
            print("==== split audio file: " + input_file)
            print("==== target_duration: " + str(target_duration))
            print("==== output_filepath: " + output_filepath)

        command = [
            "ffmpeg", "-i", input_file,
            "-f", "segment",
            "-segment_time", str(target_duration),
            "-acodec", "copy",
            str(output_filepath),
            "-loglevel", "quiet",
        ]

        if self.dry_run:
            print(" ".join(command))
            return []

        subprocess.run(
            command,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            startupinfo=startupinfo,
        )

        split_files = []
        for filename in os.listdir(output_workpath):
            if filename.startswith("split") and filename.endswith(".mp3"):
                split_files.append(os.path.join(output_workpath, filename))

        return sorted(split_files)
