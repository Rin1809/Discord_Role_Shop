import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput, Select
from database import database as db

class QnASelect(Select):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config
        self.qna_data = self.config.get("QNA_DATA", [])
        self.embed_color = discord.Color(int(self.config['EMBED_COLOR'], 16))

        options = [
            discord.SelectOption(
                label=item["label"],
                description=item.get("description"),
                emoji=item.get("emoji")
            ) for item in self.qna_data
        ]
        
        super().__init__(placeholder="Chọn một câu hỏi để xem câu trả lời...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        selected_label = self.values[0]
        
        answer_data = next((item for item in self.qna_data if item["label"] == selected_label), None)

        if not answer_data:
            return await interaction.followup.send("⚠️ Lỗi: Không tìm thấy câu trả lời cho câu hỏi này.", ephemeral=True)
        
        guild = self.bot.get_guild(self.config['GUILD_ID'])
        if not guild:
            return await interaction.followup.send("⚠️ Lỗi nghiêm trọng: Không thể tìm thấy server được cấu hình.", ephemeral=True)
            
        embed = discord.Embed(
            title=f"{answer_data.get('emoji', '❓')} {answer_data.get('answer_title', selected_label)}",
            description=answer_data.get("answer_description", "Chưa có câu trả lời."),
            color=self.embed_color
        )
        embed.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)

        await interaction.followup.send(embed=embed, ephemeral=True)

class QnAView(View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=180) 
        self.add_item(QnASelect(bot))

