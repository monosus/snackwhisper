import datetime
import os
import shutil
import sys
import tempfile
from typing import Iterable

from lib.base_caller import BaseTranscriptionCaller
from lib.output_options import FORMAT_VTT


# 沈黙閾値（秒）。タイムスタンプ付きテキスト生成時、これ以上の無音で改行する
_SILENCE_BREAK_SEC = 1.0
# 字幕1キューの目標長（秒）
_CUE_TARGET_SEC = 6.0


class ElevenLabsTranscriptionCaller(BaseTranscriptionCaller):
    """ElevenLabs Scribe (Speech-to-Text) APIによる文字起こし"""

    def __init__(self, api_key: str, timestamp_flag: bool):
        super().__init__(api_key, timestamp_flag)
        self.model = "scribe_v1"
        self.client = None
        # ファイル境界をまたいでも一貫した話者IDマッピングを使う
        self._speaker_label_map: dict[str, str] = {}
        # 字幕用キュー (start_sec, end_sec, body) を蓄積
        self._subtitle_cues: list[tuple[float, float, str]] = []

    @staticmethod
    def _ensure_ascii_path(audio_file: str):
        """日本語などASCII以外を含むパスならASCII名のテンポラリへコピーする。
        戻り値: (アップロードに使うパス, 後始末コールバック)
        """
        try:
            os.fsencode(audio_file).decode("ascii")
            return audio_file, lambda: None
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass

        ext = os.path.splitext(audio_file)[1] or ".mp3"
        fd, ascii_path = tempfile.mkstemp(prefix="elevenlabs_upload_", suffix=ext)
        os.close(fd)
        shutil.copyfile(audio_file, ascii_path)

        def _cleanup():
            try:
                os.unlink(ascii_path)
            except OSError:
                pass

        return ascii_path, _cleanup

    def _ensure_client(self):
        if self.client is None:
            from elevenlabs.client import ElevenLabs
            self.client = ElevenLabs(api_key=self.api_key)

    def _build_request_options(self) -> dict:
        opts = self.output_options
        kwargs: dict = {
            "model_id": self.model,
            "language_code": self.language,
        }

        if opts.speaker_diarization:
            kwargs["diarize"] = True

        # タイムスタンプ・字幕・話者識別のいずれかが必要なら word 単位で取得
        if opts.timestamp or opts.is_subtitle() or opts.speaker_diarization:
            kwargs["timestamps_granularity"] = "word"
        else:
            kwargs["timestamps_granularity"] = "none"

        # prompt を keyterms 配列として渡す（1行1キーターム、最大1000）
        if self.prompt:
            terms = [
                line.strip()
                for line in self.prompt.replace(",", "\n").splitlines()
                if line.strip()
            ]
            if terms:
                kwargs["keyterms"] = terms[:1000]

        return kwargs

    def _transcribe_single_file(self, audio_file: str) -> str:
        if self.dry_run:
            self._render_dry_run()
            return self.transcription.transcription

        self._ensure_client()
        assert self.client is not None

        if self.console_out:
            print("transcribe_single_file(): " + audio_file)

        upload_path, cleanup = self._ensure_ascii_path(audio_file)
        try:
            with open(upload_path, "rb") as fh:
                response = self.client.speech_to_text.convert(
                    file=fh,
                    **self._build_request_options(),
                )
        finally:
            cleanup()

        self._render_response(response)
        return self.transcription.transcription

    def _render_dry_run(self):
        opts = self.output_options
        offset = self.transcription.last_timestamp_sec
        if opts.is_subtitle():
            self._subtitle_cues.append((offset + 0.0, offset + 5.0, "これはテストです。"))
            self.transcription.add_transcription("", offset + 5)
            return
        if opts.timestamp or opts.speaker_diarization:
            ts = str(datetime.timedelta(seconds=offset))
            spk = "話者A: " if opts.speaker_diarization else ""
            line = f"[{ts}] {spk}これはテストです。\n" if opts.timestamp else f"{spk}これはテストです。\n"
            self.transcription.add_transcription(line, offset + 5)
        else:
            self.transcription.add_transcription("これはテストです。", offset + 5)

    def _render_response(self, response):
        """ElevenLabs のレスポンスを output_options に応じて整形して self.transcription に追記"""
        opts = self.output_options
        offset = float(self.transcription.last_timestamp_sec)
        words = self._extract_words(response)

        if opts.is_subtitle():
            self._build_subtitle_cues(words, offset)
            last_end = max((float(_word_end(w)) for w in words), default=0.0)
            self.transcription.add_transcription("", int(offset + last_end))
            return

        if not opts.timestamp and not opts.speaker_diarization:
            text = self._extract_text(response).strip()
            self.transcription.add_transcription(text + "\n", int(offset))
            return

        # タイムスタンプ or 話者識別あり: words から行を組み立てる
        rendered, last_end = self._render_words_to_lines(words, offset)
        self.transcription.add_transcription(rendered, int(offset + last_end))

    def _extract_words(self, response) -> list:
        """response.words を素朴に取り出す。Pydanticでもdictでも対応"""
        words = getattr(response, "words", None)
        if words is None and isinstance(response, dict):
            words = response.get("words")
        return list(words or [])

    def _extract_text(self, response) -> str:
        text = getattr(response, "text", None)
        if text is None and isinstance(response, dict):
            text = response.get("text", "")
        return text or ""

    def _speaker_label(self, speaker_id) -> str:
        if not speaker_id:
            return ""
        key = str(speaker_id)
        if key not in self._speaker_label_map:
            idx = len(self._speaker_label_map)
            # 話者A, B, C... AA, AB ... の単純連番
            label = chr(ord("A") + idx) if idx < 26 else f"#{idx}"
            self._speaker_label_map[key] = f"話者{label}"
        return self._speaker_label_map[key]

    def _render_words_to_lines(self, words: Iterable, offset: float) -> tuple[str, float]:
        """words[] を 1行 = 1発話 にまとめて整形する"""
        opts = self.output_options
        lines: list[str] = []
        current_speaker: str | None = None
        current_start: float = 0.0
        last_word_end: float = 0.0
        buffer_text = ""

        def flush(end_sec: float):
            nonlocal buffer_text
            if not buffer_text.strip():
                return
            parts = []
            if opts.timestamp:
                ts = str(datetime.timedelta(seconds=int(offset + current_start)))
                parts.append(f"[{ts}]")
            if opts.speaker_diarization and current_speaker:
                parts.append(f"{current_speaker}:")
            parts.append(buffer_text.strip())
            lines.append(" ".join(parts))
            buffer_text = ""

        for w in words:
            wtype = _word_type(w)
            if wtype == "spacing":
                buffer_text += _word_text(w) or " "
                continue
            if wtype == "audio_event":
                continue

            wtext = _word_text(w)
            wstart = float(_word_start(w) or 0.0)
            wend = float(_word_end(w) or wstart)
            wspeaker = self._speaker_label(_word_speaker_id(w)) if opts.speaker_diarization else None

            new_segment = False
            if not buffer_text:
                # 最初の単語
                current_start = wstart
                current_speaker = wspeaker
            else:
                gap = wstart - last_word_end
                if (opts.speaker_diarization and wspeaker != current_speaker) or gap >= _SILENCE_BREAK_SEC:
                    new_segment = True

            if new_segment:
                flush(last_word_end)
                current_start = wstart
                current_speaker = wspeaker

            buffer_text += wtext
            last_word_end = wend

        flush(last_word_end)
        return ("\n".join(lines) + "\n" if lines else ""), last_word_end

    def _build_subtitle_cues(self, words: Iterable, offset: float):
        """words[] を _CUE_TARGET_SEC 程度のキューにグルーピングして字幕用に蓄積"""
        cue_start: float | None = None
        cue_end: float = 0.0
        cue_text = ""

        for w in words:
            wtype = _word_type(w)
            if wtype == "spacing":
                cue_text += _word_text(w) or " "
                continue
            if wtype == "audio_event":
                continue

            wstart = float(_word_start(w) or 0.0)
            wend = float(_word_end(w) or wstart)

            if cue_start is None:
                cue_start = wstart

            cue_text += _word_text(w)
            cue_end = wend

            if cue_end - cue_start >= _CUE_TARGET_SEC:
                self._subtitle_cues.append(
                    (offset + cue_start, offset + cue_end, cue_text.strip())
                )
                cue_start = None
                cue_text = ""

        if cue_start is not None and cue_text.strip():
            self._subtitle_cues.append(
                (offset + cue_start, offset + cue_end, cue_text.strip())
            )

    def finalize(self) -> str:
        if not self.output_options.is_subtitle():
            return self.transcription.transcription

        from lib.whisper_caller import _format_ts  # 同形式の H:MM:SS,mmm を流用

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
        try:
            self._ensure_client()
            assert self.client is not None
            # 軽量な疎通確認。models.list は権限スコープに依存しにくい
            self.client.models.list()
            return True
        except Exception as e:
            status = getattr(e, "status_code", None)
            body = getattr(e, "body", None)
            if self.console_out or sys.flags.debug:
                print(
                    f"ElevenLabs APIキー確認に失敗: {type(e).__name__} status={status} body={body!r}"
                )
            # 権限不足（missing_permissions）の場合はキー自体は有効なので True
            msg = (str(e) + " " + str(body or "")).lower()
            if "missing_permissions" in msg:
                return True
            # それ以外で 401 / Unauthorized なら無効
            if status == 401 or "401" in msg or "unauthorized" in msg:
                return False
            # ネットワークや SDK 構造変化など不明な失敗は通して本リクエストで判定
            return True


# ---- レスポンスからの値抽出ユーティリティ（Pydantic / dict 両対応） ----

def _word_type(w):
    return _attr_or_key(w, "type") or "word"


def _word_text(w):
    return _attr_or_key(w, "text") or ""


def _word_start(w):
    return _attr_or_key(w, "start")


def _word_end(w):
    return _attr_or_key(w, "end")


def _word_speaker_id(w):
    return _attr_or_key(w, "speaker_id")


def _attr_or_key(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)
