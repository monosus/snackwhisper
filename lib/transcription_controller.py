import datetime
import json
import os
import re
import sys
from typing import Callable
from lib.debug_options import DebugOptions
from lib.status_bar import StatusBar
from lib.constants import DEFAULT_SETTINGS, ButtonState
from lib.audio_silencer import AudioSilencer
from lib.base_caller import BaseTranscriptionCaller
from lib.whisper_caller import WhisperTranscriptionCaller
from lib.gemini_caller import GeminiTranscriptionCaller
from lib.elevenlabs_caller import ElevenLabsTranscriptionCaller
from lib.model_profile import ModelProfile
from lib.output_options import FORMAT_JSON, FORMAT_MD, OutputOptions
from threading import Thread


_TS_LINE = re.compile(r"^\[(?:(\d+):)?(\d{1,2}):(\d{2})\]\s*(.*)$")


def format_output_text(transcription_text: str, options: OutputOptions, profile: ModelProfile, source_file: str) -> str:
    """出力形式に応じて最終的に書き出すテキストを組み立てる。
    SRT/VTT は caller 側で完成済みなのでそのまま返す。"""

    if options.output_format == FORMAT_MD:
        header = (
            f"# 文字起こし: {os.path.basename(source_file)}\n\n"
            f"- モデル: `{profile.provider}` / `{profile.model}`\n"
            f"- 生成日時: {datetime.datetime.now().isoformat(timespec='seconds')}\n\n---\n\n"
        )
        return header + transcription_text

    if options.output_format == FORMAT_JSON:
        envelope = {
            "metadata": {
                "source_file": source_file,
                "provider": profile.provider,
                "model": profile.model,
                "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "options": {
                    "timestamp": options.timestamp,
                    "speaker_diarization": options.speaker_diarization,
                    "structured": options.structured,
                    "summary": options.summary,
                },
            },
            "text": transcription_text,
        }
        if options.timestamp:
            envelope["segments"] = _parse_timestamp_segments(transcription_text)
        return json.dumps(envelope, ensure_ascii=False, indent=2)

    return transcription_text


def _parse_timestamp_segments(text: str) -> list[dict]:
    """`[H:MM:SS] 本文` 形式の行をセグメント配列に変換する"""
    segments: list[dict] = []
    for line in text.splitlines():
        m = _TS_LINE.match(line)
        if not m:
            continue
        h = int(m.group(1) or 0)
        mm = int(m.group(2))
        ss = int(m.group(3))
        segments.append({
            "start_sec": h * 3600 + mm * 60 + ss,
            "text": m.group(4),
        })
    return segments


def build_caller(profile: ModelProfile, output_options: OutputOptions) -> BaseTranscriptionCaller:
    timestamp_flag = output_options.needs_timestamps_internally()
    if profile.provider == "google":
        caller: BaseTranscriptionCaller = GeminiTranscriptionCaller(profile.api_key, timestamp_flag)
    elif profile.provider == "elevenlabs":
        caller = ElevenLabsTranscriptionCaller(profile.api_key, timestamp_flag)
    else:
        caller = WhisperTranscriptionCaller(profile.api_key, timestamp_flag)
    caller.set_model(profile.model)
    caller.set_output_options(output_options)
    return caller


