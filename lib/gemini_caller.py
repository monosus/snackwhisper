import datetime
import os
import re
import sys
from lib.base_caller import BaseTranscriptionCaller


class GeminiTranscriptionCaller(BaseTranscriptionCaller):
    """Google Gemini APIによる音声文字起こし"""

    TIMESTAMP_PROMPT = (
        "以下の音声を日本語で文字起こししてください。"
        "各発話の先頭に [MM:SS] 形式のタイムスタンプを付与し、"
        "解説や補足は一切付けず、文字起こし結果のみを出力してください。\n"
    )

    PLAIN_PROMPT = (
        "以下の音声を日本語で文字起こししてください。"
        "解説や補足は一切付けず、文字起こし結果のみを出力してください。\n"
    )

    def __init__(self, api_key: str, timestamp_flag: bool):
        super().__init__(api_key, timestamp_flag)
        self.model = "gemini-2.5-flash"
        self.client = None

    def _ensure_client(self):
        if self.client is None:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)

    def _build_instruction(self) -> str:
        base = self.TIMESTAMP_PROMPT if self.timestamp_flag else self.PLAIN_PROMPT
        if self.prompt:
            base += "\n参考辞書:\n" + self.prompt
        return base

    def _transcribe_single_file(self, audio_file: str) -> str:
        if self.dry_run:
            text = "[00:00] これはテストです。\n" if self.timestamp_flag else "これはテストです。"
            self._append_with_offset(text)
            return text

        self._ensure_client()
        assert self.client is not None

        if self.console_out:
            print("transcribe_single_file(): " + audio_file)

        uploaded = self.client.files.upload(file=audio_file)
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[self._build_instruction(), uploaded],
            )
        finally:
            try:
                self.client.files.delete(name=uploaded.name)
            except Exception:
                if sys.flags.debug:
                    print("Geminiアップロードファイルの削除に失敗しました")

        text = (response.text or "").strip() + "\n"

        if self.console_out:
            print(text)

        self._append_with_offset(text)
        return text

    def _append_with_offset(self, text: str) -> None:
        """タイムスタンプ付きの場合は前ファイルの末尾秒数を加算してから追記する"""
        offset = self.transcription.last_timestamp_sec
        last_sec_in_chunk = 0

        if self.timestamp_flag and offset > 0:
            shifted_lines = []
            for line in text.splitlines():
                m = re.match(r"^\[(\d{1,2}):(\d{2})\]\s*(.*)$", line)
                if m:
                    minutes, seconds, body = int(m.group(1)), int(m.group(2)), m.group(3)
                    sec = minutes * 60 + seconds
                    last_sec_in_chunk = max(last_sec_in_chunk, sec)
                    total = offset + sec
                    timestamp = str(datetime.timedelta(seconds=total))
                    shifted_lines.append(f"[{timestamp}] {body}")
                else:
                    shifted_lines.append(line)
            text = "\n".join(shifted_lines) + "\n"
        elif self.timestamp_flag:
            for line in text.splitlines():
                m = re.match(r"^\[(\d{1,2}):(\d{2})\]", line)
                if m:
                    sec = int(m.group(1)) * 60 + int(m.group(2))
                    last_sec_in_chunk = max(last_sec_in_chunk, sec)

        self.transcription.add_transcription(text, offset + last_sec_in_chunk)

    def check_api_token(self) -> bool:
        try:
            self._ensure_client()
            assert self.client is not None
            list(self.client.models.list())
            return True
        except Exception as e:
            if sys.flags.debug:
                print("Gemini APIキー確認に失敗:", e)
            msg = str(e).lower()
            if "api key" in msg or "unauthenticated" in msg or "permission" in msg:
                return False
            # ネットワーク等の一時的失敗ならTrue扱い（呼び出し時に再試行される）
            return True
