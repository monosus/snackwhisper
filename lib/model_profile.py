from configparser import ConfigParser
from dataclasses import dataclass, field
from typing import List, Optional


PROFILE_SECTION_PREFIX = "profile:"


PROVIDER_PRESETS: dict[str, list[str]] = {
    "openai": ["whisper-1", "gpt-4o-mini-transcribe", "gpt-4o-transcribe"],
    "google": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
    "elevenlabs": ["scribe_v1", "scribe_v2"],
}


# プロバイダ別のデフォルトプロンプト。プロファイル新規作成時や `prompt` が空のときに使われる。
DEFAULT_PROMPTS: dict[str, str] = {
    # OpenAI Whisper API は `prompt` を語彙ヒント（直前のコンテキスト）として使うため、
    # 短い単語列を並べる
    "openai": (
        "ありがとうございます。 です。 ます。 ChatGPT 本橋 神山 kintone"
    ),
    # Gemini はマルチモーダル指示として渡されるため、出力フォーマット制御を含める
    "google": (
        "正確に文字起こしを行ってください。\n"
        "- 日本語の文字や単語の間に半角スペースを入れないでください。\n"
        "- タイムスタンプの数字の間にもスペースを入れないでください。\n"
        "- 自然な日本語の文章として出力してください。"
    ),
    # ElevenLabs は keyterms（語彙ヒント配列）として解釈する。1行1キーターム。
    "elevenlabs": (
        "本橋\n"
        "神山\n"
        "kintone\n"
        "ChatGPT"
    ),
}


def _encode_prompt(prompt: str) -> str:
    """configparser に1行で格納するため改行をエスケープ"""
    return prompt.replace("\\", "\\\\").replace("\n", "\\n")


def _decode_prompt(stored: str) -> str:
    """エスケープ済みの prompt 文字列を元に戻す"""
    out: list[str] = []
    i = 0
    while i < len(stored):
        ch = stored[i]
        if ch == "\\" and i + 1 < len(stored):
            nxt = stored[i + 1]
            if nxt == "n":
                out.append("\n")
                i += 2
                continue
            if nxt == "\\":
                out.append("\\")
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


@dataclass
class ModelProfile:
    name: str
    provider: str
    model: str
    api_key: str = ""
    prompt: str = ""

    def is_valid(self) -> bool:
        return bool(self.name and self.provider and self.model)


def effective_prompt(profile: ModelProfile) -> str:
    """プロファイルの prompt が空ならプロバイダのデフォルトを返す"""
    if profile.prompt and profile.prompt.strip():
        return profile.prompt
    return DEFAULT_PROMPTS.get(profile.provider, "")


@dataclass
class ProfileRegistry:
    profiles: List[ModelProfile] = field(default_factory=list)
    selected: Optional[str] = None

    @classmethod
    def load(cls, config: ConfigParser) -> "ProfileRegistry":
        registry = cls()
        for section in config.sections():
            if not section.startswith(PROFILE_SECTION_PREFIX):
                continue
            name = section[len(PROFILE_SECTION_PREFIX):]
            stored_prompt = config.get(section, "prompt", fallback="")
            profile = ModelProfile(
                name=name,
                provider=config.get(section, "provider", fallback="openai"),
                model=config.get(section, "model", fallback=""),
                api_key=config.get(section, "api_key", fallback=""),
                prompt=_decode_prompt(stored_prompt),
            )
            if profile.is_valid():
                registry.profiles.append(profile)

        registry.selected = config.get("DEFAULT", "selected_profile", fallback=None) or None

        legacy_token = config.get("DEFAULT", "api_token", fallback="").strip()
        if legacy_token and not registry.profiles:
            registry.profiles.append(
                ModelProfile(
                    name="OpenAI (default)",
                    provider="openai",
                    model="gpt-4o-mini-transcribe",
                    api_key=legacy_token,
                    prompt="",
                )
            )
            registry.selected = "OpenAI (default)"

        if registry.selected is None and registry.profiles:
            registry.selected = registry.profiles[0].name

        return registry

    def save(self, config: ConfigParser) -> None:
        for section in list(config.sections()):
            if section.startswith(PROFILE_SECTION_PREFIX):
                config.remove_section(section)

        for profile in self.profiles:
            section = PROFILE_SECTION_PREFIX + profile.name
            config[section] = {
                "provider": profile.provider,
                "model": profile.model,
                "api_key": profile.api_key,
                "prompt": _encode_prompt(profile.prompt or ""),
            }

        if self.selected:
            config["DEFAULT"]["selected_profile"] = self.selected
        elif "selected_profile" in config["DEFAULT"]:
            del config["DEFAULT"]["selected_profile"]

        if "api_token" in config["DEFAULT"]:
            del config["DEFAULT"]["api_token"]

    def names(self) -> List[str]:
        return [p.name for p in self.profiles]

    def find(self, name: str) -> Optional[ModelProfile]:
        for p in self.profiles:
            if p.name == name:
                return p
        return None

    def select(self, name: Optional[str]) -> None:
        if name is None or self.find(name) is None:
            self.selected = self.profiles[0].name if self.profiles else None
        else:
            self.selected = name

    def selected_profile(self) -> Optional[ModelProfile]:
        if self.selected is None:
            return None
        return self.find(self.selected)

    def upsert(self, profile: ModelProfile, original_name: Optional[str] = None) -> None:
        if original_name and original_name != profile.name:
            existing = self.find(original_name)
            if existing is not None:
                self.profiles.remove(existing)
            if self.selected == original_name:
                self.selected = profile.name

        existing = self.find(profile.name)
        if existing is None:
            self.profiles.append(profile)
        else:
            existing.provider = profile.provider
            existing.model = profile.model
            existing.api_key = profile.api_key
            existing.prompt = profile.prompt

    def remove(self, name: str) -> None:
        existing = self.find(name)
        if existing is None:
            return
        self.profiles.remove(existing)
        if self.selected == name:
            self.selected = self.profiles[0].name if self.profiles else None
