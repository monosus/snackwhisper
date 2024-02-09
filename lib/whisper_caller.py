import datetime
import os
import subprocess
import sys
from openai import OpenAI


class WhisperTranscriptionCaller:
    def __init__(self, api_key, audio_files, timestamp_flag: bool):
        self.api_key = api_key
        self.audio_files = audio_files
        self.timestamp_flag = timestamp_flag

        self.transcription = ""
        self.language = "ja"
        self.model = "whisper-1"
        self.prompt = "こんにちは、本日は晴天です。"

        self.client = OpenAI(api_key=api_key)

    def transcribe_audio_files(self):
        for audio_file in self.audio_files:
            # # # Split audio if the file size is over the limit
            if sys.flags.debug:
                print("==== split audio file")
            if os.path.getsize(audio_file) > 20 * 1024 * 1024:
                cropped_files = self.split_audio(audio_file, 5 * 1024 * 1024)
            else:
                cropped_files = [audio_file]

            if sys.flags.debug:
                print(cropped_files)

            for cropped_file in cropped_files:
                self.transcription += self.transcribe_single_file(cropped_file)

        return self.transcription

    def transcribe_single_file(self, audio_file):
        with open(str(audio_file), "rb") as f:
            if self.timestamp_flag:
                transcript = self.create_with_timestamp(f)
            else:
                transcript = self.create(f)

            if sys.flags.debug:
                print(transcript)
            return transcript

    def create_with_timestamp(self, file_handler):
        transcript = self.client.audio.transcriptions.create(
            model=self.model,
            file=file_handler,
            language=self.language,
            response_format="verbose_json",
            prompt=self.prompt,
        )

        result = ""
        for segment in transcript.segments:  # type: ignore
            text = segment["text"]
            endsec = int(segment["start"])
            timestamp = str(datetime.timedelta(seconds=endsec))
            result += f"[{timestamp}] {text}\n"

        return result

    def create(self, file_handler):
        transcript = self.client.audio.transcriptions.create(
            model=self.model,
            file=file_handler,
            language=self.language,
            response_format="json",
        )
        return transcript.text

    def split_audio(self, input_file, max_size):
        duration_command = [
            "ffprobe",
            "-i",
            input_file,
            "-show_entries",
            "format=duration",
            "-v",
            "quiet",
            "-of",
            "csv=p=0",
        ]
        duration = float(
            subprocess.check_output(duration_command).decode("utf-8").strip()
        )

        size = os.path.getsize(input_file)
        target_duration = (duration * max_size) // size

        command = [
            "ffmpeg",
            "-i",
            input_file,
            "-f",
            "segment",
            "-segment_time",
            str(target_duration),
            "-acodec",
            "copy",
            "work/split-%03d.mp3",
        ]
        subprocess.run(command, check=True)

        split_files = []
        for filename in os.listdir("work"):
            if filename.startswith("split") and filename.endswith(".mp3"):
                split_files.append(os.path.join("work", filename))

        return sorted(split_files)
