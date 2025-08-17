import discord
from discord.ui import Button, View, Select
from database import database as db
from .shop_modals import PurchaseModal, SellModal

class QnASelect(Select):
    def __init__(self, bot):
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
    def __init__(self, bot):
        super().__init__(timeout=180) 
        self.add_item(QnASelect(bot))

class EarningRatesView(View):
    def __init__(self, bot):
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
            
        desc = self.messages['EARNING_RATES_DESC']
        desc += self.messages.get('BOOSTER_MULTIPLIER_INFO', '')

        embed = discord.Embed(
            title=self.messages['EARNING_RATES_TITLE'],
            description=desc,
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
            if special_rates_list[-1] == "": special_rates_list.pop()
            special_rates_desc = "\n".join(special_rates_list)
            embed.description += "\n\n" + special_rates_desc
        
        footer_text = self.config['FOOTER_MESSAGES']['EARNING_RATES']
        embed.set_footer( text=f"────────────────────\n{footer_text}", icon_url=self.bot.user.avatar.url )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class ShopActionSelect(Select):
    def __init__(self, bot):
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
            embed.set_footer(text=f"────────────────────\n{footer_text}", icon_url=self.bot.user.avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=True)

        elif action == "purchase":
            modal = PurchaseModal(bot=self.bot)
            await interaction.response.send_modal(modal)

        elif action == "sell":
            modal = SellModal(bot=self.bot)
            await interaction.response.send_modal(modal)

class ShopView(View):
    def __init__(self, bot): 
        super().__init__(timeout=None)
        self.bot = bot
        self.config = bot.config
        self.messages = self.config['MESSAGES']
        self.embed_color = discord.Color(int(self.config['EMBED_COLOR'], 16))
        
        self.add_item(ShopActionSelect(bot=self.bot))

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
        
        currency_cog = self.bot.get_cog("CurrencyHandler")
        if currency_cog:
            multiplier = currency_cog._get_boost_multiplier(interaction.user)
            if multiplier > 1:
                embed.add_field(
                    name="<a:boost:1406856003716251708> Ưu Đãi Booster",
                    value=f"```diff\n+ Bạn đang nhận được x{multiplier} coin từ mọi hoạt động!\n```",
                    inline=False
                )

        if self.config.get('SHOP_EMBED_IMAGE_URL'):
            embed.set_image(url=self.config['SHOP_EMBED_IMAGE_URL'])

        footer_text = self.config['FOOTER_MESSAGES']['ACCOUNT_INFO']
        embed.set_footer(text=f"────────────────────\n{footer_text}", icon_url=self.bot.user.avatar.url)
        
        view = EarningRatesView(bot=self.bot)
        
        try:
            await interaction.user.send(embed=embed, view=view)
            await interaction.followup.send("✅ Đã gửi thông tin tài khoản vào tin nhắn riêng của bạn!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("⚠️ Tôi không thể gửi tin nhắn riêng cho bạn. Vui lòng bật tin nhắn từ thành viên server.", ephemeral=True)

# Fix loi load
async def setup(bot):
    pass