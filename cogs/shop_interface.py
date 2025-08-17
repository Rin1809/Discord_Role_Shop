import discord
from discord.ext import commands

class ShopInterface(commands.Cog):
    def __init__(self, bot: commands.Bot): 
        self.bot = bot
        self.config = bot.config

async def setup(bot: commands.Bot):
    await bot.add_cog(ShopInterface(bot))