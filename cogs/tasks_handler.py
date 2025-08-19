import discord
from discord.ext import commands, tasks
from database import database as db
import logging

class TasksHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.leaderboard_messages = {}
        self.update_leaderboard.start()
        self.check_custom_roles.start()

    def cog_unload(self):
        self.update_leaderboard.cancel()
        self.check_custom_roles.cancel()

    @tasks.loop(minutes=5)
    async def check_custom_roles(self):
        for guild_id_str, guild_config in self.bot.guild_configs.items():
            try:
                guild_id = int(guild_id_str)
                custom_role_config = guild_config.get('CUSTOM_ROLE_CONFIG', {})
                min_boosts = custom_role_config.get('MIN_BOOST_COUNT')

                if not min_boosts:
                    continue

                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue
                
                all_custom_roles = db.get_all_custom_roles_for_guild(guild_id)
                if not all_custom_roles:
                    continue

                for custom_role_data in all_custom_roles:
                    user_id = custom_role_data['user_id']
                    role_id = custom_role_data['role_id']
                    
                    member = guild.get_member(user_id)
                    
                    # TH: nguoi dung roi server
                    if not member:
                        role_to_delete = guild.get_role(role_id)
                        if role_to_delete:
                            await role_to_delete.delete(reason="Thanh vien roi server")
                        db.delete_custom_role_data(user_id, guild_id)
                        logging.info(f"Da xoa role tuy chinh cua user {user_id} (roi server) khoi guild {guild_id}")
                        continue
                    
                    # TH: con o server, check dieu kien
                    user_db_data = db.get_or_create_user(user_id, guild_id)
                    
                    effective_boost_count = user_db_data.get('fake_boosts', 0)
                    if effective_boost_count == 0 and member.premium_since:
                        effective_boost_count = sum(1 for m in guild.premium_subscribers if m.id == member.id)

                    if effective_boost_count < min_boosts:
                        role_to_delete = guild.get_role(role_id)
                        
                        if role_to_delete:
                            # gui dm truoc khi xoa
                            try:
                                dm_message = (
                                    f"Chào bạn, role tùy chỉnh **{role_to_delete.name}** của bạn tại server **{guild.name}** "
                                    f"đã được tự động gỡ bỏ vì bạn không còn đáp ứng đủ điều kiện boost server nữa.\n\n"
                                    f"Cảm ơn bạn đã từng ủng hộ server!"
                                )
                                await member.send(dm_message)
                            except discord.Forbidden:
                                logging.warning(f"Khong the DM cho {member.name} ({member.id}) ve viec xoa role.")
                            except Exception as e:
                                logging.error(f"Loi DM cho {member.name} khi xoa role: {e}")
                            
                            await role_to_delete.delete(reason="Khong con du dieu kien boost")
                        
                        db.delete_custom_role_data(user_id, guild_id)
                        logging.info(f"Da xoa role tuy chinh cua {member.name} (khong du boost) khoi guild {guild_id}")

            except Exception as e:
                logging.error(f"Loi khi check custom role cho guild {guild_id_str}: {e}")

    @check_custom_roles.before_loop
    async def before_check_custom_roles(self):
        await self.bot.wait_until_ready()

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