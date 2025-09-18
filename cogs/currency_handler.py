import discord
from discord.ext import commands
from database import database as db
import collections
import time

class CurrencyHandler(commands.Cog):
    def __init__(self, bot: commands.Bot): 
        self.bot = bot
        self.authorized_guilds = self.bot.global_config['AUTHORIZED_GUILD_IDS']
        self.boost_count_cache = {}
        self.BOOST_CACHE_DURATION = 300 # 5 phut

    def _get_boost_multiplier(self, member: discord.Member, guild_config: dict, user_data: dict) -> float:
        booster_config = guild_config.get('BOOSTER_MULTIPLIER_CONFIG', {})
        if not booster_config.get('ENABLED', False):
            return 1.0
        
        boost_count = 0
        
        fake_boosts = user_data.get('fake_boosts', 0)
        if fake_boosts > 0:
            boost_count = fake_boosts
        elif member and member.premium_since:
            # cache boost
            cache_key = (member.guild.id, member.id)
            now = time.time()
            
            if cache_key in self.boost_count_cache:
                cached_data = self.boost_count_cache[cache_key]
                if (now - cached_data['timestamp']) < self.BOOST_CACHE_DURATION:
                    return cached_data['multiplier']

            # tinh toan neu k co cache
            count = sum(1 for m in member.guild.premium_subscribers if m.id == member.id)
            boost_count = count
        
        if boost_count > 0:
            base_multiplier = booster_config.get('BASE_MULTIPLIER', 2.0)
            per_boost_addition = booster_config.get('PER_BOOST_ADDITION', 0.5)
            
            final_multiplier = base_multiplier + ((boost_count - 1) * per_boost_addition)

            if member:
                 self.boost_count_cache[(member.guild.id, member.id)] = {
                     'multiplier': final_multiplier,
                     'timestamp': time.time()
                 }
            return final_multiplier

        return 1.0

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
            multiplier = self._get_boost_multiplier(message.author, guild_config, user_data)
            final_coins_to_add = int(coins_to_add * multiplier) 

            if final_coins_to_add > 0:
                new_balance = user_data['balance'] + final_coins_to_add
                db.update_user_data(message.author.id, message.guild.id, 
                                    balance=new_balance, 
                                    message_count=remaining_messages)
            else: 
                db.update_user_data(message.author.id, message.guild.id, 
                                    message_count=new_message_count)
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
            multiplier = self._get_boost_multiplier(payload.member, guild_config, user_data)
            final_coins_to_add = int(coins_to_add * multiplier)

            if final_coins_to_add > 0:
                new_balance = user_data['balance'] + final_coins_to_add
                db.update_user_data(payload.user_id, payload.guild_id,
                                    balance=new_balance,
                                    reaction_count=remaining_reactions)
            else:
                 db.update_user_data(payload.user_id, payload.guild_id,
                                reaction_count=new_reaction_count)
        else:
            db.update_user_data(payload.user_id, payload.guild_id,
                                reaction_count=new_reaction_count)


async def setup(bot: commands.Bot):
    await bot.add_cog(CurrencyHandler(bot))