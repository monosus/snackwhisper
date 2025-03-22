import datetime
import os
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from lib.debug_options import DebugOptions
from openai import OpenAI


class Transcription:
    """文字起こし結果を記録するためのクラス"""

    def __init__(self):
        self.transcription = ""
        self.last_timestamp_sec = 0

    def add_transcription(self, text: str, last_timestamp_sec: int):
        """文字起こし結果を追加する"""
        self.transcription += text
        self.last_timestamp_sec = last_timestamp_sec


class WhisperTranscriptionCaller:
    def __init__(self, api_key, timestamp_flag: bool):
        self.api_key = api_key
        self.timestamp_flag = timestamp_flag

        self.transcription = Transcription()
        self.language = "ja"
        self.model = "whisper-1"
        self.prompt = """dictionaryを使って、音声を書き起こしてください。

[dictionary]
清音除去
"""

        # self.client = OpenAI(api_key=api_key)

    def set_options(self, options: DebugOptions):
        self.debug_options = options

        # 音声ファイルを分割する秒数（0のときは内部で算出する）
        self.split_segment_sec = options.split_segment_sec

        # ドライランフラグ
        self.dry_run = options.dry_run

        # コンソール出力
        self.console_out = options.console_out

    def set_model(self, model: str):
        self.model = model

    def set_prompt(self, prompt: str):
        if prompt is not None:
            self.prompt = prompt

    def transcribe_audio_files(
        self, audio_files: list[str], api_key: str | None = None
    ):
        if api_key is None:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = OpenAI(api_key=api_key)

        for audio_file in audio_files:
            # # # Split audio if the file size is over the limit
            if sys.flags.debug:
                print("==== split audio file")

            if (
                self.split_segment_sec > 0
                or os.path.getsize(audio_file) > 20 * 1024 * 1024
            ):  # 20MB以上のとき
                cropped_files = self.split_audio(
                    audio_file, 5 * 1024 * 1024
                )  # 5MBごとに分割
            else:
                cropped_files = [audio_file]

            if sys.flags.debug:
                print(cropped_files)

            for cropped_file in cropped_files:
                # self.transcription += self.transcribe_single_file(cropped_file)
                self.transcribe_single_file(cropped_file)

        return self.transcription

    def transcribe_single_file(self, audio_file):
        if self.console_out:
            print("transcribe_single_file(): " + audio_file)

        with open(str(audio_file), "rb") as f:
            if self.timestamp_flag:
                self.create_with_timestamp(f)
            else:
                self.create(f)

            if self.console_out:
                print(self.transcription.transcription)

            return self.transcription.transcription

    def create_with_timestamp(self, file_handler):
        if self.dry_run:
            print("self.create_with_timestamp(): ")
            transcript = SimpleNamespace()
            transcript.segments = [
                {"start": 0, "end": 5, "text": "これはテストです。"},
                {"start": 5, "end": 10, "text": "これはテストです。"},
                {"start": 10, "end": 15, "text": "これはテストです。"},
            ]
        else:
            transcript = self.client.audio.transcriptions.create(
                model=self.model,
                file=file_handler,
                language=self.language,
                response_format="verbose_json",
                prompt=self.prompt,
            )

        file_start_sec = self.transcription.last_timestamp_sec

        if self.console_out:
            print("segments:" + str(transcript))

        result = ""
        begin_sec = self.transcription.last_timestamp_sec
        last_sec = 0
        for segment in transcript.segments:  # type: ignore
            if self.console_out:
                print("create_with_timestamp(): " + str(segment))

            text = segment["text"]
            endsec = file_start_sec + int(segment["start"])
            last_sec = int(segment["end"])
            timestamp = str(datetime.timedelta(seconds=endsec))
            result += f"[{timestamp}] {text}\n"

        self.transcription.add_transcription(result, begin_sec + last_sec)

        return result

    def create(self, file_handler):

        if self.dry_run:
            print("self.create_with_timestamp(): ")
            transcript = {"text": "これはテストです。"}
        else:
            transcript = self.client.audio.transcriptions.create(
                model=self.model,
                file=file_handler,
                language=self.language,
                response_format="json",
            )

        self.transcription.add_transcription(transcript.text, 0)  # type: ignore
        return transcript.text  # type: ignore

    # ffmpegを使ってファイルを分割する
    # max_size: 分割するファイルの最大サイズ（Byte）
    def split_audio(self, input_file, max_size):
        startupinfo = None
        if os.name == "nt":  # Windowsの場合
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        target_duration = self.split_segment_sec

        if self.dry_run:
            target_duration = 5
        elif target_duration == 0:
            duration_command = [
                "ffprobe",
                "-i",
                input_file,
                "-show_entries",
                "format=duration",
                "-v",
                "quiet",
                "-of",
                "csv=p=0",
            ]
            duration = float(
                subprocess.check_output(
                    duration_command,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    startupinfo=startupinfo,
                )
                .decode("utf-8")
                .strip()
            )

            size = os.path.getsize(input_file)
            # 音声ファイルのサイズに基づいて、分割するセグメントの目標時間を計算する
            # duration: 音声ファイルの全体の長さ（秒）
            # max_size: 分割するファイルの最大サイズ（Byte）
            # size: 音声ファイルのサイズ（バイト）
            # target_duration: 分割するセグメントの目標時間（秒）
            target_duration = (duration * max_size) // size

        # テンポラリディレクトリを作成
        temp_dir = tempfile.mkdtemp(prefix="splitaudio_")
        # input_path = os.path.dirname(input_file)
        output_workpath = os.path.join(temp_dir, "work")
        os.makedirs(output_workpath, exist_ok=True)
        output_filepath = os.path.join(output_workpath, "split-%03d.mp3")

        if self.console_out:
            print("==== split audio file: " + input_file)
            print("==== target_duration: " + str(target_duration))
            print("==== output_filepath: " + output_filepath)

        command = [
            "ffmpeg",
            "-i",
            input_file,
            "-f",
            "segment",
            "-segment_time",
            str(target_duration),
            "-acodec",
            "copy",
            str(output_filepath),
            "-loglevel",
            "quiet",
        ]

        if self.dry_run:
            print(" ".join(command))
            return []
        else:
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

    def check_api_token(self) -> bool:
        # APIトークンの有効性を確認
        self.client = OpenAI(api_key=self.api_key)

        # テンポラリファイルを作成
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file = os.path.join(temp_dir, "temp_file.wav")
            with open(temp_file, "wb") as fh:
                fh.write(b"")
            with open(temp_file, "rb") as fh:
                # APIキーの有効性を確認するために、簡単なAPIリクエストを行う
                try:
                    self.client.audio.transcriptions.create(
                        model=self.model,
                        file=fh,
                        language=self.language,
                        response_format="json",
                    )
                except Exception as e:
                    if e.code == "invalid_api_key":  # type: ignore
                        if sys.flags.debug:
                            print("APIキーが無効です。エラーメッセージ:", e)
                        return False
        return True
