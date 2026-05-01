from configparser import ConfigParser
from dataclasses import dataclass, field
from typing import List, Optional


PROFILE_SECTION_PREFIX = "profile:"


# Provider candidates with their default model lists shown in the settings dialog.
PROVIDER_PRESETS: dict[str, list[str]] = {
    "openai": ["whisper-1", "gpt-4o-mini-transcribe", "gpt-4o-transcribe"],
    "google": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
}


@dataclass
class ModelProfile:
    name: str
    provider: str
    model: str
    api_key: str = ""

    def is_valid(self) -> bool:
        return bool(self.name and self.provider and self.model)


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
            profile = ModelProfile(
                name=name,
                provider=config.get(section, "provider", fallback="openai"),
                model=config.get(section, "model", fallback=""),
                api_key=config.get(section, "api_key", fallback=""),
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

    def remove(self, name: str) -> None:
        existing = self.find(name)
        if existing is None:
            return
        self.profiles.remove(existing)
        if self.selected == name:
            self.selected = self.profiles[0].name if self.profiles else None
