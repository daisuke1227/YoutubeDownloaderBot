import subprocess
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

VIDEO_FORMAT = (
    "bestvideo[height<=1080][fps<=60][vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestaudio/"
    "bestvideo[height<=1080][fps<=60][vcodec^=avc1]+bestaudio/"
    "bestvideo[height<=1080][fps<=60]+bestaudio/"
    "best[height<=1080]/best"
)


class YouTubeDownloader:
    def __init__(self, download_dir: str = "./downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def _clean_url(self, url: str) -> str:
        url = re.sub(r'[&?]t=\d+s?', '', url)
        url = re.sub(r'[&?]list=[^&]+', '', url)
        url = re.sub(r'[&?]index=\d+', '', url)
        url = re.sub(r'[&?]start_radio=\d+', '', url)
        return url.rstrip('&?')

    def _run_ytdlp(self, url: str, args: list) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        cmd = [
            "yt-dlp",
            "--cookies-from-browser", "firefox",
            "--no-warnings",
            "--print-json",
            "--no-part",
            "--windows-filenames",
            "--no-playlist",
            "-N", "1000",
            "-o", str(self.download_dir / "%(id)s.%(ext)s"),
            *args,
            self._clean_url(url)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode != 0:
                return False, result.stderr or "Unknown error", None

            for line in reversed(result.stdout.strip().split('\n')):
                try:
                    return True, "", json.loads(line)
                except json.JSONDecodeError:
                    continue

            return False, "Could not parse yt-dlp output", None

        except subprocess.TimeoutExpired:
            return False, "Download timed out (10 minutes)", None
        except FileNotFoundError:
            return False, "yt-dlp not found", None
        except Exception as e:
            return False, str(e), None

    def download_video(self, url: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        args = [
            "-f", VIDEO_FORMAT,
            "--merge-output-format", "mp4",
            "--add-metadata",
            "--ppa", "ffmpeg:-c copy -fflags +genpts -movflags +faststart",
        ]
        return self._run_ytdlp(url, args)

    def download_with_progress(self, url: str, is_audio: bool = False):
        if is_audio:
            args = [
                "-f", "bestaudio/best",
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "320K",
                "--embed-thumbnail",
                "--add-metadata",
            ]
        else:
            args = [
                "-f", VIDEO_FORMAT,
                "--merge-output-format", "mp4",
                "--add-metadata",
                "--ppa", "ffmpeg:-c copy -fflags +genpts -movflags +faststart",
            ]

        cmd = [
            "yt-dlp",
            "--cookies-from-browser", "firefox",
            "--no-warnings",
            "--print-json",
            "--no-part",
            "--windows-filenames",
            "--no-playlist",
            "--newline",
            "--progress",
            "-N", "1000",
            "-o", str(self.download_dir / "%(id)s.%(ext)s"),
            *args,
            self._clean_url(url)
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            metadata = None
            last_percent = -1

            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                
                print(f"[yt-dlp] {line}")

                if line.startswith('{'):
                    try:
                        metadata = json.loads(line)
                    except json.JSONDecodeError:
                        pass
                elif '[download]' in line:
                    match = re.search(r'(\d+\.?\d*)%', line)
                    if match:
                        try:
                            percent = float(match.group(1))
                            speed_match = re.search(r'at\s+(\S+)', line)
                            eta_match = re.search(r'ETA\s+(\S+)', line)
                            speed = speed_match.group(1) if speed_match else "..."
                            eta = eta_match.group(1) if eta_match else "..."
                            
                            if int(percent) > last_percent:
                                last_percent = int(percent)
                                yield ('progress', percent, speed, eta)
                        except (ValueError, IndexError):
                            pass

            process.wait()

            if process.returncode != 0:
                yield ('error', "Download failed", None)
                return

            yield ('done', metadata)

        except FileNotFoundError:
            yield ('error', "yt-dlp not found", None)
        except Exception as e:
            yield ('error', str(e), None)

    def download_audio(self, url: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        args = [
            "-f", "bestaudio/best",
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "320K",
            "--embed-thumbnail",
            "--add-metadata",
        ]
        return self._run_ytdlp(url, args)

    def get_downloaded_file_path(self, video_id: str, is_audio: bool = False) -> Optional[Path]:
        ext = "mp3" if is_audio else "mp4"
        expected = self.download_dir / f"{video_id}.{ext}"

        if expected.exists():
            return expected

        for file in self.download_dir.iterdir():
            if video_id in file.name:
                return file

        return None


def format_duration(seconds: int) -> str:
    if not seconds:
        return "0:00"
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def format_views(views: int) -> str:
    if views >= 1_000_000_000:
        return f"{views / 1_000_000_000:.1f}B"
    if views >= 1_000_000:
        return f"{views / 1_000_000:.1f}M"
    if views >= 1_000:
        return f"{views / 1_000:.1f}K"
    return str(views)


def format_size(size_bytes: int) -> str:
    if not size_bytes:
        return "Unknown"
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / 1024 ** 3:.2f} GB"
    if size_bytes >= 1024 ** 2:
        return f"{size_bytes / 1024 ** 2:.2f} MB"
    return f"{size_bytes / 1024:.2f} KB"