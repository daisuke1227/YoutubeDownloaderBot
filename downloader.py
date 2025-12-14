import os
import subprocess
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, Tuple


class YouTubeDownloader:
    def __init__(self, download_dir: str = "./downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, title: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', '', title)[:100]

    def _clean_url(self, url: str) -> str:
        url = re.sub(r'[&?]t=\d+s?', '', url)
        url = re.sub(r'[&?]list=[^&]+', '', url)
        url = re.sub(r'[&?]index=\d+', '', url)
        url = re.sub(r'[&?]start_radio=\d+', '', url)
        url = url.rstrip('&?')
        return url

    def _run_ytdlp(self, url: str, args: list) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        clean_url = self._clean_url(url)
        cmd = [
            "yt-dlp",
            "--cookies-from-browser", "firefox",
            "--no-warnings",
            "--print-json",
            "--no-part",
            "--windows-filenames",
            "--no-playlist",
            "-o", str(self.download_dir / "%(id)s.%(ext)s"),
            *args,
            clean_url
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode != 0:
                error_msg = result.stderr or "Unknown error occurred"
                return False, error_msg, None

            lines = result.stdout.strip().split('\n')
            for line in reversed(lines):
                try:
                    metadata = json.loads(line)
                    return True, "", metadata
                except json.JSONDecodeError:
                    continue

            return False, "Could not parse yt-dlp output", None

        except subprocess.TimeoutExpired:
            return False, "Download timed out (10 minutes)", None
        except FileNotFoundError:
            return False, "yt-dlp not found. Please install it: pip install yt-dlp", None
        except Exception as e:
            return False, str(e), None

    def get_video_info(self, url: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        cmd = [
            "yt-dlp",
            "--cookies-from-browser", "firefox",
            "--no-warnings",
            "--dump-json",
            "--no-download",
            url
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                return False, result.stderr or "Failed to get video info", None

            metadata = json.loads(result.stdout)
            return True, "", metadata

        except Exception as e:
            return False, str(e), None

    def download_video(self, url: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        args = [
            "-f", "bestvideo[height<=1080][fps<=60][vcodec^=hvc1]+bestaudio/bestvideo[height<=1080][fps<=60][vcodec^=hev1]+bestaudio/bestvideo[height<=1080][fps<=60][vcodec^=avc1]+bestaudio/best[height<=1080]/best",
            "--merge-output-format", "mp4",
            "--add-metadata",
            "--ppa", "ffmpeg:-movflags +faststart",
        ]

        return self._run_ytdlp(url, args)

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
        expected_path = self.download_dir / f"{video_id}.{ext}"

        if expected_path.exists():
            return expected_path

        for file in self.download_dir.iterdir():
            if video_id in file.name:
                return file

        return None


def format_duration(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_views(views: int) -> str:
    if views >= 1_000_000_000:
        return f"{views / 1_000_000_000:.1f}B"
    elif views >= 1_000_000:
        return f"{views / 1_000_000:.1f}M"
    elif views >= 1_000:
        return f"{views / 1_000:.1f}K"
    return str(views)