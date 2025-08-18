import discord
from discord.ext import commands
from database import database as db

class ShopInterface(commands.Cog):
    def __init__(self, bot: commands.Bot): 
        self.bot = bot
        # dung global config cho cac id dc phep
        self.authorized_guilds = self.bot.global_config['AUTHORIZED_GUILD_IDS']

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.guild.id not in self.authorized_guilds:
            return
            
        # check khi het boost
        if before.premium_since and not after.premium_since:
            # tim role custom trong db
            custom_role_data = db.get_custom_role(before.id, before.guild.id)
            if not custom_role_data:
                return

            role_id = custom_role_data['role_id']
            role_obj = before.guild.get_role(role_id)

            if role_obj:
                try:
                    await role_obj.delete(reason=f"Thanh vien het boost server.")
                    
                    try:
                        await before.send(
                            f"Cảm ơn bạn đã từng boost server! "
                            f"Role tùy chỉnh **{role_obj.name}** của bạn đã được gỡ bỏ do bạn không còn boost server nữa. "
                            f"Hãy boost lại để có thể tạo role mới nhé!"
                        )
                    except discord.Forbidden:
                        pass
                except discord.Forbidden:
                    pass
                except Exception:
                    pass

            db.delete_custom_role_data(before.id, before.guild.id)

async def setup(bot: commands.Bot):
    await bot.add_cog(ShopInterface(bot))