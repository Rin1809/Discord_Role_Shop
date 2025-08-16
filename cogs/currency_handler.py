import discord
from discord.ext import commands
from database import database as db

class CurrencyHandler(commands.Cog):
    def __init__(self, bot: commands.Bot): 
        self.bot = bot
        self.config = bot.config
        self.guild_id = self.config['GUILD_ID']
        self.rates_config = self.config['CURRENCY_RATES']

    def _get_rates_for_channel(self, channel: discord.TextChannel):
        # Mac dinh
        rates = self.rates_config.get('default', {}).copy()
        
        # Kiem tra category
        if channel.category_id:
            category_rates = self.rates_config.get('categories', {}).get(str(channel.category_id))
            if category_rates:
                rates.update(category_rates)
        
        # Kiem tra channel
        channel_rates = self.rates_config.get('channels', {}).get(str(channel.id))
        if channel_rates:
            rates.update(channel_rates)
            
        return rates

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        
        if message.guild.id != self.guild_id:
            return

        # Lay rate
        current_rates = self._get_rates_for_channel(message.channel)
        messages_per_coin = current_rates.get('MESSAGES_PER_COIN')
        
        # Neu kenh nay ko co rate cho message thi bo qua
        if not messages_per_coin or messages_per_coin <= 0:
            return

        user_data = db.get_or_create_user(message.author.id, message.guild.id)
        
        new_message_count = user_data['message_count'] + 1
        
        # Tinh toan
        coins_to_add = new_message_count // messages_per_coin
        remaining_messages = new_message_count % messages_per_coin
        
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
        if not payload.guild_id:
            return

        if payload.guild_id != self.guild_id:
            return
        
        if payload.user_id == self.bot.user.id:
            return
        
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        # Lay rate
        current_rates = self._get_rates_for_channel(channel)
        reactions_per_coin = current_rates.get('REACTIONS_PER_COIN')

        # Neu kenh nay ko co rate cho reaction thi bo qua
        if not reactions_per_coin or reactions_per_coin <= 0:
            return

        user_data = db.get_or_create_user(payload.user_id, payload.guild_id)

        new_reaction_count = user_data['reaction_count'] + 1

        # Tinh toan
        coins_to_add = new_reaction_count // reactions_per_coin
        remaining_reactions = new_reaction_count % reactions_per_coin

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