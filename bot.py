import os
import asyncio
import discord
import requests
from discord import app_commands
from discord.ext import commands
from discord import ui
from dotenv import load_dotenv
from pathlib import Path

from downloader import YouTubeDownloader


def fetch_youtube_dislikes(video_id: str) -> int:
    try:
        response = requests.get(
            f"https://returnyoutubedislikeapi.com/Votes",
            params={"videoId": video_id},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("dislikes", 0)
    except Exception:
        pass
    return 0
from file_manager import FileManager
from file_server import FileServer
from embed_builder import (
    create_video_embed,
    create_audio_embed,
    create_download_button,
    create_error_embed,
    create_processing_embed
)

load_dotenv()


def get_local_ip() -> str:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
FILE_SERVER_PORT = int(os.getenv('FILE_SERVER_PORT', '3000'))
DOWNLOAD_DIR = os.getenv('DOWNLOAD_DIR', './downloads')
UPLOAD_DIR = os.getenv('UPLOAD_DIR', './uploads')
FILE_EXPIRY_HOURS = int(os.getenv('FILE_EXPIRY_HOURS', '24'))

_domain_setting = os.getenv('FILE_SERVER_DOMAIN', 'auto')
if _domain_setting.lower() == 'auto':
    local_ip = get_local_ip()
    FILE_SERVER_DOMAIN = f"http://{local_ip}:{FILE_SERVER_PORT}"
    print(f" Auto-detected local IP: {local_ip}")
else:
    FILE_SERVER_DOMAIN = _domain_setting


class YouTubeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()

        super().__init__(
            command_prefix='!',
            intents=intents,
            allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
            allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="YouTube | /video /audio"
            )
        )

        self.downloader = YouTubeDownloader(DOWNLOAD_DIR)
        self.file_manager = FileManager(UPLOAD_DIR, FILE_EXPIRY_HOURS)
        self.file_server = FileServer(UPLOAD_DIR, FILE_SERVER_PORT, FILE_SERVER_DOMAIN)

    async def setup_hook(self):
        self.file_server.start(threaded=True)
        self.file_manager.start_scheduler()

        await self.tree.sync()
        print(f" Synced {len(self.tree.get_commands())} slash commands")

    async def on_ready(self):
        pass

bot = YouTubeBot()