class EarningRatesView(View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.config = bot.config
        self.messages = self.config['MESSAGES']
        self.embed_color = discord.Color(int(self.config['EMBED_COLOR'], 16))

    @discord.ui.button(label="?", style=discord.ButtonStyle.secondary)
    async def bot_info_callback(self, interaction: discord.Interaction, button: Button):
        qna_view = QnAView(bot=self.bot)
        await interaction.response.send_message(
            content="<:g_chamhoi:1326543673957027961> **Các câu hỏi thường gặp**\nVui lòng chọn một câu hỏi từ menu bên dưới:", 
            view=qna_view, 
            ephemeral=True
        )

    @discord.ui.button(label="Cách Đào Coin", style=discord.ButtonStyle.secondary, emoji="💰")
    async def show_rates_callback(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        guild = self.bot.get_guild(self.config['GUILD_ID'])
        if not guild:
            return await interaction.followup.send("Lỗi: Không tìm thấy server.", ephemeral=True)
            
        embed = discord.Embed(
            title=self.messages['EARNING_RATES_TITLE'],
            description=self.messages['EARNING_RATES_DESC'],
            color=self.embed_color
        )
        
        if guild.icon:
            embed.set_author(name=guild.name, icon_url=guild.icon.url)
            embed.set_thumbnail(url=guild.icon.url)
        else:
            embed.set_author(name=guild.name)

        if self.config.get('EARNING_RATES_IMAGE_URL'):
            embed.set_image(url=self.config.get('EARNING_RATES_IMAGE_URL'))

        special_rates_list = []
        categories_config = self.config['CURRENCY_RATES'].get('categories', {})
        if categories_config:
            for cat_id, rates in categories_config.items():
                category = guild.get_channel(int(cat_id))
                if category:
                    special_rates_list.append(f"**<:g_chamhoi:1326543673957027961> Danh mục: {category.name}**")
                    msg_rate = rates.get('MESSAGES_PER_COIN')
                    react_rate = rates.get('REACTIONS_PER_COIN')
                    if msg_rate:
                        special_rates_list.append(f"> <a:timchat:1406136711741706301> `{msg_rate}` tin nhắn = `1` <a:coin:1406137409384480850>")
                    if react_rate:
                        special_rates_list.append(f"> <:reaction:1406136638421336104> `{react_rate}` reactions = `1` <a:coin:1406137409384480850>")
                    special_rates_list.append("") 

        channels_config = self.config['CURRENCY_RATES'].get('channels', {})
        if channels_config:
            for chan_id, rates in channels_config.items():
                channel = guild.get_channel(int(chan_id))
                if channel:
                    special_rates_list.append(f"**<:channel:1406136670709092422> Kênh: {channel.mention}**")
                    msg_rate = rates.get('MESSAGES_PER_COIN')
                    react_rate = rates.get('REACTIONS_PER_COIN')
                    if msg_rate:
                        special_rates_list.append(f"> <a:timchat:1406136711741706301> `{msg_rate}` tin nhắn = `1` <a:coin:1406137409384480850>")
                    if react_rate:
                        special_rates_list.append(f"> <:reaction:1406136638421336104> `{react_rate}` reactions = `1` <a:coin:1406137409384480850>")
                    special_rates_list.append("") 
        
        if special_rates_list:
            if special_rates_list[-1] == "":
                special_rates_list.pop()
            special_rates_desc = "\n".join(special_rates_list)
            embed.description += "\n\n" + special_rates_desc
        
        footer_text = self.config['FOOTER_MESSAGES']['EARNING_RATES']
        embed.set_footer(
            text=f"────────────────────\n{footer_text}",
            icon_url=self.bot.user.avatar.url
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)


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
        def __init__(self, bot: commands.Bot):
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
    
    class ShopActionSelect(Select):
        def __init__(self, bot: commands.Bot):
            self.bot = bot
            self.config = bot.config
            self.messages = self.config['MESSAGES']
            self.embed_color = discord.Color(int(self.config['EMBED_COLOR'], 16))

            options = [
                discord.SelectOption(label="Danh Sách Role", value="list_roles", description="Xem tất cả các role đang được bán.", emoji="<:MenheraFlower:1406458230317645906>"),
                discord.SelectOption(label="Mua Role", value="purchase", description="Sở hữu ngay role bạn yêu thích.", emoji="<:MenheraFlowers:1406458246528635031>"),
                discord.SelectOption(label="Bán Role", value="sell", description="Bán lại role đã mua để nhận lại coin.", emoji="<a:MenheraNod:1406458257349935244>")
            ]
            super().__init__(custom_id="shop_view:action_select", placeholder="Chọn một hành động giao dịch...", min_values=1, max_values=1, options=options)
        
        async def callback(self, interaction: discord.Interaction):
            action = self.values[0]

            if action == "list_roles":
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
                
                footer_text = self.config['FOOTER_MESSAGES']['ROLE_LIST']
                embed.set_footer(
                    text=f"────────────────────\n{footer_text}",
                    icon_url=self.bot.user.avatar.url
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

            elif action == "purchase":
                modal = ShopInterface.PurchaseModal(bot=self.bot)
                await interaction.response.send_modal(modal)

            elif action == "sell":
                modal = ShopInterface.SellModal(bot=self.bot)
                await interaction.response.send_modal(modal)

    class ShopView(View):
        def __init__(self, bot: commands.Bot): 
            super().__init__(timeout=None)
            self.bot = bot
            self.config = bot.config
            self.messages = self.config['MESSAGES']
            self.embed_color = discord.Color(int(self.config['EMBED_COLOR'], 16))
            
            self.add_item(ShopInterface.ShopActionSelect(bot=self.bot))

        @discord.ui.button(label="Tài Khoản Của Tôi", style=discord.ButtonStyle.secondary, custom_id="shop_view:account", emoji="<a:z_cat_yolo:1326542766330740818>")
        async def account_button_callback(self, interaction: discord.Interaction, button: Button):
            await interaction.response.defer(ephemeral=True)
            
            user_data = db.get_or_create_user(interaction.user.id, interaction.guild.id)

            embed = discord.Embed(
                title=self.messages['ACCOUNT_INFO_TITLE'],
                description=self.messages['ACCOUNT_INFO_DESC'],
                color=self.embed_color
            )
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            
            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)

            balance_str = self.messages['BALANCE_FIELD_VALUE'].format(balance=user_data['balance'])
            embed.add_field(name=f"```{self.messages['BALANCE_FIELD_NAME']}```", value=balance_str, inline=False)
            if self.config.get('SHOP_EMBED_IMAGE_URL'):
                embed.set_image(url=self.config['SHOP_EMBED_IMAGE_URL'])

            footer_text = self.config['FOOTER_MESSAGES']['ACCOUNT_INFO']
            embed.set_footer(
                text=f"────────────────────\n{footer_text}",
                icon_url=self.bot.user.avatar.url
            )
            
            view = EarningRatesView(bot=self.bot)
            
            try:
                await interaction.user.send(embed=embed, view=view)
                await interaction.followup.send("✅ Đã gửi thông tin tài khoản vào tin nhắn riêng của bạn!", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send("⚠️ Tôi không thể gửi tin nhắn riêng cho bạn. Vui lòng bật tin nhắn từ thành viên server.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ShopInterface(bot))