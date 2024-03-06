import os
import subprocess
import sys
import tempfile
from typing import List
from pydub import AudioSegment
from pydub.silence import split_on_silence


class AudioSilencer:
    def __init__(
        self,
        input_path,
    ):
        self.input_path = input_path
        self.flag_silence_removal = True

    # 音声ファイルから無音部分を除去
    def remove_silence_multiple(self, input_files: List[str], suffix="_silenced.mp3"):
        newfiles: List[str] = []
        for input_file in input_files:
            body = os.path.splitext(input_file)[0]
            newfile = body + suffix

            self.remove_silence(input_file, newfile)
            newfiles.append(newfile)
        return newfiles

    def remove_silence(self, input_path, output_path):

        # 音声ファイルを読み込み
        # この中で2回cmd.exeのウィンドウが開かれている
        sound = AudioSegment.from_file(input_path)
        # この後で1回cmd.exeのウィンドウが開かれている

        # 元の音声の長さを計算し、分単位で表示
        org_ms = len(sound)

        if sys.flags.debug:
            print("original: {:.2f} [min]".format(org_ms / 60 / 1000))

        # 無音部分を検出し、音声を分割
        chunks = split_on_silence(
            sound, min_silence_len=100, silence_thresh=-55, keep_silence=100
        )

        # 無音部分を除去した新しい音声を作成
        no_silence_audio = AudioSegment.empty()
        for chunk in chunks:
            no_silence_audio += chunk

        # 無音部分を除去した音声を出力
        no_silence_audio.export(output_path, format="mp3")
        org_ms = len(no_silence_audio)
        if sys.flags.debug:
            print("removed: {:.2f} [min]".format(org_ms / 60 / 1000))

    def extract_audio(self, input_file, output_file):
        command = [
            "ffmpeg",
            "-i",
            input_file,
            "-vn",
            "-acodec",
            "libmp3lame",
            output_file,
            "-loglevel",
            "quiet",
        ]
        subprocess.run(command, check=True, creationflags=subprocess.CREATE_NO_WINDOW)

    def exec(self) -> List[str]:

        # テンポラリディレクトリを作成
        temp_dir = tempfile.mkdtemp(prefix="transcribe_")

        # # Extract audio from MP4 to MP3
        if sys.flags.debug:
            print("==== Extract audio from MP4 to MP3")

        # self.input_path のbody後ろに_audioe.mp3をつけたファイル名を作る
        filename_audio = os.path.basename(self.input_path).split(".")[0] + "_audio.mp3"
        mp3_file = os.path.join(temp_dir, filename_audio)

        self.extract_audio(self.input_path, mp3_file)

        if sys.flags.debug:
            print("==== remove silence part")

        # フラグを確認して静音部分を除去
        if self.flag_silence_removal:
            silenced_files = self.remove_silence_multiple([mp3_file])
        else:
            silenced_files = [mp3_file]

        return silenced_files
