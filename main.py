import discord, asyncio, youtube_dl, random, os
from discord.ext import commands
from discord.voice_client import VoiceClient
from requests import get
from config import *
import time as timelibrary
from datetime import date
from iso639 import languages
from langdetect import detect
import praw

client = commands.Bot(command_prefix=BOT_PREFIX)
client.remove_command('help')

async def changing_status():
    await client.wait_until_ready()
    while not client.is_closed():
        status = [['playing', 'with code'], ['watching', 'my activity'], ['listening', 'MrKio']]
        for i in status:
            ActivityType = discord.ActivityType.playing
            if i[0].lower() == 'playing':
                ActivityType = discord.ActivityType.playing
            elif i[0].lower() == 'watching':
                ActivityType = discord.ActivityType.watching
            elif i[0].lower() == 'listening':
                ActivityType = discord.ActivityType.listening

            activity = discord.Activity(name=i[1], type=ActivityType)
            await client.change_presence(status=discord.Status.dnd, activity=activity)
            await asyncio.sleep(10)

async def calculate_age(born):
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

async def get_current_time():
    pm = False
    t = timelibrary.localtime()
    hour = timelibrary.strftime("%H", t)
    if int(hour) > 12:
        hour = int(hour)-12
        pm = True
    if pm:
        current_time = str(hour)+":"+timelibrary.strftime("%M")+" PM"
    else:
        current_time = str(hour)+":"+timelibrary.strftime("%M")+" AM"
    return current_time

async def reminder():
    await client.wait_until_ready()
    while not client.is_closed():
        with open('reminder.txt','r') as db:
            db = db.readlines()
            for line in db:
                topic = line.split(' ', 1)[1]
                try:
                    current_timestamp = int(line.split()[0])
                except TypeError:
                    print('Error: This is not a timestamp {}'.format(line.split()[0]))
                date_time = datetime.fromtimestamp(current_timestamp)
                if date_time < datetime.now():
                    #define the member to mention him
                    await ctx.send("**Reminder:** "+topic)

        await asnycio.sleep(30)

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
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

@client.event
async def on_ready():
    print(client.user.name + ' is ready!')
    print("ID: " + str(client.user.id))
    activity = discord.Activity(name='my activity', type=discord.ActivityType.watching)
    await client.change_presence(status=discord.Status.dnd, activity=activity)

@client.event
async def on_message(message):
    if message.author.bot:
        return
    author = message.author
    if "muted" in [y.name.lower() for y in author.roles]:
        await message.delete()
    await client.process_commands(message)

@client.command(pass_context=True)
async def reload(ctx):
    if ctx.author.id == Owner_ID:
        await ctx.channel.send(":floppy_disk: **Relaoding..**")
        await client.logout()
    else:
        ctx.channel.send(":x: **You are not Authorized to reload the bot!**")

@client.command(pass_context=True)
async def mute(ctx):
    author = ctx.message.author
    if "muted" in [y.name.lower() for y in author.roles]:
        target = ctx.message.mentions[0]
        role = discord.utils.get(ctx.guild.roles, name="muted")
        await target.remove_roles(role)
        await ctx.message.delete()
        response = await ctx.channel.send(":speaking_head: **{} was unmuted!**".format(target.mention))
        await asyncio.sleep(5)
        await response.delete()
    else:
        target = ctx.message.mentions[0]
        role = discord.utils.get(ctx.guild.roles, name="muted")
        await target.add_roles(role)
        await ctx.message.delete()
        response = await ctx.channel.send(":speak_no_evil: **{} was muted!**".format(target.mention))
        await asyncio.sleep(5)
        await response.delete()

@client.command(pass_context=True)
async def play(ctx):

    channel = None

    for vc in ctx.message.channel.guild.voice_channels:
        if not len(vc.members) > 0:
            avaliable = True
        if avaliable:
            for member in vc.members:
                if member.id == ctx.author.id:
                    channel = vc

    if channel is None:
        await ctx.send(':x: **Please join a voice channel**')
        return

    if (ctx.message.content.split()[1].lower().startswith('http://youtube.com/watch?v=')) or (ctx.message.content.split()[1].lower().startswith('https://youtube.com/watch?v=')):
        async with ctx.typing():

            url = ctx.message.content[1]
            player = await YTDLSource.from_url(url, loop=client.loop)
            if ctx.voice_client is None:
                await channel.connect()
                ctx.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)

                await ctx.send('Now playing: {}'.format(player.title))
    else:
        await ctx.send(':x: Please provide a youtube URL')

