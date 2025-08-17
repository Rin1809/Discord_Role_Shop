import discord
from discord.ui import Button, View, Select
from database import database as db
from .shop_modals import PurchaseModal, SellModal, CustomRoleModal

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
            return await interaction.followup.send("<a:c_947079524435247135:1274398161200484446> Lỗi: Không tìm thấy câu trả lời cho câu hỏi này.", ephemeral=True)
        
        guild = self.bot.get_guild(self.config['GUILD_ID'])
        if not guild:
            return await interaction.followup.send("<a:c_947079524435247135:1274398161200484446> Lỗi nghiêm trọng: Không thể tìm thấy server được cấu hình.", ephemeral=True)
            
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

class ManageCustomRoleActionSelect(Select):
    def __init__(self, bot, role_to_edit: discord.Role):
        self.bot = bot
        self.role_to_edit = role_to_edit

        options = [
            discord.SelectOption(
                label="Sửa Tên & Màu",
                value="edit",
                description="Thay đổi tên và màu sắc của role.",
                emoji="✏️"
            ),
            discord.SelectOption(
                label="Xóa Vĩnh Viễn",
                value="delete",
                description="Xóa role này khỏi bạn và server.",
                emoji="🗑️"
            )
        ]
        super().__init__(placeholder="Chọn một hành động để quản lý role...", options=options)

    async def callback(self, interaction: discord.Interaction):
        action = self.values[0]

        if action == "edit":
            modal = CustomRoleModal(bot=self.bot, role_to_edit=self.role_to_edit)
            await interaction.response.send_modal(modal)

        elif action == "delete":
            await interaction.response.defer(ephemeral=True)
            try:
                if self.role_to_edit:
                    await self.role_to_edit.delete(reason=f"Người dùng {interaction.user} tự xóa")
                
                db.delete_custom_role_data(interaction.user.id, interaction.guild.id)
                await interaction.followup.send("✅ Đã xóa thành công role tùy chỉnh của bạn.", ephemeral=True)
                
                # vo hieu hoa
                self.disabled = True
                await interaction.edit_original_response(view=self.view)

            except discord.Forbidden:
                await interaction.followup.send("❌ Tôi không có quyền để xóa role này. Vui lòng liên hệ Admin.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"Đã xảy ra lỗi không xác định: {e}", ephemeral=True)

class ManageCustomRoleView(View):
    def __init__(self, bot, role_to_edit: discord.Role):
        super().__init__(timeout=180)
        self.bot = bot
        self.role_to_edit = role_to_edit
        self.add_item(ManageCustomRoleActionSelect(bot, role_to_edit))

class EarningRatesView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.config = bot.config
        self.messages = self.config['MESSAGES']
        self.embed_color = discord.Color(int(self.config['EMBED_COLOR'], 16))

    @discord.ui.button(label="?", style=discord.ButtonStyle.secondary, row=0)
    async def bot_info_callback(self, interaction: discord.Interaction, button: Button):
        qna_view = QnAView(bot=self.bot)
        await interaction.response.send_message(
            content="<:g_chamhoi:1326543673957027961> **Các câu hỏi thường gặp**\nVui lòng chọn một câu hỏi từ menu bên dưới:", 
            view=qna_view, 
            ephemeral=True
        )

    @discord.ui.button(label="Cách Đào Coin", style=discord.ButtonStyle.secondary, emoji="💰", row=1)
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

    @discord.ui.button(label="Quản lý Role cá nhân", style=discord.ButtonStyle.secondary, emoji="<a:g_l933518643407495238:1274398152941637694>", row=1)
    async def manage_custom_role_callback(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        
        guild_id = self.config['GUILD_ID']
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return await interaction.followup.send("Lỗi: Không thể tìm thấy server được cấu hình.", ephemeral=True)

        custom_role_config = self.config.get('CUSTOM_ROLE_CONFIG', {})
        min_boosts = custom_role_config.get('MIN_BOOST_COUNT', 2)
        
        is_test_user = (interaction.user.id == 873576591693873252)

        if not is_test_user:
            boost_count = 0
            member = guild.get_member(interaction.user.id)
            if member and member.premium_since:
                boost_count = guild.premium_subscribers.count(member)

            if boost_count < min_boosts:
                return await interaction.followup.send(
                    self.config['MESSAGES']['CUSTOM_ROLE_NO_BOOSTS'].format(min_boosts=min_boosts, boost_count=boost_count), 
                    ephemeral=True
                )
        
        custom_role_data = db.get_custom_role(interaction.user.id, guild_id)
        if not custom_role_data:
            return await interaction.followup.send(self.config['MESSAGES']['CUSTOM_ROLE_NOT_OWNED'], ephemeral=True)

        role_obj = guild.get_role(custom_role_data['role_id'])
        if not role_obj:
            db.delete_custom_role_data(interaction.user.id, guild_id)
            return await interaction.followup.send("<a:c_947079524435247135:1274398161200484446> Role tùy chỉnh của bạn không còn tồn tại trên server. Dữ liệu đã được xóa.", ephemeral=True)

        embed = discord.Embed(
            description=self.config['MESSAGES']['CUSTOM_ROLE_MANAGE_PROMPT'],
            color=role_obj.color
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url)
        embed.add_field(name="Tên Role Hiện Tại", value=f"```{role_obj.name}```", inline=True)
        embed.add_field(name="Màu Sắc", value=f"```{str(role_obj.color)}```", inline=True)
        
        if self.config.get('EARNING_RATES_IMAGE_URL'):
            embed.set_image(url=self.config.get('EARNING_RATES_IMAGE_URL'))
            
        view = ManageCustomRoleView(bot=self.bot, role_to_edit=role_obj)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class ShopActionSelect(Select):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.messages = self.config['MESSAGES']
        self.embed_color = discord.Color(int(self.config['EMBED_COLOR'], 16))

        options = [
            discord.SelectOption(label="Danh Sách Role", value="list_roles", description="Xem tất cả các role đang được bán.", emoji="<:MenheraFlower:1406458230317645906>"),
            discord.SelectOption(label="Mua Role", value="purchase", description="Sở hữu ngay role bạn yêu thích.", emoji="<:MenheraFlowers:1406458246528635031>"),
            discord.SelectOption(label="Bán Role", value="sell", description="Bán lại role đã mua để nhận lại coin.", emoji="<a:MenheraNod:1406458257349935244>"),
            discord.SelectOption(label="Role Tùy Chỉnh (Booster)", value="custom_role", description="Tạo role với tên và màu của riêng bạn.", emoji="<a:boost:1406487216649277510>")
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
            await interaction.response.send_modal(PurchaseModal(bot=self.bot))

        elif action == "sell":
            await interaction.response.send_modal(SellModal(bot=self.bot))
            
        elif action == "custom_role":
            custom_role_config = self.config.get('CUSTOM_ROLE_CONFIG', {})
            min_boosts = custom_role_config.get('MIN_BOOST_COUNT', 2)
            
            is_test_user = (interaction.user.id == 873576591693873252)
            
            if not is_test_user: 
                boost_count = 0
                if interaction.user.premium_since:
                    boost_count = interaction.guild.premium_subscribers.count(interaction.user)
                if boost_count < min_boosts:
                    msg = self.config['MESSAGES']['CUSTOM_ROLE_NO_BOOSTS'].format(min_boosts=min_boosts, boost_count=boost_count)
                    await interaction.response.send_message(msg, ephemeral=True)
                    return

            if db.get_custom_role(interaction.user.id, interaction.guild.id):
                msg = self.config['MESSAGES']['CUSTOM_ROLE_ALREADY_OWNED']
                await interaction.response.send_message(msg, ephemeral=True)
                return

            price = custom_role_config.get('PRICE', 1000)
            user_data = db.get_or_create_user(interaction.user.id, interaction.guild.id)
            if user_data['balance'] < price:
                msg = self.config['MESSAGES']['CUSTOM_ROLE_NO_COIN'].format(price=price, balance=user_data['balance'])
                await interaction.response.send_message(msg, ephemeral=True)
                return
            
            await interaction.response.send_modal(CustomRoleModal(bot=self.bot, price=price))

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
                    name="<a:zgif_BoosterBadgesRoll:1406487084583358474> Ưu Đãi Booster",
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
            await interaction.followup.send("<a:c_947079524435247135:1274398161200484446> Tôi không thể gửi tin nhắn riêng cho bạn. Vui lòng bật tin nhắn từ thành viên server.", ephemeral=True)

async def setup(bot):
    pass