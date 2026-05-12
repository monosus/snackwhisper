from configparser import ConfigParser
from dataclasses import dataclass

# 出力形式の選択肢
FORMAT_TXT = "txt"
FORMAT_MD = "md"
FORMAT_JSON = "json"
FORMAT_SRT = "srt"
FORMAT_VTT = "vtt"

OUTPUT_FORMATS = [FORMAT_TXT, FORMAT_MD, FORMAT_JSON, FORMAT_SRT, FORMAT_VTT]

# SRT/VTTを生成可能なWhisperモデル（OpenAI APIの仕様）
SUBTITLE_CAPABLE_MODELS = {"whisper-1"}


def supports_timestamps(provider: str, model: str) -> bool:
    """このモデル+プロバイダの組み合わせがタイムスタンプ生成に対応しているか。
    - Gemini: プロンプト指示で対応可能
    - OpenAI whisper-1: verbose_json で取得可能
    - OpenAI gpt-4o-*-transcribe: 非対応（json/text のみ）
    """
    if provider == "google":
        return True
    if provider == "openai" and model in SUBTITLE_CAPABLE_MODELS:
        return True
    return False


@dataclass
class OutputOptions:
    """文字起こし出力に付与する情報・フォーマットの設定"""

    output_format: str = FORMAT_TXT  # txt / srt / vtt
    timestamp: bool = False           # txt時のタイムスタンプ付与
    speaker_diarization: bool = False  # 話者識別（Geminiのみ）
    structured: bool = False           # 章立て + Markdown整形（Geminiのみ）
    summary: bool = False              # 冒頭サマリ + アクションアイテム（Geminiのみ）

    def file_extension(self) -> str:
        return self.output_format if self.output_format in OUTPUT_FORMATS else "txt"

    def is_subtitle(self) -> bool:
        return self.output_format in (FORMAT_SRT, FORMAT_VTT)

    def needs_timestamps_internally(self) -> bool:
        """字幕形式またはタイムスタンプ付与時はタイムスタンプ情報が必要"""
        return self.is_subtitle() or self.timestamp

    @classmethod
    def load(cls, config: ConfigParser) -> "OutputOptions":
        opts = cls()
        opts.output_format = config.get("DEFAULT", "output_format", fallback="txt")
        if opts.output_format not in OUTPUT_FORMATS:
            opts.output_format = FORMAT_TXT
        opts.timestamp = config.get("DEFAULT", "timestamp_flag", fallback="False") == "True"
        opts.speaker_diarization = config.get("DEFAULT", "speaker_diarization", fallback="False") == "True"
        opts.structured = config.get("DEFAULT", "structured_output", fallback="False") == "True"
        opts.summary = config.get("DEFAULT", "summary_output", fallback="False") == "True"
        return opts

    def save(self, config: ConfigParser) -> None:
        config["DEFAULT"]["output_format"] = self.output_format
        config["DEFAULT"]["timestamp_flag"] = str(self.timestamp)
        config["DEFAULT"]["speaker_diarization"] = str(self.speaker_diarization)
        config["DEFAULT"]["structured_output"] = str(self.structured)
        config["DEFAULT"]["summary_output"] = str(self.summary)
