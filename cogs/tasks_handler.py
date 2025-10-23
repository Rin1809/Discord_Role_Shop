import discord
from discord.ext import commands, tasks
from database import database as db
import logging
from collections import Counter

class TasksHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

async def setup(bot: commands.Bot):
    await bot.add_cog(TasksHandler(bot))