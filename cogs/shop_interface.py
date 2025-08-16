import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput 
from database import database as db

class ShopInterface(commands.Cog):
    def __init__(self, bot: commands.Bot): 
        self.bot = bot
        self.config = bot.config
        self.messages = self.config['MESSAGES']
        self.embed_color = discord.Color(int(self.config['EMBED_COLOR'], 16))

    class PurchaseModal(Modal, title="Mua Role"):
        def __init__(self, bot: commands.Bot):
            super().__init__()
            self.bot = bot
            self.add_item(TextInput(label="Số thứ tự của role", placeholder="Nhập số tương ứng với role bạn muốn mua..."))

        async def on_submit(self, interaction: discord.Interaction): 
            try:
                role_number_input = int(self.children[0].value)
                if role_number_input <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                return await interaction.response.send_message("⚠️ Vui lòng nhập một số thứ tự hợp lệ.", ephemeral=True)

            shop_roles = db.get_shop_roles(interaction.guild.id)
            if not shop_roles or role_number_input > len(shop_roles):
                return await interaction.response.send_message("⚠️ Số thứ tự này không tồn tại trong shop.", ephemeral=True)
            
            selected_role_data = shop_roles[role_number_input - 1]
            role_id = selected_role_data['role_id']
            price = selected_role_data['price']
            
            role_obj = interaction.guild.get_role(role_id)
            if not role_obj:
                return await interaction.response.send_message("⚠️ Role này không còn tồn tại trên server. Vui lòng liên hệ Admin.", ephemeral=True)

            user_data = db.get_or_create_user(interaction.user.id, interaction.guild.id)
            
            if role_obj in interaction.user.roles:
                return await interaction.response.send_message(f"Bạn đã sở hữu role {role_obj.mention} rồi!", ephemeral=True)

            if user_data['balance'] < price:
                return await interaction.response.send_message(f"Bạn không đủ coin! Cần **{price} coin** nhưng bạn chỉ có **{user_data['balance']}**.", ephemeral=True)
                
            new_balance = user_data['balance'] - price
            db.update_user_data(interaction.user.id, interaction.guild.id, balance=new_balance)
            
            try:
                await interaction.user.add_roles(role_obj, reason="Mua từ shop")
                await interaction.response.send_message(f"🎉 Chúc mừng! Bạn đã mua thành công role {role_obj.mention} với giá **{price} coin**.", ephemeral=True)
            except discord.Forbidden:
                db.update_user_data(interaction.user.id, interaction.guild.id, balance=user_data['balance'])
                await interaction.response.send_message("❌ Đã xảy ra lỗi! Tôi không có quyền để gán role này cho bạn. Giao dịch đã được hoàn lại.", ephemeral=True)


    class ShopView(View):
        def __init__(self, bot: commands.Bot): 
            super().__init__(timeout=None)
            self.bot = bot
            self.config = bot.config
            self.messages = self.config['MESSAGES']
            self.embed_color = discord.Color(int(self.config['EMBED_COLOR'], 16))
        
        # thay doi mau nut sang do
        @discord.ui.button(label="Tài Khoản", style=discord.ButtonStyle.danger, custom_id="shop_view:account")
        async def account_button_callback(self, interaction: discord.Interaction, button: Button):
            await interaction.response.defer(ephemeral=True)
            
            user_data = db.get_or_create_user(interaction.user.id, interaction.guild.id)
            embed = discord.Embed(
                title=self.messages['ACCOUNT_INFO_TITLE'],
                description=self.messages['ACCOUNT_INFO_DESC'],
                color=self.embed_color
            )
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            balance_str = self.messages['BALANCE_FIELD_VALUE'].format(balance=user_data['balance'])
            embed.add_field(name=f"```{self.messages['BALANCE_FIELD_NAME']}```", value=balance_str, inline=False)
            
            how_to_earn_desc = self.messages['HOW_TO_EARN_COIN_DESC'].format(
                messages_per_coin=self.config['CURRENCY_RATES']['MESSAGES_PER_COIN'],
                reactions_per_coin=self.config['CURRENCY_RATES']['REACTIONS_PER_COIN']
            )
            embed.add_field(name=f"```{self.messages['HOW_TO_EARN_COIN_TITLE']}```", value=how_to_earn_desc, inline=False)
            
            if self.config.get('SHOP_EMBED_IMAGE_URL'):
                embed.set_image(url=self.config['SHOP_EMBED_IMAGE_URL'])
            
            try:
                await interaction.user.send(embed=embed)
                await interaction.followup.send("✅ Đã gửi thông tin tài khoản vào tin nhắn riêng của bạn!", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send("⚠️ Tôi không thể gửi tin nhắn riêng cho bạn. Vui lòng bật tin nhắn từ thành viên server.", ephemeral=True)

        @discord.ui.button(label="Danh Sách Role", style=discord.ButtonStyle.secondary, custom_id="shop_view:list_roles")
        async def list_roles_button_callback(self, interaction: discord.Interaction, button: Button):
            await interaction.response.defer(ephemeral=True)
            
            shop_roles = db.get_shop_roles(interaction.guild.id)
            embed = discord.Embed(
                title=self.messages['SHOP_ROLES_TITLE'],
                color=self.embed_color
            )
            
            if not shop_roles:
                embed.description = self.messages['SHOP_ROLES_EMPTY']
            else:
                role_list_str = ""
                for i, role_data in enumerate(shop_roles):
                    role = interaction.guild.get_role(role_data['role_id'])
                    if role:
                        role_list_str += f"### {i+1}. {role.mention}\n> **Giá:** `{role_data['price']}` 🪙\n"
                embed.description = self.messages['SHOP_ROLES_DESC'] + "\n\n" + role_list_str
            
            await interaction.followup.send(embed=embed, ephemeral=True)

        @discord.ui.button(label="Mua Role", style=discord.ButtonStyle.secondary, custom_id="shop_view:purchase")
        async def purchase_button_callback(self, interaction: discord.Interaction, button: Button):
            modal = ShopInterface.PurchaseModal(bot=self.bot)
            await interaction.response.send_modal(modal)

async def setup(bot: commands.Bot):
    await bot.add_cog(ShopInterface(bot))