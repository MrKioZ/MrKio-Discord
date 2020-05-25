import asyncio, discord, shlex
from discord import player
import youtube_dl

from discord.ext import commands

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-qscale 0'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class FFmpegPCMAudio(player.FFmpegPCMAudio):

    def __init__(self, source, *, executable='ffmpeg', pipe=False, stderr=None,
                 before_options=None, after_input=None, options=None,
                 reconnect=True):

        args = []
        subprocess_kwargs = {'stdin': source if pipe else None, 'stderr': stderr}

        if reconnect:
            args.extend(('-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5'))

        if isinstance(before_options, str):
            args.extend(shlex.split(before_options))

        args.append('-i')
        args.append('-' if pipe else source)

        if isinstance(after_input, str):
            args.extend(shlex.split(after_input))

        args.extend(('-f', 's16le',
                     '-ar', '48000',
                     '-ac', '2',
                     '-loglevel', 'panic'))

        if isinstance(options, str):
            args.extend(shlex.split(options))

        args.append('pipe:1')

        # skipcq: PYL-E1003
        # This is an intentional choice since we don't wanna call the parent
        # init but instead the init of its parent
        super(player.FFmpegPCMAudio, self).__init__(source, executable=executable,
                                                    args=args, **subprocess_kwargs)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.uploader = data.get('uploader')
        self.url = data.get('url')
        self.main_url = data.get('webpage_url')
        self.desc = data.get('description')
        self.views = str(data.get('view_count'))
        self.likes = str(data.get('like_count'))
        self.dislikes = str(data.get('dislike_count'))
        self.duration = str(data.get('duration'))

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)

        val = cls(FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

        return val



class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def join(self, ctx, *, channel: discord.VoiceChannel):
        """Joins a voice channel"""

        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)

        await channel.connect()

    @commands.command()
    async def leave(self, ctx, *, channel: discord.VoiceChannel):
        if ctx.voice_client is not None:
            await channel.leave()

    @commands.command()
    async def play(self, ctx, *, url):

        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)

            embed=discord.Embed(color=0xff171d, title="Playing now: "+player.title, url=player.main_url, description="Views: " + player.views + " | Likes: " + player.likes + " | Dislike: " + player.dislikes)
            embed.set_thumbnail(url=player.thumbnail)
            
            embed.add_field(name="duration", value=player.duration, inline=True)
            embed.add_field(name="uploaded by", value=player.uploader, inline=True)

            embed.set_footer(text="Requested by " + ctx.author.name + "#" + ctx.author.discriminator)
            await ctx.send(embed=embed)

        # await ctx.send(':musical_note: Now playing: **{}**'.format(player.title))

    @commands.command()
    async def volume(self, ctx, volume: int):

        if ctx.voice_client is None:
            return await ctx.send(":x: Not connected to a voice channel.")

        ctx.voice_client.source.volume = volume / 100
        await ctx.send("Changed volume to {}%".format(volume))

    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""

        await ctx.voice_client.disconnect()

    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
                print('Connected Successfully')
            else:
                await ctx.send(":x: **You are not connected to a voice channel.**")
                raise commands.CommandError("Author not connected to a voice channel.")
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()
