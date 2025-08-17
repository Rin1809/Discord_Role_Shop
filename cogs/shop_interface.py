import discord
from discord import app_commands
from discord.ext import commands
from database import database as db
from .shop_modals import CustomRoleModal 

class ShopInterface(commands.Cog):
    def __init__(self, bot: commands.Bot): 
        self.bot = bot
        self.config = bot.config
        self.embed_color = discord.Color(int(self.config['EMBED_COLOR'], 16))

    myrole = app_commands.Group(name="myrole", description="Quản lý role tùy chỉnh của bạn")

    @myrole.command(name="edit", description="Chỉnh sửa tên và màu cho role tùy chỉnh của bạn.")
    async def edit_my_role(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        custom_role_data = db.get_custom_role(interaction.user.id, interaction.guild.id)
        if not custom_role_data:
            return await interaction.followup.send("⚠️ Bạn chưa sở hữu role tùy chỉnh nào để chỉnh sửa.", ephemeral=True)

        role_id = custom_role_data['role_id']
        role_obj = interaction.guild.get_role(role_id)
        if not role_obj:
            db.delete_custom_role_data(interaction.user.id, interaction.guild.id) # Xoa db neu role ko ton tai
            return await interaction.followup.send("⚠️ Role tùy chỉnh của bạn không còn tồn tại trên server. Dữ liệu đã được xóa.", ephemeral=True)
        
        # Tao modal voi du lieu co san
        modal = CustomRoleModal(bot=self.bot, role_to_edit=role_obj)
        await interaction.followup.send("Vui lòng nhập thông tin mới cho role của bạn:", view=None) # Xoa view cu neu co
        await interaction.response.send_modal(modal) # Gui modal moi
        # Su dung interaction.followup.send() sau khi defer, sau do send_modal() tren interaction chinh
        # la cach tiep can khac, nhung send_modal truc tiep sau defer thuong ko duoc
        # Vi vay, cach tot nhat la send_modal truc tiep
        # await interaction.response.send_modal(modal) # Gui thang modal, khong can followup

    @myrole.command(name="delete", description="Xóa vĩnh viễn role tùy chỉnh của bạn.")
    async def delete_my_role(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        custom_role_data = db.get_custom_role(interaction.user.id, interaction.guild.id)
        if not custom_role_data:
            return await interaction.followup.send("⚠️ Bạn không có role tùy chỉnh nào để xóa.", ephemeral=True)
        
        role_id = custom_role_data['role_id']
        role_obj = interaction.guild.get_role(role_id)

        try:
            if role_obj:
                await role_obj.delete(reason=f"Người dùng {interaction.user} tự xóa")
            db.delete_custom_role_data(interaction.user.id, interaction.guild.id)
            await interaction.followup.send("✅ Đã xóa thành công role tùy chỉnh của bạn.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Tôi không có quyền để xóa role này. Vui lòng liên hệ Admin.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Đã xảy ra lỗi không xác định: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ShopInterface(bot))