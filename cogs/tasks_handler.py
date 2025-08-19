import discord
from discord.ext import commands, tasks
from database import database as db
import logging

class TasksHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.leaderboard_messages = {}
        self.update_leaderboard.start()

    def cog_unload(self):
        self.update_leaderboard.cancel()

    @tasks.loop(minutes=1)
    async def update_leaderboard(self):
        if not self.bot.guild_configs:
            return

        for guild_id_str, guild_config in self.bot.guild_configs.items():
            thread_id = guild_config.get('leaderboard_thread_id')
            if not thread_id:
                continue

            try:
                guild_id = int(guild_id_str)
                guild = self.bot.get_guild(guild_id)
                thread = self.bot.get_channel(thread_id)
                
                if not guild or not thread:
                    logging.warning(f"Thread BXH hoac guild {guild_id} khong tim thay.")
                    continue

                top_users = db.get_top_users(guild.id, limit=20)
                
                if top_users is None:
                    logging.error(f"Lay top users tu db that bai cho guild {guild.id}")
                    continue

                embed_color = discord.Color(int(str(guild_config.get('EMBED_COLOR', '#ff00af')).lstrip('#'), 16))
                embed = discord.Embed(
                    title="Bảng Xếp Hạng Đại Gia <:b_34:1343877618340204627>",
                    description="Top 20 thành viên có số dư coin cao nhất server.",
                    color=embed_color,
                    timestamp=discord.utils.utcnow()
                )

                leaderboard_lines = []
                for i, user_data in enumerate(top_users):
                    member = guild.get_member(user_data['user_id'])
                    display_name = member.mention if member else f"User đã rời server"
                    
                    emoji = "🔹"
                    if i == 0: emoji = "🥇"
                    elif i == 1: emoji = "🥈"
                    elif i == 2: emoji = "🥉"
                    
                    balance_formatted = f"{user_data['balance']:,}"
                    line = f"{emoji} **Hạng {i+1}:** {display_name}\n> **Số dư:** `{balance_formatted}` <a:coin:1406137409384480850>"
                    leaderboard_lines.append(line)
                
                embed.description = "\n\n".join(leaderboard_lines) if leaderboard_lines else "Chưa có ai trên bảng xếp hạng."

                if guild.icon:
                    embed.set_thumbnail(url=guild.icon.url)
                
                if guild_config.get('EARNING_RATES_IMAGE_URL'):
                    embed.set_image(url=guild_config.get('EARNING_RATES_IMAGE_URL'))

                embed.set_footer(text="Cập nhật mỗi 1 phút", icon_url=self.bot.user.avatar.url)
                
                message = self.leaderboard_messages.get(thread_id)
                if message:
                    await message.edit(content=None, embed=embed)
                else:
                    found = False
                    async for msg in thread.history(limit=5):
                        if msg.author.id == self.bot.user.id:
                            self.leaderboard_messages[thread_id] = msg
                            await msg.edit(content=None, embed=embed)
                            found = True
                            break
                    if not found:
                        self.leaderboard_messages[thread_id] = await thread.send(embed=embed)

            except discord.NotFound:
                try:
                    self.leaderboard_messages[thread_id] = await thread.send(embed=embed)
                except Exception as e:
                    logging.error(f"Gui tin nhan BXH moi that bai: {e}")
            except Exception as e:
                logging.error(f"Loi cap nhat BXH cho guild {guild_id_str}: {e}")
                self.leaderboard_messages.pop(thread_id, None)

    @update_leaderboard.before_loop
    async def before_update_leaderboard(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(TasksHandler(bot))