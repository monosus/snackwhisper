import datetime
import os
import subprocess
import sys
import tempfile
from openai import OpenAI


class WhisperTranscriptionCaller:
    def __init__(self, api_key, timestamp_flag: bool):
        self.api_key = api_key
        self.timestamp_flag = timestamp_flag

        self.transcription = ""
        self.language = "ja"
        self.model = "whisper-1"
        self.prompt = """dictionaryを使って、音声を書き起こしてください。

[dictionary]
清音除去
"""

        # self.client = OpenAI(api_key=api_key)

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
            if os.path.getsize(audio_file) > 20 * 1024 * 1024:
                cropped_files = self.split_audio(audio_file, 5 * 1024 * 1024)
            else:
                cropped_files = [audio_file]

            if sys.flags.debug:
                print(cropped_files)

            for cropped_file in cropped_files:
                self.transcription += self.transcribe_single_file(cropped_file)

        return self.transcription

    def transcribe_single_file(self, audio_file):
        with open(str(audio_file), "rb") as f:
            if self.timestamp_flag:
                transcript = self.create_with_timestamp(f)
            else:
                transcript = self.create(f)

            if sys.flags.debug:
                print(transcript)
            return transcript

    def create_with_timestamp(self, file_handler):
        print(self.prompt)

        transcript = self.client.audio.transcriptions.create(
            model=self.model,
            file=file_handler,
            language=self.language,
            response_format="verbose_json",
            prompt=self.prompt,
        )

        result = ""
        for segment in transcript.segments:  # type: ignore
            text = segment["text"]
            endsec = int(segment["start"])
            timestamp = str(datetime.timedelta(seconds=endsec))
            result += f"[{timestamp}] {text}\n"

        return result

    def create(self, file_handler):
        transcript = self.client.audio.transcriptions.create(
            model=self.model,
            file=file_handler,
            language=self.language,
            response_format="json",
        )
        return transcript.text

    def split_audio(self, input_file, max_size):
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
            subprocess.check_output(duration_command).decode("utf-8").strip()
        )

        size = os.path.getsize(input_file)
        target_duration = (duration * max_size) // size

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
            "work/split-%03d.mp3",
            "-loglevel",
            "quiet",
        ]
        subprocess.run(command, check=True)

        split_files = []
        for filename in os.listdir("work"):
            if filename.startswith("split") and filename.endswith(".mp3"):
                split_files.append(os.path.join("work", filename))

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
