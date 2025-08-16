import discord
from discord import app_commands 
from discord.ext import commands
from database import database as db

class AdminCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config
        self.embed_color = discord.Color(int(self.config['EMBED_COLOR'], 16))

    shop = app_commands.Group(name="shop", description="Các lệnh quản lý shop role")
    coin = app_commands.Group(name="coin", description="Các lệnh quản lý tiền tệ")

    @shop.command(name="setup", description="Gửi bảng điều khiển shop vào kênh đã định.")
    @app_commands.checks.has_permissions(administrator=True) 
    async def setup_shop(self, interaction: discord.Interaction): 
        channel_id = self.config.get('SHOP_CHANNEL_ID')
        if not channel_id:
            return await interaction.response.send_message("⚠️ `SHOP_CHANNEL_ID` chưa được thiết lập.", ephemeral=True)
        
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return await interaction.response.send_message(f"⚠️ Không tìm thấy kênh với ID `{channel_id}`.", ephemeral=True)
        
        embed = discord.Embed(
            title=self.config['MESSAGES']['SHOP_EMBED_TITLE'],
            description=self.config['MESSAGES']['SHOP_EMBED_DESCRIPTION'],
            color=self.embed_color
        )
        
        # them thumbnail neu co
        if self.config.get('SHOP_EMBED_THUMBNAIL_URL'):
            embed.set_thumbnail(url=self.config.get('SHOP_EMBED_THUMBNAIL_URL'))

        footer_text = self.config['FOOTER_MESSAGES']['SHOP_PANEL']
        embed.set_footer(
            text=f"────────────────────\n{footer_text}", 
            icon_url=self.bot.user.avatar.url
        )
        
        if self.config.get('SHOP_EMBED_IMAGE_URL'):
            embed.set_image(url=self.config.get('SHOP_EMBED_IMAGE_URL'))

        shop_cog = self.bot.get_cog("ShopInterface")
        if not shop_cog:
            return await interaction.response.send_message("Lỗi: Cog 'ShopInterface' chưa được tải.", ephemeral=True)
        
        view = shop_cog.ShopView(bot=self.bot)

        try:
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Đã gửi bảng điều khiển shop tới {channel.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"❌ Tôi không có quyền gửi tin nhắn vào kênh {channel.mention}.", ephemeral=True)

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