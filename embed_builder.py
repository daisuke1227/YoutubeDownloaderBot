import discord
from datetime import datetime
from typing import Optional, Dict, Any


YOUTUBE_COLORS = [
    0xFF0000,
    0xCC0000,
    0xFF4444,
    0xBF0000,
]


def format_duration(seconds: int) -> str:
    if not seconds:
        return "Unknown"

    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_views(views: int) -> str:
    if not views:
        return "Unknown"

    if views >= 1_000_000_000:
        return f"{views / 1_000_000_000:.1f}B views"
    elif views >= 1_000_000:
        return f"{views / 1_000_000:.1f}M views"
    elif views >= 1_000:
        return f"{views / 1_000:.1f}K views"
    return f"{views:,} views"


def format_file_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    elif size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} bytes"


def create_video_embed(
    metadata: Dict[str, Any],
    file_url: str,
    download_url: str,
    file_size: Optional[int] = None,
    expires_in_hours: int = 24
) -> discord.Embed:
    title = metadata.get('title', 'Unknown Title')
    uploader = metadata.get('uploader', metadata.get('channel', 'Unknown'))
    duration = metadata.get('duration', 0)
    view_count = metadata.get('view_count', 0)
    thumbnail = metadata.get('thumbnail', '')
    upload_date = metadata.get('upload_date', '')
    description = metadata.get('description', '')[:200] + '...' if metadata.get('description') else ''

    embed = discord.Embed(
        title=f" {title}",
        url=file_url,
        color=YOUTUBE_COLORS[0],
        timestamp=datetime.now()
    )

    embed.add_field(
        name=" Channel",
        value=uploader,
        inline=True
    )

    embed.add_field(
        name="⏱ Duration",
        value=format_duration(duration),
        inline=True
    )

    embed.add_field(
        name=" Views",
        value=format_views(view_count),
        inline=True
    )

    if file_size:
        embed.add_field(
            name=" File Size",
            value=format_file_size(file_size),
            inline=True
        )

    embed.add_field(
        name=" Quality",
        value="1080p 60fps",
        inline=True
    )

    embed.add_field(
        name="⏰ Expires",
        value=f"In {expires_in_hours} hours",
        inline=True
    )

    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    embed.set_footer(
        text="YouTube Downloader Bot • Click title to play",
        icon_url="https://www.youtube.com/s/desktop/12d6b690/img/favicon_144x144.png"
    )

    return embed


def create_audio_embed(
    metadata: Dict[str, Any],
    file_url: str,
    download_url: str,
    file_size: Optional[int] = None,
    expires_in_hours: int = 24
) -> discord.Embed:
    title = metadata.get('title', 'Unknown Title')
    uploader = metadata.get('uploader', metadata.get('channel', 'Unknown'))
    duration = metadata.get('duration', 0)
    thumbnail = metadata.get('thumbnail', '')

    embed = discord.Embed(
        title=f" {title}",
        url=file_url,
        color=0x1DB954,
        timestamp=datetime.now()
    )

    embed.add_field(
        name=" Artist/Channel",
        value=uploader,
        inline=True
    )

    embed.add_field(
        name="⏱ Duration",
        value=format_duration(duration),
        inline=True
    )

    embed.add_field(
        name=" Quality",
        value="320 kbps MP3",
        inline=True
    )

    if file_size:
        embed.add_field(
            name=" File Size",
            value=format_file_size(file_size),
            inline=True
        )

    embed.add_field(
        name="⏰ Expires",
        value=f"In {expires_in_hours} hours",
        inline=True
    )

    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    embed.set_footer(
        text="YouTube Downloader Bot • Click title to download",
        icon_url="https://www.youtube.com/s/desktop/12d6b690/img/favicon_144x144.png"
    )

    return embed


def create_download_button(file_url: str, download_url: str, is_audio: bool = False) -> discord.ui.View:
    view = discord.ui.View(timeout=None)

    stream_btn = discord.ui.Button(
        label=" Stream" if not is_audio else " Listen",
        url=file_url,
        style=discord.ButtonStyle.link
    )
    view.add_item(stream_btn)

    download_btn = discord.ui.Button(
        label=" Download",
        url=download_url,
        style=discord.ButtonStyle.link
    )
    view.add_item(download_btn)

    return view


def create_error_embed(error_message: str, url: str = "") -> discord.Embed:
    embed = discord.Embed(
        title=" Download Failed",
        description=error_message,
        color=0xFF0000,
        timestamp=datetime.now()
    )

    if url:
        embed.add_field(name="URL", value=url, inline=False)

    embed.set_footer(text="YouTube Downloader Bot")

    return embed


def create_processing_embed(url: str, is_audio: bool = False) -> discord.Embed:
    embed = discord.Embed(
        title="⏳ Processing...",
        description=f"{' Extracting audio' if is_audio else ' Downloading video'} from YouTube\nThis may take a few minutes...",
        color=0xFFAA00,
        timestamp=datetime.now()
    )

    embed.add_field(name="URL", value=url, inline=False)
    embed.set_footer(text="YouTube Downloader Bot • Please wait")

    return embed