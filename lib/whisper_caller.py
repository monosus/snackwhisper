import datetime
import os
import sys
import tempfile
from types import SimpleNamespace
from lib.base_caller import BaseTranscriptionCaller, Transcription
from openai import OpenAI


__all__ = ["Transcription", "WhisperTranscriptionCaller"]


class WhisperTranscriptionCaller(BaseTranscriptionCaller):
    def __init__(self, api_key: str, timestamp_flag: bool):
        super().__init__(api_key, timestamp_flag)
        self.model = "whisper-1"
        self.client: OpenAI | None = None

    def _ensure_client(self):
        if self.client is None:
            self.client = OpenAI(api_key=self.api_key)

    def _transcribe_single_file(self, audio_file: str) -> str:
        self._ensure_client()

        if self.console_out:
            print("transcribe_single_file(): " + audio_file)

        with open(str(audio_file), "rb") as f:
            if self.timestamp_flag:
                self._create_with_timestamp(f)
            else:
                self._create(f)

            if self.console_out:
                print(self.transcription.transcription)

            return self.transcription.transcription

    def _create_with_timestamp(self, file_handler):
        if self.dry_run:
            print("self.create_with_timestamp(): ")
            transcript = SimpleNamespace()
            transcript.segments = [
                {"start": 0, "end": 5, "text": "これはテストです。"},
                {"start": 5, "end": 10, "text": "これはテストです。"},
                {"start": 10, "end": 15, "text": "これはテストです。"},
            ]
        else:
            assert self.client is not None
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

    def _create(self, file_handler):
        if self.dry_run:
            print("self.create(): ")
            transcript = SimpleNamespace(text="これはテストです。")
        else:
            assert self.client is not None
            transcript = self.client.audio.transcriptions.create(
                model=self.model,
                file=file_handler,
                language=self.language,
                response_format="json",
            )

        self.transcription.add_transcription(transcript.text, 0)  # type: ignore
        return transcript.text  # type: ignore

    def check_api_token(self) -> bool:
        self._ensure_client()
        assert self.client is not None

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file = os.path.join(temp_dir, "temp_file.wav")
            with open(temp_file, "wb") as fh:
                fh.write(b"")
            with open(temp_file, "rb") as fh:
                try:
                    self.client.audio.transcriptions.create(
                        model=self.model,
                        file=fh,
                        language=self.language,
                        response_format="json",
                    )
                except Exception as e:
                    if getattr(e, "code", None) == "invalid_api_key":
                        if sys.flags.debug:
                            print("APIキーが無効です。エラーメッセージ:", e)
                        return False
        return True
