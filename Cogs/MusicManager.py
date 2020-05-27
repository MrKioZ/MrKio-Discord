import discord, asyncio, itertools, sys, traceback, time, aiohttp
from urllib.parse import quote
from bs4 import BeautifulSoup
from discord.ext import commands
from discord import player
from async_timeout import timeout
from functools import partial
from youtube_dl import YoutubeDL


ytdlopts = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # ipv6 addresses cause issues sometimes
}

ffmpegopts = {
    'before_options': '-nostdin',
    'options': '-vn'
}

ytdl = YoutubeDL(ytdlopts)

def human_format(num):
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    # add more suffixes if you need them
    return '%.2f%s' % (num, ['', 'K', 'M', 'B', 'T', 'P'][magnitude])

async def searchQuery(SELECTED_URL):
    async with aiohttp.ClientSession() as session:
        async with session.get(SELECTED_URL) as resp:
            text = await resp.read()

    soup = BeautifulSoup(text.decode('utf-8'), 'lxml')
    videos = {}
    for indx, vid in enumerate(soup.findAll(attrs={'class':'yt-uix-tile-link'})):

        if 'watch' in vid['href']:
            videos[('https://www.youtube.com' + vid['href'].split('&', 1)[0])] = vid['title']

        if indx == 4:
            break

    return videos


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


class VoiceConnectionError(commands.CommandError):
    """Custom Exception class for connection errors."""


class InvalidVoiceChannel(VoiceConnectionError):
    """Exception for cases of invalid Voice Channels."""


class YTDLSource(discord.PCMVolumeTransformer):

    def __init__(self, source, *, data, requester):
        super().__init__(source)
        self.requester = requester

        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.uploader = data.get('uploader')
        self.url = data.get('url')
        self.web_url = data.get('webpage_url')
        self.desc = data.get('description')
        self.views = human_format(data.get('view_count'))
        self.likes = human_format(data.get('like_count'))
        self.dislikes = human_format(data.get('dislike_count'))
        self.duration = str(time.strftime('%H:%M:%S', time.gmtime(data.get('duration'))))

        # YTDL info dicts (data) have other useful information you might want
        # https://github.com/rg3/youtube-dl/blob/master/README.md

    def __getitem__(self, item: str):
        """Allows us to access attributes similar to a dict.
        This is only useful when you are NOT downloading.
        """
        return self.__getattribute__(item)

    @classmethod
    async def create_source(cls, ctx, search: str, *, loop, download=False):
        loop = loop or asyncio.get_event_loop()

        to_run = partial(ytdl.extract_info, url=search, download=download)
        data = await loop.run_in_executor(None, to_run)

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
        data['duration'] = str(time.strftime('%H:%M:%S', time.gmtime(int(data.get('duration'))))).replace('00:','')

        embed = discord.Embed(color=0xff171d, title=data.get("title"), url=str(data.get("webpage_url")), description="Views: " + human_format(data.get("view_count")) + " | Likes: " + human_format(data.get("like_count")) + " | Dislike: " + human_format(data.get("dislike_count")))
        embed.set_author(name="Added to Queue", icon_url=ctx.author.avatar_url)
        embed.set_thumbnail(url=data.get("thumbnail"))
        embed.add_field(name="duration", value=data.get('duration'), inline=True)
        embed.add_field(name="uploaded by", value=data.get("uploader"), inline=True)

        embed.set_footer(text="Requested by " + str(ctx.author))

        await ctx.send(embed=embed)#embed=embed, delete_after=15)

        if download:
            source = ytdl.prepare_filename(data)
        else:
            return {'webpage_url': data['webpage_url'], 'requester': ctx.author, 'title': data['title']}

        return cls(FFmpegPCMAudio(source), data=data, requester=ctx.author)

    @classmethod
    async def regather_stream(cls, data, *, loop):
        """Used for preparing a stream, instead of downloading.
        Since Youtube Streaming links expire."""
        loop = loop or asyncio.get_event_loop()
        requester = data['requester']

        to_run = partial(ytdl.extract_info, url=data['webpage_url'], download=False)
        data = await loop.run_in_executor(None, to_run)

        return cls(FFmpegPCMAudio(data['url']), data=data, requester=requester)


