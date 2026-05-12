import datetime
import os
import re
import sys
import tempfile
from types import SimpleNamespace
from lib.base_caller import BaseTranscriptionCaller, Transcription
from lib.output_options import FORMAT_SRT, FORMAT_VTT
from openai import OpenAI


__all__ = ["Transcription", "WhisperTranscriptionCaller"]


# 字幕形式（SRT/VTT）のタイムコード正規表現
_SRT_TS = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)


class WhisperTranscriptionCaller(BaseTranscriptionCaller):
    def __init__(self, api_key: str, timestamp_flag: bool):
        super().__init__(api_key, timestamp_flag)
        self.model = "whisper-1"
        self.client: OpenAI | None = None
        self._subtitle_cues: list[tuple[float, float, str]] = []  # (start_sec, end_sec, text)

    def _ensure_client(self):
        if self.client is None:
            self.client = OpenAI(api_key=self.api_key)

    def _transcribe_single_file(self, audio_file: str) -> str:
        self._ensure_client()

        if self.console_out:
            print("transcribe_single_file(): " + audio_file)

        with open(str(audio_file), "rb") as f:
            if self.output_options.is_subtitle():
                self._create_subtitle(f)
            elif self.output_options.timestamp:
                self._create_with_timestamp(f)
            else:
                self._create(f)

            if self.console_out:
                print(self.transcription.transcription)

            return self.transcription.transcription

    def _create_with_timestamp(self, file_handler):
        if self.dry_run:
            transcript = SimpleNamespace()
            transcript.segments = [
                SimpleNamespace(start=0, end=5, text="これはテストです。"),
                SimpleNamespace(start=5, end=10, text="これはテストです。"),
                SimpleNamespace(start=10, end=15, text="これはテストです。"),
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
            text = _seg_attr(segment, "text")
            endsec = file_start_sec + int(_seg_attr(segment, "start"))
            last_sec = int(_seg_attr(segment, "end"))
            timestamp = str(datetime.timedelta(seconds=endsec))
            result += f"[{timestamp}] {text}\n"

        self.transcription.add_transcription(result, begin_sec + last_sec)
        return result

    def _create(self, file_handler):
        if self.dry_run:
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

    def _create_subtitle(self, file_handler):
        """SRT/VTT文字列を取得し、ファイル境界をまたぐタイムコードに加算するために
        いったんキューに分解して保持する"""
        offset_sec = float(self.transcription.last_timestamp_sec)

        if self.dry_run:
            text = (
                "1\n00:00:00,000 --> 00:00:05,000\nこれはテストです。\n\n"
                "2\n00:00:05,000 --> 00:00:10,000\nこれはテストです。\n"
            )
        else:
            assert self.client is not None
            response_format = "srt" if self.output_options.output_format == FORMAT_SRT else "vtt"
            text = self.client.audio.transcriptions.create(
                model=self.model,
                file=file_handler,
                language=self.language,
                response_format=response_format,
                prompt=self.prompt,
            )
            if not isinstance(text, str):
                text = getattr(text, "text", str(text))

        cues = self._parse_cues(text)
        last_end = offset_sec
        for start, end, body in cues:
            self._subtitle_cues.append((offset_sec + start, offset_sec + end, body))
            last_end = max(last_end, offset_sec + end)

        self.transcription.add_transcription("", int(last_end))
        return text

    def _parse_cues(self, text: str) -> list[tuple[float, float, str]]:
        cues: list[tuple[float, float, str]] = []
        block_lines: list[str] = []

        def flush(block: list[str]):
            if not block:
                return
            ts_index = -1
            for i, line in enumerate(block):
                if _SRT_TS.search(line):
                    ts_index = i
                    break
            if ts_index == -1:
                return
            m = _SRT_TS.search(block[ts_index])
            if m is None:
                return
            start = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000
            end = int(m.group(5)) * 3600 + int(m.group(6)) * 60 + int(m.group(7)) + int(m.group(8)) / 1000
            body = "\n".join(block[ts_index + 1:]).strip()
            if body:
                cues.append((start, end, body))

        for raw in text.splitlines():
            if raw.strip() == "":
                flush(block_lines)
                block_lines = []
            else:
                block_lines.append(raw)
        flush(block_lines)
        return cues

    def finalize(self) -> str:
        if not self.output_options.is_subtitle():
            return self.transcription.transcription

        if self.output_options.output_format == FORMAT_VTT:
            out_lines = ["WEBVTT", ""]
            for start, end, body in self._subtitle_cues:
                out_lines.append(f"{_format_ts(start, '.')} --> {_format_ts(end, '.')}")
                out_lines.append(body)
                out_lines.append("")
            self.transcription.transcription = "\n".join(out_lines).rstrip() + "\n"
        else:  # SRT
            out_lines = []
            for idx, (start, end, body) in enumerate(self._subtitle_cues, start=1):
                out_lines.append(str(idx))
                out_lines.append(f"{_format_ts(start, ',')} --> {_format_ts(end, ',')}")
                out_lines.append(body)
                out_lines.append("")
            self.transcription.transcription = "\n".join(out_lines).rstrip() + "\n"

        return self.transcription.transcription

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


def _format_ts(seconds: float, ms_sep: str) -> str:
    total_ms = int(round(seconds * 1000))
    h, rem = divmod(total_ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{ms_sep}{ms:03d}"


def _seg_attr(segment, key: str):
    """新APIの Pydantic モデル/旧APIの dict 両方から値を取得"""
    if isinstance(segment, dict):
        return segment[key]
    return getattr(segment, key)
