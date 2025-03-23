
from configparser import ConfigParser


class DebugOptions:
    def __init__(self, config: ConfigParser | None = None):
        if config is None:
            self.export_errorlog = False
            self.console_out = False
            self.split_segment_sec = 0
            self.dry_run = False

            return

        # エラーログの出力
        self.export_errorlog = config.get("DEBUG", "export_errorlog", fallback="False") == "True"

        # 分割する時間（秒）、ゼロのときは内部で計算する
        self.split_segment_sec = int(
            config.get("DEBUG", "split_segment_sec", fallback="0")
        )

        # ドライランフラグ
        self.dry_run = config.get("DEBUG", "dry_run", fallback="False") == "True"

        # 出力フラグ
        self.console_out = config.get("DEBUG", "console_out", fallback="False") == "True"

