import discord
from discord.ui import Modal, TextInput
from database import database as db

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
            return await interaction.followup.send("⚠️ Vui lòng nhập một số thứ tự hợp lệ.", ephemeral=True)

        shop_roles = db.get_shop_roles(interaction.guild.id)
        if not shop_roles or role_number_input > len(shop_roles):
            return await interaction.followup.send("⚠️ Số thứ tự này không tồn tại trong shop.", ephemeral=True)
        
        selected_role_data = shop_roles[role_number_input - 1]
        role_id = selected_role_data['role_id']
        price = selected_role_data['price']
        
        role_obj = interaction.guild.get_role(role_id)
        if not role_obj:
            return await interaction.followup.send("⚠️ Role này không còn tồn tại trên server. Vui lòng liên hệ Admin.", ephemeral=True)

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
                "⚠️ Tôi không thể gửi biên lai vào tin nhắn riêng của bạn. Giao dịch vẫn thành công. Đây là biên lai của bạn:", 
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
            return await interaction.followup.send("⚠️ Vui lòng nhập một số thứ tự hợp lệ.", ephemeral=True)

        shop_roles = db.get_shop_roles(interaction.guild.id)
        if not shop_roles or role_number_input > len(shop_roles):
            return await interaction.followup.send("⚠️ Số thứ tự này không tồn tại trong shop.", ephemeral=True)

        selected_role_data = shop_roles[role_number_input - 1]
        role_id = selected_role_data['role_id']
        price = selected_role_data['price']

        role_obj = interaction.guild.get_role(role_id)
        if not role_obj:
            return await interaction.followup.send("⚠️ Role này không còn tồn tại trên server. Vui lòng liên hệ Admin.", ephemeral=True)

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
                "⚠️ Tôi không thể gửi biên lai vào tin nhắn riêng của bạn. Giao dịch vẫn thành công. Đây là biên lai của bạn:", 
                embed=receipt_embed, 
                ephemeral=True
            )

# Fix loi load
async def setup(bot):
    pass