import asyncio
import socket
import discord
import requests
from discord import app_commands, ui
from discord.ext import commands
from dotenv import load_dotenv
from pathlib import Path
from os import getenv

from downloader import YouTubeDownloader, format_duration, format_views, format_size
from file_manager import FileManager
from file_server import FileServer
from embed_builder import create_error_embed, create_processing_embed

load_dotenv()

DISCORD_TOKEN = getenv('DISCORD_TOKEN')
FILE_SERVER_PORT = int(getenv('FILE_SERVER_PORT', '3000'))
DOWNLOAD_DIR = getenv('DOWNLOAD_DIR', './downloads')
UPLOAD_DIR = getenv('UPLOAD_DIR', './uploads')
FILE_EXPIRY_HOURS = int(getenv('FILE_EXPIRY_HOURS', '24'))


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def get_server_domain() -> str:
    domain = getenv('FILE_SERVER_DOMAIN', 'auto')
    if domain.lower() == 'auto':
        ip = get_local_ip()
        print(f" Auto-detected local IP: {ip}")
        return f"http://{ip}:{FILE_SERVER_PORT}"
    return domain


def fetch_dislikes(video_id: str) -> int:
    try:
        resp = requests.get(
            "https://returnyoutubedislikeapi.com/Votes",
            params={"videoId": video_id},
            timeout=5
        )
        if resp.ok:
            return resp.json().get("dislikes", 0)
    except Exception:
        pass
    return 0


FILE_SERVER_DOMAIN = get_server_domain()


class YouTubeBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=discord.Intents.default(),
            allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
            allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
            activity=discord.Activity(type=discord.ActivityType.watching, name="YouTube | /video /audio")
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


def build_info_text(title: str, uploader: str, views: int, duration: int, 
                    likes: int, dislikes: int, size_bytes: int, icon: str, extra: str = "") -> str:
    text = f"**{title}**\n"
    text += f"{icon} {uploader}\n"
    text += f"👁️ {format_views(views)} views • ⏱️ {format_duration(duration)}\n"
    text += f"👍 {format_views(likes)} • 👎 {format_views(dislikes)}\n"
    text += f"📁 {format_size(size_bytes)}{extra} • ⏳ Expires in {FILE_EXPIRY_HOURS}h"
    return text


async def process_download(interaction: discord.Interaction, url: str, is_audio: bool, hidden: bool = False):
    await interaction.response.defer(ephemeral=True)

    try:
        await interaction.followup.send(embed=create_processing_embed(url, is_audio), ephemeral=True)

        loop = asyncio.get_event_loop()
        download_fn = bot.downloader.download_audio if is_audio else bot.downloader.download_video
        success, error, metadata = await loop.run_in_executor(None, download_fn, url)

        if not success:
            await interaction.followup.send(embed=create_error_embed(error, url), ephemeral=True)
            return

        video_id = metadata.get('id', '')
        file_path = bot.downloader.get_downloaded_file_path(video_id, is_audio=is_audio)

        if not file_path:
            await interaction.followup.send(embed=create_error_embed("Downloaded file not found", url), ephemeral=True)
            return

        file_uuid = bot.file_manager.add_file(
            file_path, file_path.name,
            video_title=metadata.get('title', 'Unknown'),
            video_id=video_id
        )

        if not file_uuid:
            await interaction.followup.send(embed=create_error_embed("Failed to process file", url), ephemeral=True)
            return

        ext = ".mp3" if is_audio else ".mp4"
        file_info = bot.file_manager.get_file_info(file_uuid)
        file_url = bot.file_server.get_file_url(file_uuid, download=False, extension=ext)
        download_url = bot.file_server.get_file_url(file_uuid, download=True, extension=ext)
        video_url = f"https://youtube.com/watch?v={video_id}"

        info_text = build_info_text(
            title=metadata.get('title', 'Unknown'),
            uploader=metadata.get('uploader', 'Unknown'),
            views=metadata.get('view_count', 0),
            duration=metadata.get('duration', 0),
            likes=metadata.get('like_count', 0),
            dislikes=fetch_dislikes(video_id),
            size_bytes=file_info.get('size_bytes', 0) if file_info else 0,
            icon="🎵" if is_audio else "📺",
            extra=" • 🎧 320kbps MP3" if is_audio else ""
        )

        if is_audio:
            class LayoutView(ui.LayoutView):
                container = ui.Container(
                    ui.TextDisplay(info_text),
                    ui.ActionRow(
                        ui.Button(label="YouTube", url=video_url, style=discord.ButtonStyle.link),
                        ui.Button(label="Stream", url=file_url, style=discord.ButtonStyle.link),
                        ui.Button(label="Download", url=download_url, style=discord.ButtonStyle.link)
                    ),
                    accent_colour=discord.Colour.green()
                )
        else:
            class LayoutView(ui.LayoutView):
                container = ui.Container(
                    ui.TextDisplay(info_text),
                    ui.MediaGallery(discord.MediaGalleryItem(media=file_url)),
                    ui.ActionRow(
                        ui.Button(label="YouTube", url=video_url, style=discord.ButtonStyle.link),
                        ui.Button(label="Stream", url=file_url, style=discord.ButtonStyle.link),
                        ui.Button(label="Download", url=download_url, style=discord.ButtonStyle.link)
                    ),
                    accent_colour=discord.Colour.red()
                )

        if hidden:
            await interaction.followup.send(view=LayoutView(), ephemeral=True)
        else:
            try:
                await interaction.channel.send(view=LayoutView())
            except discord.Forbidden:
                await interaction.followup.send(view=LayoutView(), ephemeral=False)

        media_type = "audio" if is_audio else "video"
        print(f" Downloaded {media_type}: {metadata.get('title', 'Unknown')} -> {file_uuid}")

    except Exception as e:
        try:
            await interaction.edit_original_response(embed=create_error_embed(str(e), url))
        except:
            await interaction.followup.send(embed=create_error_embed(str(e), url))


@bot.tree.command(name="video", description="Download a YouTube video in 1080p quality")
@app_commands.describe(url="The YouTube video URL to download", hidden="Only you can see the result")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def download_video(interaction: discord.Interaction, url: str, hidden: bool = False):
    await process_download(interaction, url, is_audio=False, hidden=hidden)


@bot.tree.command(name="audio", description="Download a YouTube video as 320kbps MP3")
@app_commands.describe(url="The YouTube video URL to extract audio from", hidden="Only you can see the result")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def download_audio(interaction: discord.Interaction, url: str, hidden: bool = False):
    await process_download(interaction, url, is_audio=True, hidden=hidden)


@bot.tree.command(name="stats", description="Show bot statistics and file storage info")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def show_stats(interaction: discord.Interaction):
    stats = bot.file_manager.get_stats()

    embed = discord.Embed(title=" Bot Statistics", color=0x5865F2, timestamp=discord.utils.utcnow())
    embed.add_field(name=" Files Stored", value=str(stats['total_files']), inline=True)
    embed.add_field(name=" Total Size", value=f"{stats['total_size_mb']} MB", inline=True)
    embed.add_field(name="⏰ File Expiry", value=f"{stats['expiry_hours']} hours", inline=True)
    embed.add_field(name=" File Server", value=FILE_SERVER_DOMAIN, inline=True)
    embed.add_field(name=" Servers", value=str(len(bot.guilds)), inline=True)
    embed.set_footer(text="YouTube Downloader Bot")

    await interaction.response.send_message(embed=embed)


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print(" Error: DISCORD_TOKEN not found in .env file")
        exit(1)

    print(" Starting YouTube Downloader Bot...")
    bot.run(DISCORD_TOKEN)
