"""ビルド時刻を _buildinfo.py に書き出すスクリプト。build.bat から呼ばれる。"""
import datetime
import os


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(here, "_buildinfo.py")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(target, "w", encoding="utf-8") as f:
        f.write(f'BUILD_TIMESTAMP = "{timestamp}"\n')
    print(f"[make_buildinfo] BUILD_TIMESTAMP = {timestamp}")


if __name__ == "__main__":
    main()
