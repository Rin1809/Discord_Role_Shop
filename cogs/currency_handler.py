import discord
from discord.ext import commands, tasks
from database import database as db
import logging
from collections import Counter

class CurrencyHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.leaderboard_messages = {}
        self.update_leaderboard.start()
        self.check_custom_roles.start()
        self.sync_real_boosts.start() 

    def cog_unload(self):
        self.update_leaderboard.cancel()
        self.check_custom_roles.cancel()
        self.sync_real_boosts.cancel()

    def _get_boost_multiplier(self, member: discord.Member, guild_config: dict, user_data: dict) -> float:
        """tinh toan he so nhan coin cho booster."""
        booster_config = guild_config.get('BOOSTER_MULTIPLIER_CONFIG', {})
        
        # kiem tra xem tinh nang co bat khong
        if not booster_config.get('ENABLED', False):
            return 1.0

        # uu tien fake_boosts
        fake_boosts = user_data.get('fake_boosts', 0)
        real_boosts = user_data.get('real_boosts', 0)
        effective_boost_count = fake_boosts if fake_boosts > 0 else real_boosts

        if effective_boost_count <= 0:
            return 1.0

        base_multiplier = booster_config.get('BASE_MULTIPLIER', 1.0)
        per_boost_addition = booster_config.get('PER_BOOST_ADDITION', 0.0)

        # tinh toan he so
        # boost dau tien se nhan base_multiplier
        # moi boost them se cong them per_boost_addition
        final_multiplier = base_multiplier + ((effective_boost_count - 1) * per_boost_addition)
        
        return max(1.0, final_multiplier) # dam bao khong bao gio < 1.0

    @tasks.loop(minutes=5)
    async def sync_real_boosts(self):
        """
        Dong bo so luong boost thuc te cua moi thanh vien vao database.
        Logic duoc toi uu de xu ly va dam bao tinh toan chinh xac.
        """
        logging.info("Bat dau dong bo so luong boost thuc te...")
        for guild_id_str in self.bot.guild_configs.keys():
            try:
                guild_id = int(guild_id_str)
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue

                # FIX START: Dam bao cache thanh vien da day du truoc khi xu ly.
                # Day la buoc quan trong de tranh viec guild.premium_subscribers bi trong/thieu.
                if not guild.chunked:
                    try:
                        logging.info(f"Cache thanh vien cho guild '{guild.name}' chua hoan tat. Dang tai...")
                        await guild.chunk()
                        logging.info(f"Tai cache thanh vien cho guild '{guild.name}' hoan tat.")
                    except Exception as e:
                        logging.error(f"Loi khi tai cache thanh vien cho guild {guild.id}: {e}")
                # FIX END

                # B1: Lay so luong boost hien tai tu Discord API
                current_api_boosts = Counter(member.id for member in guild.premium_subscribers)

                # B2: Lay trang thai boost hien tai tu database
                users_in_db_with_boosts = db.execute_query(
                    "SELECT user_id, real_boosts FROM users WHERE guild_id = %s AND real_boosts > 0",
                    (guild_id,),
                    fetch='all'
                )
                current_db_boosts = {user['user_id']: user['real_boosts'] for user in users_in_db_with_boosts} if users_in_db_with_boosts else {}

                updated_count = 0

                # B3: Cap nhat nguoi dung dang boost
                # (nguoi moi, hoac nguoi co thay doi so luong boost)
                for user_id, api_count in current_api_boosts.items():
                    db.get_or_create_user(user_id, guild_id) # dam bao user ton tai
                    if current_db_boosts.get(user_id) != api_count:
                        db.update_user_data(user_id, guild_id, real_boosts=api_count)
                        updated_count += 1

                # B4: Reset so boost cho nguoi dung da ngung boost
                stopped_boosting_users = set(current_db_boosts.keys()) - set(current_api_boosts.keys())
                for user_id in stopped_boosting_users:
                    db.update_user_data(user_id, guild_id, real_boosts=0)
                    updated_count += 1
                
                if updated_count > 0:
                    logging.info(f"Dong bo boost cho guild {guild.name} thanh cong. Da cap nhat {updated_count} thanh vien.")
                else:
                    logging.info(f"Khong co thay doi boost nao cho guild {guild.name}.")

            except Exception as e:
                logging.error(f"Loi khi dong bo boost that cho guild {guild_id_str}: {e}")

    @sync_real_boosts.before_loop
    async def before_sync_real_boosts(self):
        await self.bot.wait_until_ready()

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
                if not guild or not guild.me.guild_permissions.manage_roles:
                    continue
                
                all_custom_roles = db.get_all_custom_roles_for_guild(guild_id)
                if not all_custom_roles:
                    continue
                
                valid_booster_roles_to_position = []

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
                    
                    # Uu tien so boost that da duoc dong bo
                    real_boosts = user_db_data.get('real_boosts', 0)
                    fake_boosts = user_db_data.get('fake_boosts', 0)
                    
                    effective_boost_count = fake_boosts if fake_boosts > 0 else real_boosts

                    if effective_boost_count < min_boosts:
                        role_to_delete = guild.get_role(role_id)
                        
                        if role_to_delete:
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
                        continue
                    
                    # Neu member van hop le, them role vao danh sach de sap xep
                    role_obj = guild.get_role(role_id)
                    if role_obj:
                        valid_booster_roles_to_position.append(role_obj)

                # Sap xep lai toan bo role booster hop le trong 1 lan
                if not valid_booster_roles_to_position:
                    continue

                try:
                    target_top_position = guild.me.top_role.position - 1
                    
                    # Sap xep cac role theo vi tri hien tai de giu thu tu tuong doi on dinh
                    sorted_roles = sorted(valid_booster_roles_to_position, key=lambda r: r.position, reverse=True)
                    
                    positions_payload = {}
                    has_changes = False
                    for i, role in enumerate(sorted_roles):
                        new_position = target_top_position - i
                        # Dam bao vi tri khong bao gio < 1
                        if new_position < 1: new_position = 1
                        
                        positions_payload[role] = new_position
                        if role.position != new_position:
                            has_changes = True

                    # Chi goi API neu co thay doi can thiet
                    if has_changes:
                        await guild.edit_role_positions(positions=positions_payload, reason="Dinh ky sap xep toan bo role booster")
                        logging.info(f"Da sap xep lai {len(positions_payload)} role booster cho guild {guild.name}")

                except discord.Forbidden:
                    logging.warning(f"Khong co quyen de sap xep hang loat role trong guild {guild.name}")
                except Exception as e:
                    logging.error(f"Loi khi sap xep hang loat role booster trong guild {guild.name}: {e}")


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
                    # Neu khong tim thay tin nhan, tao tin moi
                    thread = self.bot.get_channel(thread_id)
                    if thread:
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
    await bot.add_cog(CurrencyHandler(bot))