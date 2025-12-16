import discord
from datetime import datetime
from typing import Optional, Dict, Any

YOUTUBE_ICON = "https://www.youtube.com/s/desktop/12d6b690/img/favicon_144x144.png"


def format_duration(seconds: int) -> str:
    if not seconds:
        return "Unknown"
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def format_views(views: int) -> str:
    if not views:
        return "Unknown"
    if views >= 1_000_000_000:
        return f"{views / 1_000_000_000:.1f}B views"
    if views >= 1_000_000:
        return f"{views / 1_000_000:.1f}M views"
    if views >= 1_000:
        return f"{views / 1_000:.1f}K views"
    return f"{views:,} views"


def format_file_size(size_bytes: int) -> str:
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / 1024 ** 3:.2f} GB"
    if size_bytes >= 1024 ** 2:
        return f"{size_bytes / 1024 ** 2:.2f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} bytes"


def create_video_embed(
    metadata: Dict[str, Any],
    file_url: str,
    download_url: str,
    file_size: Optional[int] = None,
    expires_in_hours: int = 24
) -> discord.Embed:
    is_large = file_size and file_size > 250 * 1024 * 1024
    
    embed = discord.Embed(
        title=f" {metadata.get('title', 'Unknown')}",
        url=file_url,
        color=0xFF0000,
        timestamp=datetime.now(),
        description="video too large for discord preview, click **Stream** to watch >:(" if is_large else None
    )

    embed.add_field(name=" Channel", value=metadata.get('uploader', 'Unknown'), inline=True)
    embed.add_field(name="⏱ Duration", value=format_duration(metadata.get('duration', 0)), inline=True)
    embed.add_field(name=" Views", value=format_views(metadata.get('view_count', 0)), inline=True)

    if file_size:
        embed.add_field(name=" File Size", value=format_file_size(file_size), inline=True)

    embed.add_field(name=" Quality", value="1080p 60fps", inline=True)
    embed.add_field(name="⏰ Expires", value=f"In {expires_in_hours} hours", inline=True)

    if thumbnail := metadata.get('thumbnail'):
        if is_large:
            embed.set_image(url=thumbnail)
        else:
            embed.set_thumbnail(url=thumbnail)

    embed.set_footer(text="YouTube Downloader Bot • Click title to play", icon_url=YOUTUBE_ICON)
    return embed


def create_audio_embed(
    metadata: Dict[str, Any],
    file_url: str,
    download_url: str,
    file_size: Optional[int] = None,
    expires_in_hours: int = 24
) -> discord.Embed:
    embed = discord.Embed(
        title=f" {metadata.get('title', 'Unknown')}",
        url=file_url,
        color=0x1DB954,
        timestamp=datetime.now()
    )

    embed.add_field(name=" Artist/Channel", value=metadata.get('uploader', 'Unknown'), inline=True)
    embed.add_field(name="⏱ Duration", value=format_duration(metadata.get('duration', 0)), inline=True)
    embed.add_field(name=" Quality", value="320 kbps MP3", inline=True)

    if file_size:
        embed.add_field(name=" File Size", value=format_file_size(file_size), inline=True)

    embed.add_field(name="⏰ Expires", value=f"In {expires_in_hours} hours", inline=True)

    if thumbnail := metadata.get('thumbnail'):
        embed.set_thumbnail(url=thumbnail)

    embed.set_footer(text="YouTube Downloader Bot • Click title to download", icon_url=YOUTUBE_ICON)
    return embed


def create_download_button(file_url: str, download_url: str, is_audio: bool = False) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(
        label=" Listen" if is_audio else " Stream",
        url=file_url,
        style=discord.ButtonStyle.link
    ))
    view.add_item(discord.ui.Button(
        label=" Download",
        url=download_url,
        style=discord.ButtonStyle.link
    ))
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
    action = " Extracting audio" if is_audio else " Downloading video"
    embed = discord.Embed(
        title="⏳ Processing...",
        description=f"{action} from YouTube\nThis may take a few minutes...",
        color=0xFFAA00,
        timestamp=datetime.now()
    )
    embed.add_field(name="URL", value=url, inline=False)
    embed.set_footer(text="YouTube Downloader Bot • Please wait")
    return embed


def create_progress_embed(percent: float, speed: str, eta: str, is_audio: bool = False) -> discord.Embed:
    filled = int(percent / 5)
    bar = "█" * filled + "░" * (20 - filled)
    action = "🎵 Extracting audio" if is_audio else "📺 Downloading video"
    
    embed = discord.Embed(
        title=action,
        description=f"```\n[{bar}] {percent:.1f}%\n```",
        color=0x00FF00 if percent >= 100 else 0xFFAA00,
    )
    embed.add_field(name="⚡ Speed", value=speed or "...", inline=True)
    embed.add_field(name="⏱️ ETA", value=eta or "...", inline=True)
    embed.set_footer(text="YouTube Downloader Bot")
    return embed


def create_success_embed(is_audio: bool = False) -> discord.Embed:
    action = "🎵 Audio extracted!" if is_audio else "📺 Video downloaded!"
    embed = discord.Embed(
        title=action,
        description="Processing complete. Here's your file:",
        color=0x00FF00,
    )
    embed.set_footer(text="YouTube Downloader Bot")
    return embed