@client.command(pass_context=True)
async def bitcoin(ctx):
    json_resp = get('https://api.coindesk.com/v1/bpi/currentprice/btc.json').json()
    value = json_resp['bpi']['USD']['rate']
    embed = discord.Embed(color=0xff171d, thumbnail='https://cdn.pixabay.com/photo/2013/12/08/12/12/bitcoin-225079__340.png')

    embed.add_field(name="Bitcoin Price", value=value+"$ USD", inline=False)
    embed.set_footer(text="Requestsed by {}#{}".format(ctx.author.name,ctx.author.discriminator))
    await ctx.send(embed=embed)

@client.command(pass_context=True)
async def google(ctx):
    content = ctx.message.content.split(" ", 1)
    if len(content) > 1:
        content = content[1]
        await ctx.send(google(content))
    else:
        ctx.send('**!Google <Query>**')    

@client.command(pass_context=True)
async def say(ctx):
    await ctx.message.delete()
    content = ctx.message.content.split()
    content.pop(0)
    response = ''
    for word in content:
        response += " "+word
        if word == content[len(content)-1]:
            await ctx.send(response)

@client.command(pass_context=True)
async def help(ctx):
    embed = discord.Embed(color=0xff171d)
    embed.set_thumbnail(url=client.user.avatar_url)
    embed.add_field(name='Help menu', value=help_desc)
    the_creator = client.get_user(324786471678771200)
    embed.set_footer(text='This bot was made by ' + the_creator.name+"#"+the_creator.discriminator)
    await ctx.send(embed=embed)

@client.command(name='meme', pass_context=True)
async def meme(ctx):
    subreddits = ['memes','wholesomememes','whoooosh','dankmemes','funny']
    subreddit = random.choice(subreddits)

    reddit = praw.Reddit(client_id=REDDIT_CLIENT_ID,client_secret=REDDIT_CLIENT_SECRET,user_agent= 'prawagent')

    submissions = []
    for submission in reddit.subreddit(subreddit).hot(limit=25):
        if submission.url.endswith('jpg') or submission.url.endswith('png'):
            submissions.append(submission)

    submission = random.choice(submissions)

    embed = discord.Embed(color=EMBED_COLOR, title=submission.title)
    embed.set_image(url=submission.url)
    await ctx.send(embed=embed)

@client.command(pass_context=True)
async def langdetect(ctx):
    with ctx.typing():
        content = ctx.message.content.split(' ', 1)[1]
        current_language = languages.get(alpha2=detect(content))
        await ctx.send('I think this is '+current_language.name)


@client.command(pass_context=True)
async def remind(ctx):
    content = ctx.message.content
    topic = content.split(' ', 1)[1]

    def check(author, channel):
        return message.author == author and message.channel == channel

    await ctx.send('**Please type the date and the time for the task**')
    await ctx.send('**In the next format (e.x: 16Sep2012)**')
    time = await client.wait_for('message', check=check(ctx.author, ctx.channel), timeout=60)
    if time:
        try:
            scheduled = datetime.strptime('16Sep2012', '%d%b%Y')
            timestamp = datetime.timestamp(scheduled)
            async with open('reminder.txt','a+') as db:
                f.write(timestamp+" "+ctx.author.id+" "+topic)
        except ValueError:
            await ctx.send(':x: **Invalid format**')

@client.command(pass_context=True)
async def announce(ctx):
    announcement = ctx.message.content.split(' ', 1)[1].split(' ', 1)[1]
    everyone_mention = '**[**'+ctx.guild.default_role.name+'**]**'
    if ctx.message.channel_mentions:
        channel = ctx.message.channel_mentions[0]
        print(everyone_mention+announcement)
        await channel.send(everyone_mention+" "+announcement)
        await ctx.send(':mega: **Announcement has been made successfully!**')
    else:
        await ctx.send(':x: **Please mention the channel that you want to Announce it in**')

