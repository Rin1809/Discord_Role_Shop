import discord
from discord import app_commands 
from discord.ext import commands
from database import database as db
from .shop_views import ShopView 
from utils import format_text 

class AdminCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    shop = app_commands.Group(name="shop", description="Các lệnh quản lý shop role")
    coin = app_commands.Group(name="coin", description="Các lệnh quản lý tiền tệ")

    async def get_guild_config(self, guild_id: int):
        # ham helper lay config
        return self.bot.guild_configs.get(str(guild_id))

    @shop.command(name="setup", description="Gửi bảng điều khiển shop và tạo thread bảng xếp hạng.")
    @app_commands.checks.has_permissions(administrator=True) 
    async def setup_shop(self, interaction: discord.Interaction): 
        await interaction.response.defer(ephemeral=True)
        
        guild_id_str = str(interaction.guild.id)
        guild_config = await self.get_guild_config(interaction.guild.id)
        
        if not guild_config:
            return await interaction.followup.send("⚠️ Cấu hình cho server này chưa được thiết lập trong database.", ephemeral=True)

        channel_id = guild_config.get('shop_channel_id')
        if not channel_id:
            return await interaction.followup.send(f"⚠️ Kênh shop cho server này chưa được thiết lập trong database.", ephemeral=True)
        
        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            return await interaction.followup.send(f"⚠️ Không tìm thấy kênh với ID `{channel_id}`.", ephemeral=True)
        
        embed_color = discord.Color(int(guild_config.get('EMBED_COLOR', '0xff00af'), 16))
        messages = guild_config.get('MESSAGES', {})

        embed = discord.Embed(
            title=messages.get('SHOP_EMBED_TITLE', "Shop Role"),
            # Su dung format_text o day
            description=format_text(messages.get('SHOP_EMBED_DESCRIPTION', "Chào mừng")),
            color=embed_color
        )
        
        if guild_config.get('SHOP_EMBED_THUMBNAIL_URL'):
            embed.set_thumbnail(url=guild_config.get('SHOP_EMBED_THUMBNAIL_URL'))

        footer_text = guild_config.get('FOOTER_MESSAGES', {}).get('SHOP_PANEL', 'Bot by Yumemi')
        embed.set_footer(
            text=f"────────────────────\n{footer_text}", 
            icon_url=self.bot.user.avatar.url
        )
        
        if guild_config.get('SHOP_EMBED_IMAGE_URL'):
            embed.set_image(url=guild_config.get('SHOP_EMBED_IMAGE_URL'))
        
        view = ShopView(bot=self.bot)

        try:
            panel_message = await channel.send(embed=embed, view=view)
            
            # tao thread bxh
            old_thread_id = guild_config.get('leaderboard_thread_id')
            
            try:
                # khoa thread cu neu co
                if old_thread_id:
                    old_thread = self.bot.get_channel(int(old_thread_id))
                    if old_thread:
                        await old_thread.edit(archived=True, locked=True)
            except Exception:
                pass 

            leaderboard_thread = await panel_message.create_thread(name="🏆 Bảng Xếp Hạng Coin 🏆")
            await leaderboard_thread.send("Bảng xếp hạng sẽ được cập nhật tại đây...")
            
            # luu id vao db va cache
            db.update_guild_config(interaction.guild.id, leaderboard_thread_id=leaderboard_thread.id)
            self.bot.guild_configs[guild_id_str]['leaderboard_thread_id'] = leaderboard_thread.id
            
            # khoi dong lai task
            task_cog = self.bot.get_cog('TasksHandler')
            if task_cog:
                task_cog.update_leaderboard.restart()

            await interaction.followup.send(f"✅ Đã gửi bảng điều khiển shop tới {channel.mention} và tạo thread BXH.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(f"❌ Tôi không có quyền gửi tin nhắn hoặc tạo thread trong kênh {channel.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Lỗi không xác định: {e}", ephemeral=True)

    @shop.command(name="addrole", description="Thêm một role vào shop.")
    @app_commands.describe(role="Role cần thêm", price="Giá của role") 
    @app_commands.checks.has_permissions(administrator=True)
    async def add_role(self, interaction: discord.Interaction, role: discord.Role, price: int):
        if price < 0:
            return await interaction.response.send_message("⚠️ Giá tiền không thể là số âm.", ephemeral=True)

        db.add_role_to_shop(role.id, interaction.guild.id, price)
        await interaction.response.send_message(f"✅ Đã thêm role {role.mention} vào shop với giá `{price}` coin.", ephemeral=True)
        
    @shop.command(name="removerole", description="Xóa một role khỏi shop.")
    @app_commands.describe(role="Role cần xóa")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_role(self, interaction: discord.Interaction, role: discord.Role):
        db.remove_role_from_shop(role.id, interaction.guild.id)
        await interaction.response.send_message(f"✅ Đã xóa role {role.mention} khỏi shop.", ephemeral=True)

    @coin.command(name="give", description="Tặng coin cho một thành viên.")
    @app_commands.describe(member="Người nhận coin", amount="Số coin muốn tặng")
    @app_commands.checks.has_permissions(administrator=True)
    async def give_coin(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            return await interaction.response.send_message("⚠️ Lượng coin phải là số dương.", ephemeral=True)
        
        user_data = db.get_or_create_user(member.id, interaction.guild.id)
        new_balance = user_data['balance'] + amount
        db.update_user_data(member.id, interaction.guild.id, balance=new_balance)
        await interaction.response.send_message(f"✅ Đã tặng `{amount}` coin cho {member.mention}. Số dư mới: `{new_balance}` coin.", ephemeral=True)

    @coin.command(name="set", description="Thiết lập số coin chính xác cho một thành viên.")
    @app_commands.describe(member="Thành viên cần set coin", amount="Số coin chính xác")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_coin(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount < 0:
            return await interaction.response.send_message("⚠️ Lượng coin không thể là số âm.", ephemeral=True)

        db.update_user_data(member.id, interaction.guild.id, balance=amount)
        await interaction.response.send_message(f"✅ Đã đặt số dư của {member.mention} thành `{amount}` coin.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCommands(bot))