@bot.tree.command(name="video", description="Download a YouTube video in 1080p 60fps quality")
@app_commands.describe(url="The YouTube video URL to download")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def download_video(interaction: discord.Interaction, url: str):
    await interaction.response.defer(ephemeral=True)

    try:
        processing_embed = create_processing_embed(url, is_audio=False)
        await interaction.followup.send(embed=processing_embed, ephemeral=True)

        loop = asyncio.get_event_loop()
        success, error, metadata = await loop.run_in_executor(
            None,
            bot.downloader.download_video,
            url
        )

        if not success:
            error_embed = create_error_embed(error, url)
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return

        video_id = metadata.get('id', '')
        file_path = bot.downloader.get_downloaded_file_path(video_id, is_audio=False)

        if not file_path:
            error_embed = create_error_embed("Downloaded file not found", url)
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return

        file_uuid = bot.file_manager.add_file(
            file_path,
            file_path.name,
            video_title=metadata.get('title', 'Unknown'),
            video_id=video_id
        )

        if not file_uuid:
            error_embed = create_error_embed("Failed to process file", url)
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return

        file_info = bot.file_manager.get_file_info(file_uuid)
        file_url = bot.file_server.get_file_url(file_uuid, download=False, extension=".mp4")
        download_url = bot.file_server.get_file_url(file_uuid, download=True, extension=".mp4")

        title = metadata.get('title', 'Video')
        uploader = metadata.get('uploader', 'Unknown')
        views = metadata.get('view_count', 0)
        likes = metadata.get('like_count', 0)
        dislikes = fetch_youtube_dislikes(video_id)
        duration_secs = metadata.get('duration', 0)
        
        def format_duration(secs):
            if not secs:
                return "Unknown"
            mins, s = divmod(int(secs), 60)
            hrs, mins = divmod(mins, 60)
            if hrs > 0:
                return f"{hrs}:{mins:02d}:{s:02d}"
            return f"{mins}:{s:02d}"
        
        def format_number(n):
            if not n:
                return "0"
            if n >= 1_000_000:
                return f"{n/1_000_000:.1f}M"
            if n >= 1_000:
                return f"{n/1_000:.1f}K"
            return str(n)
        
        def format_size(bytes_size):
            if not bytes_size:
                return "Unknown"
            if bytes_size >= 1024 * 1024 * 1024:
                return f"{bytes_size / (1024 * 1024 * 1024):.2f} GB"
            if bytes_size >= 1024 * 1024:
                return f"{bytes_size / (1024 * 1024):.2f} MB"
            return f"{bytes_size / 1024:.2f} KB"
        
        file_size_bytes = file_info.get('size_bytes') if file_info else None
        
        video_url = f"https://youtube.com/watch?v={video_id}"
        
        info_text = f"**{title}**\n"
        info_text += f"📺 {uploader}\n"
        info_text += f"👁️ {format_number(views)} views • ⏱️ {format_duration(duration_secs)}\n"
        info_text += f"👍 {format_number(likes)} • 👎 {format_number(dislikes)}\n"
        info_text += f"📁 {format_size(file_size_bytes)} • ⏳ Expires in {FILE_EXPIRY_HOURS}h"
        
        class VideoLayoutView(ui.LayoutView):
            container = ui.Container(
                ui.TextDisplay(info_text),
                ui.MediaGallery(
                    discord.MediaGalleryItem(media=file_url)
                ),
                ui.ActionRow(
                    ui.Button(label="YouTube", url=video_url, style=discord.ButtonStyle.link),
                    ui.Button(label="Stream", url=file_url, style=discord.ButtonStyle.link),
                    ui.Button(label="Download", url=download_url, style=discord.ButtonStyle.link)
                ),
                accent_colour=discord.Colour.red()
            )
        
        layout_view = VideoLayoutView()
        await interaction.channel.send(view=layout_view)

        print(f" Downloaded video: {metadata.get('title', 'Unknown')} -> {file_uuid}")

    except Exception as e:
        error_embed = create_error_embed(str(e), url)
        try:
            await interaction.edit_original_response(embed=error_embed)
        except:
            await interaction.followup.send(embed=error_embed)


