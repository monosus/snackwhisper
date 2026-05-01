import datetime
import os
import re
import sys
from lib.base_caller import BaseTranscriptionCaller


class GeminiTranscriptionCaller(BaseTranscriptionCaller):
    """Google Gemini APIによる音声文字起こし"""

    def __init__(self, api_key: str, timestamp_flag: bool):
        super().__init__(api_key, timestamp_flag)
        self.model = "gemini-2.5-flash"
        self.client = None
        self._summary_buffer: list[str] = []  # 各分割ファイルの要約結果を集約

    def _ensure_client(self):
        if self.client is None:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)

    def _build_instruction(self) -> str:
        opts = self.output_options
        sections: list[str] = ["以下の音声を日本語で文字起こししてください。"]

        if opts.speaker_diarization:
            sections.append(
                "発話ごとに話者を識別し、`話者A:` `話者B:` のように行頭にラベルを付けてください。"
                "同一話者と判断した発話には同じラベルを使ってください。"
            )

        if opts.timestamp:
            sections.append(
                "各発話（または話者交替）の先頭に [MM:SS] 形式のタイムスタンプを付与してください。"
            )

        if opts.structured:
            sections.append(
                "話題が大きく変わる箇所で `## 見出し` のMarkdown見出しを挿入し、"
                "適切に段落・箇条書きを使って整形してください。"
                "ただし元の発話内容は改変せず、フィラーの除去と読点・改行の整理にとどめてください。"
            )

        if opts.summary:
            sections.append(
                "文字起こし本文の後ろに、以下のセクションを必ず付け加えてください:\n"
                "  `--- SUMMARY ---` 行の下に3〜5行の要約\n"
                "  `--- ACTION ITEMS ---` 行の下にTODO・決定事項を箇条書き（無ければ「特になし」）"
            )

        sections.append(
            "上記以外の解説や前置き、Markdownのコードフェンスは付けず、結果のみを出力してください。"
        )

        if self.prompt:
            sections.append("参考辞書:\n" + self.prompt)

        return "\n\n".join(sections)

    def _transcribe_single_file(self, audio_file: str) -> str:
        if self.dry_run:
            text = self._dry_run_text()
            self._append_chunk(text)
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

        text = (response.text or "").strip()

        if self.console_out:
            print(text)

        self._append_chunk(text)
        return text

    def _dry_run_text(self) -> str:
        opts = self.output_options
        head = "[00:00] " if opts.timestamp else ""
        spk = "話者A: " if opts.speaker_diarization else ""
        body = f"{head}{spk}これはテストです。"
        if opts.summary:
            body += "\n\n--- SUMMARY ---\nテスト要約。\n--- ACTION ITEMS ---\n- 特になし"
        return body

    def _append_chunk(self, text: str) -> None:
        """summary/action 部分は末尾に集約、本文はタイムスタンプを補正して追記"""
        body, summary_block = self._split_summary(text)
        if summary_block:
            self._summary_buffer.append(summary_block)

        offset = self.transcription.last_timestamp_sec
        last_sec_in_chunk = 0
        out_lines: list[str] = []

        if self.output_options.timestamp:
            for line in body.splitlines():
                m = re.match(r"^\[(\d{1,2}):(\d{2})\]\s*(.*)$", line)
                if m:
                    minutes, seconds, rest = int(m.group(1)), int(m.group(2)), m.group(3)
                    sec = minutes * 60 + seconds
                    last_sec_in_chunk = max(last_sec_in_chunk, sec)
                    total = offset + sec
                    timestamp = str(datetime.timedelta(seconds=total))
                    out_lines.append(f"[{timestamp}] {rest}")
                else:
                    out_lines.append(line)
            shifted = "\n".join(out_lines).rstrip() + "\n"
        else:
            shifted = body.rstrip() + "\n"

        self.transcription.add_transcription(shifted, offset + last_sec_in_chunk)

    def _split_summary(self, text: str) -> tuple[str, str]:
        """本文と要約セクションを分離する"""
        if not self.output_options.summary:
            return text, ""

        marker = "--- SUMMARY ---"
        idx = text.find(marker)
        if idx == -1:
            return text, ""
        return text[:idx].rstrip(), text[idx:].strip()

    def finalize(self) -> str:
        """全分割ファイル処理後に呼び出し、要約セクションを末尾に追加する"""
        if not self._summary_buffer:
            return self.transcription.transcription

        merged_summary = "\n\n".join(self._summary_buffer)
        if not self.transcription.transcription.endswith("\n"):
            self.transcription.transcription += "\n"
        self.transcription.transcription += "\n" + merged_summary + "\n"
        return self.transcription.transcription

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
            return True
