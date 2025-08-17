import discord
from discord import app_commands
from discord.ext import commands
from database import database as db

class ShopInterface(commands.Cog):
    def __init__(self, bot: commands.Bot): 
        self.bot = bot
        self.config = bot.config
        self.embed_color = discord.Color(int(self.config['EMBED_COLOR'], 16))

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # check khi het boost
        if before.premium_since and not after.premium_since:
            # check dung server
            if before.guild.id != self.config['GUILD_ID']:
                return

            # tim role custom trong db
            custom_role_data = db.get_custom_role(before.id, before.guild.id)
            if not custom_role_data:
                return # ko co role custom

            role_id = custom_role_data['role_id']
            role_obj = before.guild.get_role(role_id)

            if role_obj:
                try:
                    await role_obj.delete(reason=f"Thành viên {before.name} đã hết boost server.")
                    
                    # gui dm thong bao
                    try:
                        await before.send(
                            f"Cảm ơn bạn đã từng boost server! "
                            f"Role tùy chỉnh **{role_obj.name}** của bạn đã được gỡ bỏ do bạn không còn boost server nữa. "
                            f"Hãy boost lại để có thể tạo role mới nhé!"
                        )
                    except discord.Forbidden:
                        pass # ko a/h neu ko gui dc dm
                except discord.Forbidden:
                    # bot ko co quyen xoa role
                    pass
                except Exception:
                    pass # bo qua cac loi khac

            # luon xoa data du user het boost
            db.delete_custom_role_data(before.id, before.guild.id)

async def setup(bot: commands.Bot):
    await bot.add_cog(ShopInterface(bot))