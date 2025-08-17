import discord
from discord.ui import Modal, TextInput
from database import database as db
import re

# ham check hex
def is_valid_hex_color(s):
    return re.match(r'^#?([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$', s) is not None

class PurchaseModal(Modal, title="Mua Role"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = bot.config 
        self.embed_color = discord.Color(int(self.config['EMBED_COLOR'], 16))
        self.add_item(TextInput(
            label="Số thứ tự của role", 
            placeholder="Nhập số tương ứng với role bạn muốn mua...",
            custom_id="purchase_role_id_input"
        ))

    async def on_submit(self, interaction: discord.Interaction): 
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            role_number_input = int(self.children[0].value)
            if role_number_input <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return await interaction.followup.send("<a:c_947079524435247135:1274398161200484446> Vui lòng nhập một số thứ tự hợp lệ.", ephemeral=True)

        shop_roles = db.get_shop_roles(interaction.guild.id)
        if not shop_roles or role_number_input > len(shop_roles):
            return await interaction.followup.send("<a:c_947079524435247135:1274398161200484446> Số thứ tự này không tồn tại trong shop.", ephemeral=True)
        
        selected_role_data = shop_roles[role_number_input - 1]
        role_id = selected_role_data['role_id']
        price = selected_role_data['price']
        
        role_obj = interaction.guild.get_role(role_id)
        if not role_obj:
            return await interaction.followup.send("<a:c_947079524435247135:1274398161200484446> Role này không còn tồn tại trên server. Vui lòng liên hệ Admin.", ephemeral=True)

        user_data = db.get_or_create_user(interaction.user.id, interaction.guild.id)
        
        if role_obj in interaction.user.roles:
            return await interaction.followup.send(f"Bạn đã sở hữu role {role_obj.mention} rồi!", ephemeral=True)

        if user_data['balance'] < price:
            return await interaction.followup.send(f"Bạn không đủ coin! Cần **{price} coin** nhưng bạn chỉ có **{user_data['balance']}**.", ephemeral=True)
            
        new_balance = user_data['balance'] - price
        
        try:
            await interaction.user.add_roles(role_obj, reason="Mua từ shop")
            db.update_user_data(interaction.user.id, interaction.guild.id, balance=new_balance)
        except discord.Forbidden:
            return await interaction.followup.send("❌ Đã xảy ra lỗi! Tôi không có quyền để gán role này cho bạn. Giao dịch đã bị hủy.", ephemeral=True)
        
        receipt_embed = discord.Embed(
            title="Biên Lai Giao Dịch Mua Hàng",
            description="Giao dịch của bạn đã được xử lý thành công.",
            color=self.embed_color,
            timestamp=discord.utils.utcnow()
        )
        receipt_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        if interaction.guild.icon:
            receipt_embed.set_thumbnail(url=interaction.guild.icon.url)
        
        receipt_embed.add_field(name="Loại Giao Dịch", value="```Mua Role```", inline=False)
        receipt_embed.add_field(name="Sản Phẩm", value=f"```{role_obj.name}```", inline=True)
        receipt_embed.add_field(name="Chi Phí", value=f"```- {price} coin```", inline=True)
        receipt_embed.add_field(name="Số Dư Mới", value=f"```{new_balance} coin```", inline=True)
        
        if self.config.get('SHOP_EMBED_IMAGE_URL'):
            receipt_embed.set_image(url=self.config.get('SHOP_EMBED_IMAGE_URL'))

        receipt_embed.set_footer(text=f"Cảm ơn bạn đã giao dịch tại {interaction.guild.name}", icon_url=self.bot.user.avatar.url)

        try:
            await interaction.user.send(embed=receipt_embed)
            await interaction.followup.send("✅ Giao dịch thành công! Vui lòng kiểm tra tin nhắn riêng để xem biên lai.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(
                "<a:c_947079524435247135:1274398161200484446> Tôi không thể gửi biên lai vào tin nhắn riêng của bạn. Giao dịch vẫn thành công. Đây là biên lai của bạn:", 
                embed=receipt_embed, 
                ephemeral=True
            )

class SellModal(Modal, title="Bán Lại Role"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = bot.config
        self.embed_color = discord.Color(int(self.config['EMBED_COLOR'], 16))
        self.add_item(TextInput(
            label="Số thứ tự của role muốn bán", 
            placeholder="Nhập số tương ứng với role bạn muốn bán...",
            custom_id="sell_role_id_input"
        ))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            role_number_input = int(self.children[0].value)
            if role_number_input <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return await interaction.followup.send("<a:c_947079524435247135:1274398161200484446> Vui lòng nhập một số thứ tự hợp lệ.", ephemeral=True)

        shop_roles = db.get_shop_roles(interaction.guild.id)
        if not shop_roles or role_number_input > len(shop_roles):
            return await interaction.followup.send("<a:c_947079524435247135:1274398161200484446> Số thứ tự này không tồn tại trong shop.", ephemeral=True)

        selected_role_data = shop_roles[role_number_input - 1]
        role_id = selected_role_data['role_id']
        price = selected_role_data['price']

        role_obj = interaction.guild.get_role(role_id)
        if not role_obj:
            return await interaction.followup.send("<a:c_947079524435247135:1274398161200484446> Role này không còn tồn tại trên server. Vui lòng liên hệ Admin.", ephemeral=True)

        if role_obj not in interaction.user.roles:
            return await interaction.followup.send(f"Bạn không sở hữu role {role_obj.mention} để bán.", ephemeral=True)
        
        user_data = db.get_or_create_user(interaction.user.id, interaction.guild.id)
        
        refund_percentage = self.config.get('SELL_REFUND_PERCENTAGE', 0.65)
        refund_amount = int(price * refund_percentage)
        new_balance = user_data['balance'] + refund_amount

        try:
            await interaction.user.remove_roles(role_obj, reason="Bán lại cho shop")
            db.update_user_data(interaction.user.id, interaction.guild.id, balance=new_balance)
        except discord.Forbidden:
            return await interaction.followup.send("❌ Đã xảy ra lỗi! Tôi không có quyền để xóa role này khỏi bạn. Giao dịch đã bị hủy.", ephemeral=True)

        receipt_embed = discord.Embed(
            title="Biên Lai Giao Dịch Bán Hàng",
            description="Giao dịch của bạn đã được xử lý thành công.",
            color=self.embed_color,
            timestamp=discord.utils.utcnow()
        )
        receipt_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        if interaction.guild.icon:
            receipt_embed.set_thumbnail(url=interaction.guild.icon.url)
        
        receipt_embed.add_field(name="Loại Giao Dịch", value="```Bán Role```", inline=False)
        receipt_embed.add_field(name="Sản Phẩm", value=f"```{role_obj.name}```", inline=True)
        receipt_embed.add_field(name="Tiền Nhận Lại", value=f"```+ {refund_amount} coin```", inline=True)
        receipt_embed.add_field(name="Số Dư Mới", value=f"```{new_balance} coin```", inline=True)
        
        if self.config.get('SHOP_EMBED_IMAGE_URL'):
            receipt_embed.set_image(url=self.config.get('SHOP_EMBED_IMAGE_URL'))

        receipt_embed.set_footer(text=f"Cảm ơn bạn đã giao dịch tại {interaction.guild.name}", icon_url=self.bot.user.avatar.url)

        try:
            await interaction.user.send(embed=receipt_embed)
            await interaction.followup.send("✅ Giao dịch thành công! Vui lòng kiểm tra tin nhắn riêng để xem biên lai.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(
                "<a:c_947079524435247135:1274398161200484446> Tôi không thể gửi biên lai vào tin nhắn riêng của bạn. Giao dịch vẫn thành công. Đây là biên lai của bạn:", 
                embed=receipt_embed, 
                ephemeral=True
            )

class CustomRoleModal(Modal):
    def __init__(self, bot, price=None, role_to_edit: discord.Role = None):
        super().__init__(title="Tạo Hoặc Sửa Role Tùy Chỉnh")
        self.bot = bot
        self.config = bot.config
        self.price = price
        self.role_to_edit = role_to_edit
        self.embed_color = discord.Color(int(self.config['EMBED_COLOR'], 16))

        self.add_item(TextInput(
            label="Tên role bạn muốn",
            placeholder="Ví dụ: Đại Gia Server",
            custom_id="custom_role_name",
            default=role_to_edit.name if role_to_edit else None
        ))
        self.add_item(TextInput(
            label="Mã màu HEX (ví dụ: #ff00af)",
            placeholder="Nhập mã màu bắt đầu bằng #",
            custom_id="custom_role_color",
            default=str(role_to_edit.color) if role_to_edit else "#ff00af"
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        role_name = self.children[0].value
        role_color_str = self.children[1].value

        if not is_valid_hex_color(role_color_str):
            return await interaction.followup.send("<a:c_947079524435247135:1274398161200484446> Mã màu HEX không hợp lệ. Vui lòng thử lại (ví dụ: `#ff00af`).", ephemeral=True)
        
        color_int = int(role_color_str.lstrip('#'), 16)
        new_color = discord.Color(color_int)
        
        guild_id = self.config['GUILD_ID']
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return await interaction.followup.send("Lỗi nghiêm trọng: Không tìm thấy server.", ephemeral=True)

        user_data = db.get_or_create_user(interaction.user.id, guild_id)

        # xu ly sua role
        if self.role_to_edit:
            try:
                await self.role_to_edit.edit(name=role_name, color=new_color, reason=f"Người dùng {interaction.user} tự sửa")
                db.add_or_update_custom_role(interaction.user.id, guild_id, self.role_to_edit.id, role_name, role_color_str)
                
                # fix loi @unknown-role khi gui dm
                success_msg = f"✅ Đã cập nhật thành công role **{role_name}** của bạn."
                try:
                    await interaction.user.send(success_msg)
                    await interaction.followup.send("✅ Đã xử lý! Vui lòng kiểm tra tin nhắn riêng.", ephemeral=True)
                except discord.Forbidden:
                    await interaction.followup.send(success_msg, ephemeral=True)

            except discord.Forbidden:
                await interaction.followup.send("❌ Tôi không có quyền để chỉnh sửa role này.", ephemeral=True)
            return

        # xu ly tao role moi
        if user_data['balance'] < self.price:
            return await interaction.followup.send(f"Bạn không đủ coin! Cần **{self.price} coin** nhưng bạn chỉ có **{user_data['balance']}**.", ephemeral=True)
        
        new_balance = user_data['balance'] - self.price

        try:
            member = guild.get_member(interaction.user.id)
            if not member:
                 return await interaction.followup.send("Lỗi: Không tìm thấy bạn trên server.", ephemeral=True)

            new_role = await guild.create_role(
                name=role_name, color=new_color, reason=f"Role tùy chỉnh của {interaction.user.name}"
            )
            await member.add_roles(new_role)
            
            db.update_user_data(interaction.user.id, guild_id, balance=new_balance)
            db.add_or_update_custom_role(interaction.user.id, guild_id, new_role.id, role_name, role_color_str)
            
            # tao bien lai
            receipt_embed = discord.Embed(
                title="Biên Lai Tạo Role Tùy Chỉnh",
                description="Role tùy chỉnh của bạn đã được tạo và gán thành công.",
                color=self.embed_color,
                timestamp=discord.utils.utcnow()
            )
            receipt_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            if interaction.guild.icon:
                receipt_embed.set_thumbnail(url=interaction.guild.icon.url)
            
            receipt_embed.add_field(name="Loại Giao Dịch", value="```Tạo Role Tùy Chỉnh```", inline=False)
            receipt_embed.add_field(name="Tên Role", value=f"```{role_name}```", inline=True)
            receipt_embed.add_field(name="Màu Sắc", value=f"```{role_color_str}```", inline=True)
            receipt_embed.add_field(name="Chi Phí", value=f"```- {self.price} coin```", inline=False)
            receipt_embed.add_field(name="Số Dư Mới", value=f"```{new_balance} coin```", inline=True)
            
            if self.config.get('SHOP_EMBED_IMAGE_URL'):
                receipt_embed.set_image(url=self.config.get('SHOP_EMBED_IMAGE_URL'))

            receipt_embed.set_footer(text=f"Cảm ơn bạn đã giao dịch tại {interaction.guild.name}", icon_url=self.bot.user.avatar.url)

            try:
                await interaction.user.send(embed=receipt_embed)
                await interaction.followup.send("✅ Giao dịch thành công! Vui lòng kiểm tra tin nhắn riêng để xem biên lai.", ephemeral=True)
            except discord.Forbidden:
                 await interaction.followup.send(
                    "<a:c_947079524435247135:1274398161200484446> Tôi không thể gửi biên lai vào DM. Giao dịch vẫn thành công. Đây là biên lai của bạn:", 
                    embed=receipt_embed, 
                    ephemeral=True
                )

        except discord.Forbidden:
            await interaction.followup.send("❌ Đã xảy ra lỗi! Tôi không có quyền tạo hoặc gán role. Giao dịch đã bị hủy.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Đã xảy ra lỗi không mong muốn: {e}", ephemeral=True)

async def setup(bot):
    pass