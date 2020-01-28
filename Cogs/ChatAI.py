import discord
from discord.ext import commands

class ChatAI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_member = None

    @commands.Cog.listener()
    async def on_message(self, message):
        MemberName = message.author.name
        channel = message.channel

        if message.content.startswith("<@!{self.bot.user.id}>"):

            #Getting the message without the mention
            message = message.content.split(" ", 1)[1]
            repsonse = 'Hello world'

            await channel.send('{author.mention}',response)
            print('Message >',message)
            print('Repsonse >',repsonse)
