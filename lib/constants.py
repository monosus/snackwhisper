from enum import Enum


# 定数定義で、実行ボタンの状況をdisable, release, 何もしないの3つに分ける
class ButtonState(Enum):
    DISABLE = 0
    RELEASE = 1
    NONE = 2