class MusicPlayer:

    __slots__ = ('bot', '_guild', '_channel', '_cog', 'queue', 'next', 'current', 'np', 'volume')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.np = None  # Now playing message
        self.volume = .5
        self.current = None

        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        """Our main player loop."""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next.clear()

            try:
                # Wait for the next song. If we timeout cancel the player and disconnect...
                async with timeout(300):  # 5 minutes...
                    source = await self.queue.get()
            except asyncio.TimeoutError:
                return self.destroy(self._guild)

            if not isinstance(source, YTDLSource):
                # Source was probably a stream (not downloaded)
                # So we should regather to prevent stream expiration
                try:
                    source = await YTDLSource.regather_stream(source, loop=self.bot.loop)
                except Exception as e:
                    await self._channel.send(f'There was an error processing your song.\n'
                                             f'```css\n[{e}]\n```')
                    continue

            source.volume = self.volume
            self.current = source

            self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))

            self.np = await self._channel.send(":arrow_forward: **playing now** `" + source.title + "`", delete_after=10)

            await self.next.wait()

            # Make sure the FFmpeg process is cleaned up.
            source.cleanup()
            self.current = None

            try:
                # We are no longer playing this song...
                await self.np.delete()
            except discord.HTTPException:
                pass

    def destroy(self, guild):
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self._cog.cleanup(guild))


