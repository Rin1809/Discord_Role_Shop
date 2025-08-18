import discord
from discord.ext import commands
from database import database as db
import collections

class CurrencyHandler(commands.Cog):
    def __init__(self, bot: commands.Bot): 
        self.bot = bot
        self.authorized_guilds = self.bot.global_config['AUTHORIZED_GUILD_IDS']

    def _get_boost_multiplier(self, member: discord.Member) -> int:
        if member and member.id == 873576591693873252:
            return 3

        if not member or not member.premium_since:
            return 1
        
        boost_count = sum(1 for m in member.guild.premium_subscribers if m.id == member.id)
        
        if boost_count > 0:
            return boost_count + 1
        return 1

    def _get_rates_for_channel(self, guild_config: dict, channel: discord.TextChannel):
        if not guild_config:
            return {}
            
        rates_config = guild_config.get('CURRENCY_RATES', {})
        rates = rates_config.get('default', {}).copy()
        
        if channel.category_id:
            category_rates = rates_config.get('categories', {}).get(str(channel.category_id))
            if category_rates:
                rates.update(category_rates)
        
        channel_rates = rates_config.get('channels', {}).get(str(channel.id))
        if channel_rates:
            rates.update(channel_rates)
            
        return rates

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        
        if message.guild.id not in self.authorized_guilds:
            return

        guild_config = self.bot.guild_configs.get(str(message.guild.id))
        if not guild_config:
            return

        current_rates = self._get_rates_for_channel(guild_config, message.channel)
        messages_per_coin = current_rates.get('MESSAGES_PER_COIN')
        
        if not messages_per_coin or messages_per_coin <= 0:
            return

        user_data = db.get_or_create_user(message.author.id, message.guild.id)
        
        new_message_count = user_data['message_count'] + 1
        
        coins_to_add = new_message_count // messages_per_coin
        remaining_messages = new_message_count % messages_per_coin
        
        if coins_to_add > 0:
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
        if not payload.guild_id or payload.guild_id not in self.authorized_guilds or payload.member.bot:
            return
        
        guild_config = self.bot.guild_configs.get(str(payload.guild_id))
        if not guild_config:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        current_rates = self._get_rates_for_channel(guild_config, channel)
        reactions_per_coin = current_rates.get('REACTIONS_PER_COIN')

        if not reactions_per_coin or reactions_per_coin <= 0:
            return

        user_data = db.get_or_create_user(payload.user_id, payload.guild_id)
        new_reaction_count = user_data['reaction_count'] + 1
        coins_to_add = new_reaction_count // reactions_per_coin
        remaining_reactions = new_reaction_count % reactions_per_coin

        if coins_to_add > 0:
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