@client.command(pass_context=True)
async def time(ctx):
    current_time = await get_current_time()
    await ctx.send(":alarm_clock: **" + current_time + "**")

@client.command(pass_context=True)
async def serverinfo(ctx):
    guild = ctx.message.guild
    embed=discord.Embed(title="This is all i got from "+guild.name, color=0xff171d)
    embed.set_author(name=guild.name+"'s Information", icon_url=guild.icon_url)
    embed.set_thumbnail(url=guild.icon_url)
    year_creation = str(guild.created_at.year)
    month_creation = str(guild.created_at.month)
    day_creation = str(guild.created_at.day)
    embed.add_field(name="Created at", value=year_creation+"/"+month_creation+"/"+day_creation, inline=True)
    embed.add_field(name="Total Members", value=len(guild.members), inline=True)
    age = await calculate_age(guild.created_at)
    embed.add_field(name="Server Age", value="About " + str(age) + " Years", inline=True)
    embed.add_field(name="Server Owner", value=guild.owner.name+"#"+str(guild.owner.discriminator), inline=True)
    embed.add_field(name="Total Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Server Region", value=str(guild.region), inline=True)
    current_time = await get_current_time()
    embed.set_footer(text="Requested by " + ctx.author.name + "#" + ctx.author.discriminator + " at " + current_time)
    await ctx.send(embed=embed)

@client.command(pass_context=True)
async def userinfo(ctx):

    target = None
    if len(ctx.message.mentions) > 0:
        target = ctx.message.mentions[0]
    if target:
        joined = target.joined_at
        avatar_url = target.avatar_url

        embed=discord.Embed(title="This is all i got from "+target.name, color=0xff171d)
        embed.set_author(name=target.name+"'s Information",icon_url=avatar_url)
        embed.set_thumbnail(url=avatar_url)
        year_creation = str(target.created_at.year)
        month_creation = str(target.created_at.month)
        day_creation = str(target.created_at.day)
        embed.add_field(name="Joined Discord", value=year_creation+"/"+month_creation+"/"+day_creation, inline=True)
        year_join = str(target.joined_at.year)
        month_join = str(target.joined_at.month)
        day_join = str(target.joined_at.day)
        embed.add_field(name="Joined Server", value=year_join+"/"+month_join+"/"+day_join, inline=True)
        age = await calculate_age(ctx.author.created_at)
        embed.add_field(name="Account Age", value="About "+str(age)+" Years old!", inline=True)
        embed.add_field(name="Highest Role", value=target.top_role.mention, inline=True)
        current_time = await get_current_time()
        embed.set_footer(text="Requested by " + ctx.author.name + "#" + ctx.author.discriminator + " at " + current_time)
    else:
        embed=discord.Embed(title="This is all i got from User", color=0xff171d)
        embed.set_author(name=ctx.author.name+"'s Information", icon_url=ctx.author.avatar_url)
        embed.set_thumbnail(url=ctx.author.avatar_url)
        year_creation = str(ctx.author.created_at.year)
        month_creation = str(ctx.author.created_at.month)
        day_creation = str(ctx.author.created_at.day)
        embed.add_field(name="Joined Discord", value=year_creation+"/"+month_creation+"/"+day_creation, inline=True)
        year_join = str(ctx.author.joined_at.year)
        month_join = str(ctx.author.joined_at.month)
        day_join = str(ctx.author.joined_at.day)
        embed.add_field(name="Joined Server", value=year_join+"/"+month_join+"/"+day_join, inline=True)
        age = await calculate_age(ctx.author.created_at)
        embed.add_field(name="Account Age", value="About "+str(age)+" Years old!", inline=True)
        embed.add_field(name="Highest Role", value=ctx.author.top_role.mention, inline=True)
        current_time = await get_current_time()
        embed.set_footer(text="Requested by " + ctx.author.name + "#" + ctx.author.discriminator + " at " + current_time)

    await ctx.send(embed=embed)

@client.command(pass_context=True)
async def eightball(ctx):
    await ctx.send('**' + random.choice(eightball_random_answers) + '**')

client.loop.create_task(changing_status())
client.run(TOKEN, bot=True, reconnect=True)