@bot.tree.command(name="audio", description="Download a YouTube video as 320kbps MP3")
@app_commands.describe(url="The YouTube video URL to extract audio from")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def download_audio(interaction: discord.Interaction, url: str):
    await interaction.response.defer(ephemeral=True)

    try:
        processing_embed = create_processing_embed(url, is_audio=True)
        await interaction.followup.send(embed=processing_embed, ephemeral=True)

        loop = asyncio.get_event_loop()
        success, error, metadata = await loop.run_in_executor(
            None,
            bot.downloader.download_audio,
            url
        )

        if not success:
            error_embed = create_error_embed(error, url)
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return

        video_id = metadata.get('id', '')
        file_path = bot.downloader.get_downloaded_file_path(video_id, is_audio=True)

        if not file_path:
            error_embed = create_error_embed("Downloaded file not found", url)
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return

        file_uuid = bot.file_manager.add_file(
            file_path,
            file_path.name,
            video_title=metadata.get('title', 'Unknown'),
            video_id=video_id
        )

        if not file_uuid:
            error_embed = create_error_embed("Failed to process file", url)
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return

        file_info = bot.file_manager.get_file_info(file_uuid)
        file_url = bot.file_server.get_file_url(file_uuid, download=False, extension=".mp3")
        download_url = bot.file_server.get_file_url(file_uuid, download=True, extension=".mp3")

        title = metadata.get('title', 'Audio')
        uploader = metadata.get('uploader', 'Unknown')
        views = metadata.get('view_count', 0)
        likes = metadata.get('like_count', 0)
        dislikes = fetch_youtube_dislikes(video_id)
        duration_secs = metadata.get('duration', 0)
        
        def format_duration(secs):
            if not secs:
                return "Unknown"
            mins, s = divmod(int(secs), 60)
            hrs, mins = divmod(mins, 60)
            if hrs > 0:
                return f"{hrs}:{mins:02d}:{s:02d}"
            return f"{mins}:{s:02d}"
        
        def format_number(n):
            if not n:
                return "0"
            if n >= 1_000_000:
                return f"{n/1_000_000:.1f}M"
            if n >= 1_000:
                return f"{n/1_000:.1f}K"
            return str(n)
        
        def format_size(bytes_size):
            if not bytes_size:
                return "Unknown"
            if bytes_size >= 1024 * 1024 * 1024:
                return f"{bytes_size / (1024 * 1024 * 1024):.2f} GB"
            if bytes_size >= 1024 * 1024:
                return f"{bytes_size / (1024 * 1024):.2f} MB"
            return f"{bytes_size / 1024:.2f} KB"
        
        file_size_bytes = file_info.get('size_bytes') if file_info else None
        
        video_url = f"https://youtube.com/watch?v={video_id}"
        
        info_text = f"**{title}**\n"
        info_text += f"🎵 {uploader}\n"
        info_text += f"👁️ {format_number(views)} views • ⏱️ {format_duration(duration_secs)}\n"
        info_text += f"👍 {format_number(likes)} • 👎 {format_number(dislikes)}\n"
        info_text += f"📁 {format_size(file_size_bytes)} • 🎧 320kbps MP3 • ⏳ Expires in {FILE_EXPIRY_HOURS}h"
        
        class AudioLayoutView(ui.LayoutView):
            container = ui.Container(
                ui.TextDisplay(info_text),
                ui.ActionRow(
                    ui.Button(label="YouTube", url=video_url, style=discord.ButtonStyle.link),
                    ui.Button(label="Stream", url=file_url, style=discord.ButtonStyle.link),
                    ui.Button(label="Download", url=download_url, style=discord.ButtonStyle.link)
                ),
                accent_colour=discord.Colour.green()
            )
        
        layout_view = AudioLayoutView()
        await interaction.channel.send(view=layout_view)

        print(f" Downloaded audio: {metadata.get('title', 'Unknown')} -> {file_uuid}")

    except Exception as e:
        error_embed = create_error_embed(str(e), url)
        try:
            await interaction.edit_original_response(embed=error_embed)
        except:
            await interaction.followup.send(embed=error_embed)


@bot.tree.command(name="stats", description="Show bot statistics and file storage info")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def show_stats(interaction: discord.Interaction):
    stats = bot.file_manager.get_stats()

    embed = discord.Embed(
        title=" Bot Statistics",
        color=0x5865F2,
        timestamp=discord.utils.utcnow()
    )

    embed.add_field(
        name=" Files Stored",
        value=str(stats['total_files']),
        inline=True
    )

    embed.add_field(
        name=" Total Size",
        value=f"{stats['total_size_mb']} MB",
        inline=True
    )

    embed.add_field(
        name="⏰ File Expiry",
        value=f"{stats['expiry_hours']} hours",
        inline=True
    )

    embed.add_field(
        name=" File Server",
        value=FILE_SERVER_DOMAIN,
        inline=True
    )

    embed.add_field(
        name=" Servers",
        value=str(len(bot.guilds)),
        inline=True
    )

    embed.set_footer(text="YouTube Downloader Bot")

    await interaction.response.send_message(embed=embed)


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print(" Error: DISCORD_TOKEN not found in .env file")
        exit(1)

    print(" Starting YouTube Downloader Bot...")
    bot.run(DISCORD_TOKEN)