class TranscriptionController:
    def __init__(self, profile: ModelProfile, audio_file: str, output_options: OutputOptions):
        self.profile = profile
        self.audio_file = audio_file
        self.output_options = output_options

        self.transcription = ""
        self.language = "ja"
        self.prompt = None
        self.keep_silence_removed_files = False

        self.result_encoding = DEFAULT_SETTINGS.RESULT_ENCODING
        self.set_status_function: Callable[[str, ButtonState], None] | None = None
        self.debug_options = DebugOptions()

    def set_debug_options(self, options: DebugOptions):
        self.debug_options = options
        self.export_errorlog = options.export_errorlog
        self.split_segment_sec: int = options.split_segment_sec
        self.dry_run = options.dry_run

    def set_prompt(self, prompt: str):
        if prompt is not None:
            self.prompt = prompt

    def set_stauts_bar(self, statusbar: StatusBar):
        self.status_bar = statusbar

    def set_status(self, message: str, button_state: ButtonState = ButtonState.NONE):
        if self.set_status_function is not None:
            self.set_status_function(message, button_state)

    def transcribe_audio(self, flag_silence_removal: bool = False):

        def handling_transcribe_audio():
            try:
                if sys.flags.debug:
                    saved_file = sleep_for_debugging()
                else:
                    saved_file = silence_and_transcribe()
            except Exception as e:
                self.set_status(f"😫 エラーです: {e}", ButtonState.RELEASE)
                if self.export_errorlog:
                    self.output(
                        self.audio_file,
                        transcription=str(e),
                        encoding=self.result_encoding,
                        postfix="_errorlog",
                        extension="txt",
                    )

                if sys.flags.debug:
                    print(e)
                return

            self.set_status("😇 ファイルを保存します")

            saved_file = saved_file.split("/")[-1]
            self.set_status(f"🤩 完了しました: {saved_file}", ButtonState.RELEASE)

        def silence_and_transcribe():
            self.set_status("😇 音声抽出と静音除去を処理しています…")

            silenced_files: list[str] = []
            if self.dry_run:
                return self.output(
                    self.audio_file,
                    transcription="Dry Run",
                    postfix="_dryrun",
                    encoding=self.result_encoding,
                    extension=self.output_options.file_extension(),
                )
            else:
                silencer = AudioSilencer(self.audio_file)
                silencer.flag_silence_removal = flag_silence_removal
                silenced_files = silencer.exec()

                if self.keep_silence_removed_files:
                    input_file_path = os.path.dirname(self.audio_file)
                    for silenced_file in silenced_files:
                        copy_file(silenced_file, input_file_path)

            msg = (
                f"😇 {self.profile.provider} ({self.profile.model}) で文字起こし中…"
            )
            self.set_status(msg)
            transcription = self.transcriptor.transcribe_audio_files(silenced_files)

            formatted = format_output_text(
                transcription.transcription,
                self.output_options,
                self.profile,
                self.audio_file,
            )

            return self.output(
                self.audio_file,
                transcription=formatted,
                encoding=self.result_encoding,
                extension=self.output_options.file_extension(),
            )

        def copy_file(src: str, dst: str):
            import shutil

            if sys.platform == "win32":
                shutil.copy(src, dst)
            elif sys.platform == "darwin":
                shutil.copy2(src, dst)
            elif sys.platform == "linux":
                shutil.copy2(src, dst)

        def sleep_for_debugging():
            import time

            time.sleep(5)
            return "[DEBUG_MODE]"

        thread = Thread(target=handling_transcribe_audio)
        thread.start()

    @staticmethod
    def output(
        audio_file,
        transcription: str,
        encoding: str = "UTF-8",
        postfix: str = "",
        extension: str = "txt",
    ):
        input_file_path = os.path.dirname(audio_file)
        input_file_body = os.path.basename(os.path.splitext(audio_file)[0])
        output_file_name = os.path.join(
            input_file_path,
            input_file_body.replace(".", "_") + postfix + "." + extension,
        )

        if sys.flags.debug:
            print("==== Save transcription to TXT file")
        with open(output_file_name, "w", encoding=encoding) as f:
            f.write(transcription)

        if sys.flags.debug:
            print(f"Transcription saved to: [{output_file_name}]")
        return output_file_name

    def check_api_token(self):
        self.set_status("😇 APIトークンを確認しています…")
        self.transcriptor = build_caller(self.profile, self.output_options)
        self.transcriptor.set_options(self.debug_options)

        if self.prompt is not None:
            self.transcriptor.set_prompt(self.prompt)

        return self.transcriptor.check_api_token()
