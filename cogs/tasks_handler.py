import discord
from discord.ext import commands, tasks
from database import database as db
import logging

class TasksHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config
        self.embed_color = discord.Color(int(self.config['EMBED_COLOR'], 16))
        self.leaderboard_message = None
        self.update_leaderboard.start()

    def cog_unload(self):
        self.update_leaderboard.cancel()

    @tasks.loop(minutes=1)
    async def update_leaderboard(self):
        thread_id = self.config.get('LEADERBOARD_THREAD_ID')
        guild_id = self.config.get('GUILD_ID')
        
        if not thread_id or not guild_id:
            return

        guild = self.bot.get_guild(int(guild_id))
        thread = self.bot.get_channel(int(thread_id))
        
        if not guild or not thread:
            logging.warning("Leaderboard thread or guild not found. Skipping update.")
            return

        top_users = db.get_top_users(guild.id, limit=20)
        
        if top_users is None:
            logging.error("Failed to fetch top users from database.")
            return

        embed = discord.Embed(
            title="Bảng Xếp Hạng Đại Gia <:b_34:1343877618340204627>",
            description="Top 20 thành viên có số dư coin cao nhất server.",
            color=self.embed_color,
            timestamp=discord.utils.utcnow()
        )

        leaderboard_lines = []
        for i, user_data in enumerate(top_users):
            member = guild.get_member(user_data['user_id'])
            display_name = member.mention if member else f"Người dùng rời server"
            
            emoji = ""
            if i == 0: emoji = "🥇"
            elif i == 1: emoji = "🥈"
            elif i == 2: emoji = "🥉"
            else: emoji = "🔹"
            
            balance_formatted = f"{user_data['balance']:,}"
            
            line = f"{emoji} **Hạng {i+1}:** {display_name}\n> **Số dư:** `{balance_formatted}` <a:coin:1406137409384480850>"
            leaderboard_lines.append(line)
        
        if not leaderboard_lines:
            embed.description = "Chưa có ai trên bảng xếp hạng."
        else:
            embed.description = "\n\n".join(leaderboard_lines)

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        if self.config.get('EARNING_RATES_IMAGE_URL'):
            embed.set_image(url=self.config.get('EARNING_RATES_IMAGE_URL'))

        embed.set_footer(text="Cập nhật mỗi 1 phút", icon_url=self.bot.user.avatar.url)

        try:
            if self.leaderboard_message:
                await self.leaderboard_message.edit(content=None, embed=embed)
            else:
                async for msg in thread.history(limit=5):
                    if msg.author.id == self.bot.user.id:
                        self.leaderboard_message = msg
                        await self.leaderboard_message.edit(content=None, embed=embed)
                        return
                
                self.leaderboard_message = await thread.send(embed=embed)

        except discord.NotFound:
            self.leaderboard_message = None 
            try:
                self.leaderboard_message = await thread.send(embed=embed)
            except Exception as e:
                logging.error(f"Failed to send new leaderboard message: {e}")
        except Exception as e:
            logging.error(f"Failed to update leaderboard: {e}")
            self.leaderboard_message = None


    @update_leaderboard.before_loop
    async def before_update_leaderboard(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(TasksHandler(bot))