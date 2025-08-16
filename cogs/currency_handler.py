# cogs/currency_handler.py
import discord
from discord.ext import commands
from database import database as db

class CurrencyHandler(commands.Cog):
    def __init__(self, bot: commands.Bot): 
        self.bot = bot
        self.config = bot.config
        self.guild_id = self.config['GUILD_ID']
        self.rates = self.config['CURRENCY_RATES']

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Bỏ qua bot và tin nhắn riêng
        if message.author.bot or not message.guild:
            return
        
        # Chỉ hoạt động trên server đã cấu hình
        if message.guild.id != self.guild_id:
            return

        user_data = db.get_or_create_user(message.author.id, message.guild.id)
        
        new_message_count = user_data['message_count'] + 1
        
        coins_to_add = new_message_count // self.rates['MESSAGES_PER_COIN']
        remaining_messages = new_message_count % self.rates['MESSAGES_PER_COIN']
        
        if coins_to_add > 0:
            new_balance = user_data['balance'] + coins_to_add
            db.update_user_data(message.author.id, message.guild.id, 
                                balance=new_balance, 
                                message_count=remaining_messages)
        else:
            db.update_user_data(message.author.id, message.guild.id, 
                                message_count=new_message_count)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # Bỏ qua tin nhắn riêng
        if not payload.guild_id:
            return

        # Chỉ hoạt động trên server đã cấu hình
        if payload.guild_id != self.guild_id:
            return
        
        # Bỏ qua reaction của chính bot
        if payload.user_id == self.bot.user.id:
            return

        user_data = db.get_or_create_user(payload.user_id, payload.guild_id)

        new_reaction_count = user_data['reaction_count'] + 1

        coins_to_add = new_reaction_count // self.rates['REACTIONS_PER_COIN']
        remaining_reactions = new_reaction_count % self.rates['REACTIONS_PER_COIN']

        if coins_to_add > 0:
            new_balance = user_data['balance'] + coins_to_add
            db.update_user_data(payload.user_id, payload.guild_id,
                                balance=new_balance,
                                reaction_count=remaining_reactions)
        else:
            db.update_user_data(payload.user_id, payload.guild_id,
                                reaction_count=new_reaction_count)


async def setup(bot: commands.Bot):
    await bot.add_cog(CurrencyHandler(bot))