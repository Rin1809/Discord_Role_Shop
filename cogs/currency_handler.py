import discord
from discord.ext import commands
from database import database as db
import collections

class CurrencyHandler(commands.Cog):
    def __init__(self, bot: commands.Bot): 
        self.bot = bot
        self.config = bot.config
        self.guild_id = self.config['GUILD_ID']
        self.rates_config = self.config['CURRENCY_RATES']

    def _get_boost_multiplier(self, member: discord.Member) -> int:
        if not member:
            return 1
            
        # premium_since chi check co boost hay ko, ko check so luong
        if not member.premium_since:
            return 1
        
        # Dem so lan member xuat hien trong list booster
        boost_count = member.guild.premium_subscribers.count(member)
        
        if boost_count > 0:
            return boost_count + 1
        return 1

    def _get_rates_for_channel(self, channel: discord.TextChannel):
        rates = self.rates_config.get('default', {}).copy()
        
        if channel.category_id:
            category_rates = self.rates_config.get('categories', {}).get(str(channel.category_id))
            if category_rates:
                rates.update(category_rates)
        
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

        current_rates = self._get_rates_for_channel(message.channel)
        messages_per_coin = current_rates.get('MESSAGES_PER_COIN')
        
        if not messages_per_coin or messages_per_coin <= 0:
            return

        user_data = db.get_or_create_user(message.author.id, message.guild.id)
        
        new_message_count = user_data['message_count'] + 1
        
        coins_to_add = new_message_count // messages_per_coin
        remaining_messages = new_message_count % messages_per_coin
        
        if coins_to_add > 0:
            # Ap dung he so nhan
            multiplier = self._get_boost_multiplier(message.author)
            final_coins_to_add = coins_to_add * multiplier

            new_balance = user_data['balance'] + final_coins_to_add
            db.update_user_data(message.author.id, message.guild.id, 
                                balance=new_balance, 
                                message_count=remaining_messages)
        else:
            db.update_user_data(message.author.id, message.guild.id, 
                                message_count=new_message_count)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id or payload.guild_id != self.guild_id or payload.member.bot:
            return
        
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        current_rates = self._get_rates_for_channel(channel)
        reactions_per_coin = current_rates.get('REACTIONS_PER_COIN')

        if not reactions_per_coin or reactions_per_coin <= 0:
            return

        user_data = db.get_or_create_user(payload.user_id, payload.guild_id)

        new_reaction_count = user_data['reaction_count'] + 1

        coins_to_add = new_reaction_count // reactions_per_coin
        remaining_reactions = new_reaction_count % reactions_per_coin

        if coins_to_add > 0:
            # Ap dung he so nhan
            multiplier = self._get_boost_multiplier(payload.member)
            final_coins_to_add = coins_to_add * multiplier

            new_balance = user_data['balance'] + final_coins_to_add
            db.update_user_data(payload.user_id, payload.guild_id,
                                balance=new_balance,
                                reaction_count=remaining_reactions)
        else:
            db.update_user_data(payload.user_id, payload.guild_id,
                                reaction_count=new_reaction_count)


async def setup(bot: commands.Bot):
    await bot.add_cog(CurrencyHandler(bot))