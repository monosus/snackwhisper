import os
import sys
from typing import Callable
from lib.debug_options import DebugOptions
from lib.status_bar import StatusBar
from lib.constants import DEFAULT_SETTINGS, ButtonState
from lib.audio_silencer import AudioSilencer
from lib.whisper_caller import WhisperTranscriptionCaller
from threading import Thread


class TranscriptionController:
    def __init__(self, api_key: str, audio_file: str, timestamp_flag: bool):
        self.api_key = api_key
        self.audio_file = audio_file
        self.timestamp_flag = timestamp_flag

        self.transcription = ""
        self.language = "ja"
        self.model = (
            # "whisper-1"  # ・gpt-4o-mini-transcribe / gpt-4o-transcribe / whisper-1
            "gpt-4o-mini-transcribe"  # ・gpt-4o-mini-transcribe / gpt-4o-transcribe / whisper-1
            # "gpt-4o-transcribe"  # ・gpt-4o-mini-transcribe / gpt-4o-transcribe / whisper-1
        )
        self.prompt = None
        self.keep_silence_removed_files = False

        # 出力エンコーディングのデフォルトを指定
        self.result_encoding = DEFAULT_SETTINGS.RESULT_ENCODING
        self.set_status_function: Callable[[str, ButtonState], None] | None = None
        self.debug_options = DebugOptions()

    def set_debug_options(self, options: DebugOptions):
        self.debug_options = options

        # エラーの際にテキストファイルを出力する
        self.export_errorlog = options.export_errorlog

        # 音声ファイルを分割する秒数（0のときは内部で算出する）
        self.split_segment_sec: int = options.split_segment_sec
        self.dry_run = options.dry_run

    def set_prompt(self, prompt: str):
        if prompt is not None:
            self.prompt = prompt

    def set_stauts_bar(self, statusbar: StatusBar):
        self.status_bar = statusbar

    def set_status(self, message: str, button_state: ButtonState = ButtonState.NONE):
        """ステータスバーにメッセージを表示する

        Args:
            message (str): ステータスバーに表示するメッセージ
            button_state (ButtonState, optional): ボタンの状態を指定します。デフォルトはButtonState.NONEです。
        """
        if self.set_status_function is not None:
            self.set_status_function(message, button_state)

    # 音声書き起こしを実行
    def transcribe_audio(self, flag_silence_removal: bool = False):

        # 別スレッドで音声抽出と静音除去を実行
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
                    )

                if sys.flags.debug:
                    print(e)
                return

            self.set_status("😇 ファイルを保存します")

            saved_file = saved_file.split("/")[-1]
            self.set_status(f"🤩 完了しました: {saved_file}", ButtonState.RELEASE)

        # 音声抽出と静音除去を実行
        def silence_and_transcribe():
            self.set_status("😇 音声抽出と静音除去を処理しています…")

            silenced_files: list[str] = []
            if self.dry_run:
                return self.output(
                    self.audio_file,
                    transcription="Dry Run",
                    postfix="_dryrun",
                    encoding=self.result_encoding,
                )
            else:
                silencer = AudioSilencer(self.audio_file)
                silencer.flag_silence_removal = (
                    flag_silence_removal  # 静音除去フラグを設定
                )
                silenced_files = silencer.exec()

                if self.keep_silence_removed_files:
                    # silenced_filesをすべて入力ファイルと同じディレクトリにコピーする
                    input_file_path = os.path.dirname(self.audio_file)
                    for silenced_file in silenced_files:
                        copy_file(silenced_file, input_file_path)

            self.transcriptor.set_model(self.model)
            msg = f"😇 WhisperAPI (model: {self.model}) を呼び出しています…"
            self.set_status(msg)
            transcription = self.transcriptor.transcribe_audio_files(silenced_files)

            # return self.output(transcription=transcription)
            return self.output(
                self.audio_file,
                transcription=transcription.transcription,
                encoding=self.result_encoding,
            )

        # Windows / Mac / Linuxでのファイルコピー処理
        def copy_file(src: str, dst: str):
            import shutil

            if sys.platform == "win32":  # Windows
                shutil.copy(src, dst)
            elif sys.platform == "darwin":  # Mac
                shutil.copy2(src, dst)
            elif sys.platform == "linux":  # Linux
                shutil.copy2(src, dst)

        # デバッグ時はスリープしてデバッグしやすくする
        def sleep_for_debugging():
            import time

            time.sleep(5)
            return "[DEBUG_MODE]"

        thread = Thread(target=handling_transcribe_audio)
        thread.start()

    @staticmethod
    def output(
        audio_file, transcription: str, encoding: str = "UTF-8", postfix: str = ""
    ):
        # 文字起こしの保存設定
        input_file_path = os.path.dirname(audio_file)
        input_file_body = os.path.basename(os.path.splitext(audio_file)[0])
        output_file_name = os.path.join(
            input_file_path, input_file_body.replace(".", "_") + postfix + ".txt"
        )

        # Save transcription to TXT file
        if sys.flags.debug:
            print("==== Save transcription to TXT file")
        with open(output_file_name, "w", encoding=encoding) as f:
            f.write(transcription)

        if sys.flags.debug:
            print(f"Transcription saved to: [{output_file_name}]")
        return output_file_name

    def check_api_token(self):
        # APIトークンの有効性を確認
        self.set_status("😇 APIトークンを確認しています…")
        self.transcriptor = WhisperTranscriptionCaller(
            self.api_key, self.timestamp_flag
        )
        self.transcriptor.set_options(self.debug_options)

        if self.prompt is not None:
            self.transcriptor.set_prompt(self.prompt)

        return self.transcriptor.check_api_token()