class Music(commands.Cog):
    """Music related commands."""

    __slots__ = ('bot', 'players')

    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            del self.players[guild.id]
        except KeyError:
            pass

    async def __local_check(self, ctx):
        """A local check which applies to all commands in this cog."""
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    async def __error(self, ctx, error):
        """A local error handler for all errors arising from commands in this cog."""
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.send('This command can not be used in Private Messages.')
            except discord.HTTPException:
                pass
        elif isinstance(error, InvalidVoiceChannel):
            await ctx.send('Error connecting to Voice Channel. '
                           'Please make sure you are in a valid channel or provide me with one')

        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    def get_player(self, ctx):
        """Retrieve the guild player, or generate one."""
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx)
            self.players[ctx.guild.id] = player

        return player

    @commands.command(name='connect', aliases=['join'])
    async def connect_(self, ctx, *, channel: discord.VoiceChannel=None):
        """Connect to voice.
        Parameters
        ------------
        channel: discord.VoiceChannel [Optional]
            The channel to connect to. If a channel is not specified, an attempt to join the voice channel you are in
            will be made.
        This command also handles moving the bot to different channels.
        """
        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                raise InvalidVoiceChannel('No channel to join. Please either specify a valid channel or join one.')

        vc = ctx.voice_client

        if vc:
            if vc.channel.id == channel.id:
                return
            try:
                await vc.move_to(channel)
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'Moving to channel: <{channel}> timed out.')
        else:
            try:
                await channel.connect()
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'Connecting to channel: <{channel}> timed out.')

        await ctx.send(f'Connected to: **{channel}**', delete_after=20)

    @commands.command(name='play', aliases=['sing'])
    async def play_(self, ctx, *, search: str):

        await ctx.trigger_typing()

        vc = ctx.voice_client

        if not vc:
            await ctx.invoke(self.connect_)

        player = self.get_player(ctx)

        if (not 'http://' in search) or (not 'https://' in search):
            query = quote(search)
            url = "https://www.youtube.com/results?search_query=" + query
            query = await searchQuery(url)

            result = ''

            urlz = []
            for indx, i in enumerate(query.keys()):
                urlz.append(i)
                if indx == 0:
                    result += '**'+str(indx+1)+'**. `'+query[i]+'`'
                else:
                    result += '\n\n**'+str(indx+1)+'**. `'+query[i]+'`'

            embed = discord.Embed(color=0xff171d, title="Search Results", description=result)
            embed.set_author(name="Requested Song", icon_url=ctx.author.avatar_url)
            embed.set_footer(text="requested by "+str(ctx.author))
            QueryMsg = await ctx.send(embed=embed, delete_after=61)

            await QueryMsg.add_reaction('1️⃣')
            await QueryMsg.add_reaction('2️⃣')
            await QueryMsg.add_reaction('3️⃣')
            await QueryMsg.add_reaction('4️⃣')
            await QueryMsg.add_reaction('5️⃣')

            check = lambda reaction, user: ctx.author == user
            reaction = ''
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                await QueryMsg.delete()
            except asyncio.TimeoutError:
                await ctx.send(':x: **you did not react fast enough**', delete_after=10)
                await QueryMsg.delete()

            if '1' in str(reaction):
                source = await YTDLSource.create_source(ctx, urlz[0], loop=self.bot.loop, download=False)
            elif '2' in str(reaction):
                source = await YTDLSource.create_source(ctx, urlz[1], loop=self.bot.loop, download=False)
            elif '3' in str(reaction):
                source = await YTDLSource.create_source(ctx, urlz[2], loop=self.bot.loop, download=False)
            elif '4' in str(reaction):
                source = await YTDLSource.create_source(ctx, urlz[3], loop=self.bot.loop, download=False)
            elif '5' in str(reaction):
                source = await YTDLSource.create_source(ctx, urlz[4], loop=self.bot.loop, download=False)

        elif ('youtube' in search) or ('youtu.be' in search):
            source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop, download=False)
        else:
            await ctx.send(':x: **This is not a Youtube URL!**')
            return
        # If download is False, source will be a dict which will be used later to regather the stream.
        # If download is True, source will be a FFmpegPCMAudio with a VolumeTransformer.
        #source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop, download=False)

        await player.queue.put(source)

    @commands.command(name='pause')
    async def pause_(self, ctx):
        """Pause the currently playing song."""
        vc = ctx.voice_client

        if not vc or not vc.is_playing():
            return await ctx.send('I am not currently playing anything!', delete_after=20)
        elif vc.is_paused():
            return

        vc.pause()
        await ctx.send(f'**`{ctx.author}`**: Paused the song!')

    @commands.command(name='resume')
    async def resume_(self, ctx):
        """Resume the currently paused song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!', delete_after=20)
        elif not vc.is_paused():
            return

        vc.resume()
        await ctx.send(f'**`{ctx.author}`**: Resumed the song!')

    @commands.command(name='skip')
    async def skip_(self, ctx):
        """Skip the song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!', delete_after=20)

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return

        vc.stop()
        await ctx.send(f':fast_forward: **Song Skipped!**')

    @commands.command(name='queue', aliases=['q', 'playlist'])
    async def queue_info(self, ctx):
        """Retrieve a basic queue of upcoming songs."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently connected to voice!', delete_after=20)

        player = self.get_player(ctx)
        if player.queue.empty():
            return await ctx.send('There are currently no more queued songs.')

        # Grab up to 5 entries from the queue...
        upcoming = list(itertools.islice(player.queue._queue, 0, 5))

        fmt = '\n'.join(str(indx+1)+f'**`{i["title"]}`**' for indx, i in enumerate(upcoming))
        embed = discord.Embed(color=0xff171d, title=f'Upcoming - Next {len(upcoming)}', description=fmt)

        await ctx.send(embed=embed)

    @commands.command(name='now_playing', aliases=['np', 'current', 'currentsong', 'playing'])
    async def now_playing_(self, ctx):
        """Display information about the currently playing song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently connected to voice!', delete_after=20)

        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send('I am not currently playing anything!')

        try:
            # Remove our previous now_playing message.
            await player.np.delete()
        except discord.HTTPException:
            pass

        player.np = await ctx.send(f'**Now Playing:** `{vc.source.title}` '
                                   f'requested by `{vc.source.requester}`')

    @commands.command(name='volume', aliases=['vol'])
    async def change_volume(self, ctx, *, vol: float):
        """Change the player volume.
        Parameters
        ------------
        volume: float or int [Required]
            The volume to set the player to in percentage. This must be between 1 and 100.
        """
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently connected to voice!', delete_after=20)

        if not 0 < vol < 101:
            return await ctx.send('Please enter a value between 1 and 100.')

        player = self.get_player(ctx)

        if vc.source:
            vc.source.volume = vol / 100

        player.volume = vol / 100
        await ctx.send(f'**`{ctx.author}`**: Set the volume to **{vol}%**')

    @commands.command(name='stop', aliases=['leave'])
    async def stop_(self, ctx):
        """Stop the currently playing song and destroy the player.
        !Warning!
            This will destroy the player assigned to your guild, also deleting any queued songs and settings.
        """
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!', delete_after=20)

        await self.cleanup(ctx.guild)
