import discord
from discord.ui import Button, View, Select
from database import database as db
from .shop_modals import PurchaseModal, SellModal, CustomRoleModal
import math

ROLES_PER_PAGE = 5

class PaginatedRoleListView(View):
    def __init__(self, bot, interaction: discord.Interaction, guild_config: dict, roles: list):
        super().__init__(timeout=180)
        self.bot = bot
        self.interaction = interaction
        self.guild_config = guild_config
        self.roles = roles
        self.current_page = 0
        self.total_pages = math.ceil(len(self.roles) / ROLES_PER_PAGE)
        self.messages = self.guild_config.get('MESSAGES', {})
        self.embed_color = discord.Color(int(self.guild_config.get('EMBED_COLOR', '0xff00af'), 16))

    async def get_page_embed(self) -> discord.Embed:
        # tao embed cho trang hien tai
        embed = discord.Embed(
            title=self.messages.get('SHOP_ROLES_TITLE', "Danh sách role"),
            color=self.embed_color
        )
        start_index = self.current_page * ROLES_PER_PAGE
        end_index = start_index + ROLES_PER_PAGE
        roles_on_page = self.roles[start_index:end_index]

        if not roles_on_page:
            embed.description = self.messages.get('SHOP_ROLES_EMPTY', "Shop trống.")
        else:
            role_list_str = ""
            for i, role_data in enumerate(roles_on_page):
                role = self.interaction.guild.get_role(role_data['role_id'])
                if role:
                    role_list_str += f"### {start_index + i + 1}. {role.mention}\n> **Giá:** `{role_data['price']}` 🪙\n"
            
            base_desc = self.messages.get('SHOP_ROLES_DESC', '')
            embed.description = (base_desc + "\n\n" + role_list_str) if base_desc else role_list_str
        
        footer_text = f"Trang {self.current_page + 1}/{self.total_pages}"
        embed.set_footer(text=footer_text, icon_url=self.bot.user.avatar.url)
        return embed

    async def update_view(self):
        # cap nhat nut bam
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page >= self.total_pages - 1
        embed = await self.get_page_embed()
        await self.interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Trước", style=discord.ButtonStyle.secondary, emoji="⬅️", custom_id="prev_page")
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_view()

    @discord.ui.button(label="Sau", style=discord.ButtonStyle.secondary, emoji="➡️", custom_id="next_page")
    async def next_page(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await self.update_view()

class QnASelect(Select):
    def __init__(self, bot, guild_config, guild_id: int):
        self.bot = bot
        self.guild_config = guild_config
        self.guild_id = guild_id 
        self.qna_data = self.guild_config.get("QNA_DATA", [])
        self.embed_color = discord.Color(int(self.guild_config.get('EMBED_COLOR', '0xff00af'), 16))

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
        
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return await interaction.followup.send("Lỗi: Không thể tìm thấy server tương ứng.", ephemeral=True)
            
        embed = discord.Embed(
            title=f"{answer_data.get('emoji', '❓')} {answer_data.get('answer_title', selected_label)}",
            description=answer_data.get("answer_description", "Chưa có câu trả lời."),
            color=self.embed_color
        )
        embed.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)

        await interaction.followup.send(embed=embed, ephemeral=True)

class QnAView(View):
    def __init__(self, bot, guild_config, guild_id: int):
        super().__init__(timeout=180) 
        self.add_item(QnASelect(bot, guild_config, guild_id))

class ManageCustomRoleActionSelect(Select):
    def __init__(self, bot, guild_config, role_to_edit: discord.Role, guild_id: int):
        self.bot = bot
        self.guild_config = guild_config
        self.role_to_edit = role_to_edit
        self.guild_id = guild_id

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
            modal = CustomRoleModal(bot=self.bot, guild_id=self.guild_id, guild_config=self.guild_config, role_to_edit=self.role_to_edit)
            await interaction.response.send_modal(modal)

        elif action == "delete":
            await interaction.response.defer(ephemeral=True)
            try:
                if self.role_to_edit:
                    await self.role_to_edit.delete(reason=f"Người dùng {interaction.user} tự xóa")
                
                db.delete_custom_role_data(interaction.user.id, self.guild_id)
                await interaction.followup.send("✅ Đã xóa thành công role tùy chỉnh của bạn.", ephemeral=True)
                
                self.disabled = True
                await interaction.edit_original_response(view=self.view)

            except discord.Forbidden:
                await interaction.followup.send("❌ Tôi không có quyền để xóa role này. Vui lòng liên hệ Admin.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"Đã xảy ra lỗi không xác định: {e}", ephemeral=True)

class ManageCustomRoleView(View):
    def __init__(self, bot, guild_config, role_to_edit: discord.Role, guild_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.add_item(ManageCustomRoleActionSelect(bot, guild_config, role_to_edit, guild_id))

class EarningRatesView(View):
    def __init__(self, bot, guild_config, guild_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_config = guild_config
        self.guild_id = guild_id
        self.messages = self.guild_config.get('MESSAGES', {})
        self.embed_color = discord.Color(int(self.guild_config.get('EMBED_COLOR', '0xff00af'), 16))

    @discord.ui.button(label="?", style=discord.ButtonStyle.secondary, row=0)
    async def bot_info_callback(self, interaction: discord.Interaction, button: Button):
        qna_view = QnAView(bot=self.bot, guild_config=self.guild_config, guild_id=self.guild_id)
        await interaction.response.send_message(
            content="<:g_chamhoi:1326543673957027961> **Các câu hỏi thường gặp**\nVui lòng chọn một câu hỏi từ menu bên dưới:", 
            view=qna_view, 
            ephemeral=True
        )

    @discord.ui.button(label="Cách Đào Coin", style=discord.ButtonStyle.secondary, emoji="💰", row=1)
    async def show_rates_callback(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return await interaction.followup.send("Lỗi: Không thể tìm thấy server tương ứng.", ephemeral=True)

        desc_parts = []
        
        if base_desc := self.messages.get('EARNING_RATES_DESC'):
            desc_parts.append(base_desc)

        if booster_info := self.messages.get('BOOSTER_MULTIPLIER_INFO'):
            desc_parts.append(booster_info)

        rates_lines = []
        currency_rates = self.guild_config.get('CURRENCY_RATES', {})

        if default_rates := currency_rates.get('default'):
            rates_lines.append(f"**<:g_chamhoi:1326543673957027961> Tỷ lệ mặc định**")
            if msg_rate := default_rates.get('MESSAGES_PER_COIN'):
                rates_lines.append(f"> <a:timchat:1406136711741706301> `{msg_rate}` tin nhắn = `1` <a:coin:1406137409384480850>")
            if react_rate := default_rates.get('REACTIONS_PER_COIN'):
                rates_lines.append(f"> <:reaction:1406136638421336104> `{react_rate}` reactions = `1` <a:coin:1406137409384480850>")
            rates_lines.append("")

        if categories_config := currency_rates.get('categories', {}):
            for cat_id, rates in categories_config.items():
                category = guild.get_channel(int(cat_id))
                if category:
                    rates_lines.append(f"**<:g_chamhoi:1326543673957027961> Danh mục: {category.name}**")
                    if msg_rate := rates.get('MESSAGES_PER_COIN'):
                        rates_lines.append(f"> <a:timchat:1406136711741706301> `{msg_rate}` tin nhắn = `1` <a:coin:1406137409384480850>")
                    if react_rate := rates.get('REACTIONS_PER_COIN'):
                        rates_lines.append(f"> <:reaction:1406136638421336104> `{react_rate}` reactions = `1` <a:coin:1406137409384480850>")
                    rates_lines.append("") 

        if channels_config := currency_rates.get('channels', {}):
            for chan_id, rates in channels_config.items():
                channel = guild.get_channel(int(chan_id))
                if channel:
                    rates_lines.append(f"**<:channel:1406136670709092422> Kênh: {channel.mention}**")
                    if msg_rate := rates.get('MESSAGES_PER_COIN'):
                        rates_lines.append(f"> <a:timchat:1406136711741706301> `{msg_rate}` tin nhắn = `1` <a:coin:1406137409384480850>")
                    if react_rate := rates.get('REACTIONS_PER_COIN'):
                        rates_lines.append(f"> <:reaction:1406136638421336104> `{react_rate}` reactions = `1` <a:coin:1406137409384480850>")
                    rates_lines.append("") 
        
        if rates_lines:
            if rates_lines[-1] == "": rates_lines.pop()
            desc_parts.append("\n".join(rates_lines))

        embed = discord.Embed(
            title=self.messages.get('EARNING_RATES_TITLE', "Tỷ lệ kiếm coin"),
            description="\n\n".join(desc_parts),
            color=self.embed_color
        )
        
        if guild.icon:
            embed.set_author(name=guild.name, icon_url=guild.icon.url)
            embed.set_thumbnail(url=guild.icon.url)
        else:
            embed.set_author(name=guild.name)

        if self.guild_config.get('EARNING_RATES_IMAGE_URL'):
            embed.set_image(url=self.guild_config.get('EARNING_RATES_IMAGE_URL'))
        
        footer_text = self.guild_config.get('FOOTER_MESSAGES', {}).get('EARNING_RATES', '')
        embed.set_footer(text=f"────────────────────\n{footer_text}", icon_url=self.bot.user.avatar.url)
        
        await interaction.followup.send(embed=embed, ephemeral=True)


    @discord.ui.button(label="Quản lý Role cá nhân", style=discord.ButtonStyle.secondary, emoji="<a:g_l933518643407495238:1274398152941637694>", row=1)
    async def manage_custom_role_callback(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return await interaction.followup.send("Lỗi: Không thể tìm thấy server tương ứng.", ephemeral=True)

        guild_id = guild.id

        custom_role_config = self.guild_config.get('CUSTOM_ROLE_CONFIG', {})
        min_boosts = custom_role_config.get('MIN_BOOST_COUNT', 2)
        
        is_test_user = (interaction.user.id == 873576591693873252)
        
        member = guild.get_member(interaction.user.id)
        if not member:
             return await interaction.followup.send("Lỗi: Không thể tìm thấy bạn trên server.", ephemeral=True)

        if not is_test_user:
            boost_count = 0
            if member and member.premium_since:
                boost_count = sum(1 for m in guild.premium_subscribers if m.id == member.id)

            if boost_count < min_boosts:
                msg = self.messages.get('CUSTOM_ROLE_NO_BOOSTS', "Bạn cần có ít nhất {min_boosts} boost để dùng tính năng này.").format(min_boosts=min_boosts, boost_count=boost_count)
                return await interaction.followup.send(msg, ephemeral=True)
        
        custom_role_data = db.get_custom_role(interaction.user.id, guild_id)
        if not custom_role_data:
            return await interaction.followup.send(self.messages.get('CUSTOM_ROLE_NOT_OWNED', "Bạn chưa tạo role tùy chỉnh nào cả."), ephemeral=True)

        role_obj = guild.get_role(custom_role_data['role_id'])
        if not role_obj:
            db.delete_custom_role_data(interaction.user.id, guild_id)
            return await interaction.followup.send("<a:c_947079524435247135:1274398161200484446> Role tùy chỉnh của bạn không còn tồn tại. Dữ liệu đã được xóa.", ephemeral=True)

        embed = discord.Embed(
            description=self.messages.get('CUSTOM_ROLE_MANAGE_PROMPT', "Đây là role tùy chỉnh của bạn. Sử dụng menu bên dưới để Sửa hoặc Xóa."),
            color=role_obj.color
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url)
        embed.add_field(name="Tên Role Hiện Tại", value=f"```{role_obj.name}```", inline=True)
        embed.add_field(name="Màu Sắc", value=f"```{str(role_obj.color)}```", inline=True)
        
        if self.guild_config.get('SHOP_EMBED_IMAGE_URL'):
            embed.set_image(url=self.guild_config.get('SHOP_EMBED_IMAGE_URL'))
            
        view = ManageCustomRoleView(bot=self.bot, guild_config=self.guild_config, role_to_edit=role_obj, guild_id=guild_id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class ShopActionSelect(Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="Danh Sách Role", value="list_roles", description="Xem tất cả các role đang được bán.", emoji="<:MenheraFlower:1406458230317645906>"),
            discord.SelectOption(label="Mua Role", value="purchase", description="Sở hữu ngay role bạn yêu thích.", emoji="<:MenheraFlowers:1406458246528635031>"),
            discord.SelectOption(label="Bán Role", value="sell", description="Bán lại role đã mua để nhận lại coin.", emoji="<a:MenheraNod:1406458257349935244>"),
            discord.SelectOption(label="Role Tùy Chỉnh (Booster)", value="custom_role", description="Tạo role với tên và màu của riêng bạn.", emoji="<a:boost:1406487216649277510>")
        ]
        super().__init__(custom_id="shop_view:action_select", placeholder="Chọn một hành động giao dịch...", min_values=1, max_values=1, options=options)
    
    async def callback(self, interaction: discord.Interaction):
        guild_config = self.bot.guild_configs.get(str(interaction.guild.id))
        if not guild_config:
            return await interaction.response.send_message("Lỗi: Không tìm thấy config cho server.", ephemeral=True, delete_after=10)
        
        messages = guild_config.get('MESSAGES', {})
        action = self.values[0]

        if action == "list_roles":
            await interaction.response.defer(ephemeral=True)
            shop_roles = db.get_shop_roles(interaction.guild.id)
            
            if not shop_roles:
                embed = discord.Embed(
                    title=messages.get('SHOP_ROLES_TITLE', "Danh sách role"),
                    description=messages.get('SHOP_ROLES_EMPTY', "Shop hiện đang trống."),
                    color=discord.Color.orange()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # tao view phan trang
            paginated_view = PaginatedRoleListView(self.bot, interaction, guild_config, shop_roles)
            initial_embed = await paginated_view.get_page_embed()
            paginated_view.prev_page.disabled = True
            paginated_view.next_page.disabled = paginated_view.total_pages <= 1
            
            await interaction.followup.send(embed=initial_embed, view=paginated_view, ephemeral=True)

        elif action == "purchase":
            await interaction.response.send_modal(PurchaseModal(bot=self.bot))

        elif action == "sell":
            await interaction.response.send_modal(SellModal(bot=self.bot))
            
        elif action == "custom_role":
            await interaction.response.defer(ephemeral=True)
            custom_role_config = guild_config.get('CUSTOM_ROLE_CONFIG', {})
            min_boosts = custom_role_config.get('MIN_BOOST_COUNT', 2)
            
            is_test_user = (interaction.user.id == 873576591693873252)
            
            if not is_test_user: 
                boost_count = 0
                if interaction.user.premium_since:
                    boost_count = sum(1 for m in interaction.guild.premium_subscribers if m.id == interaction.user.id)
                if boost_count < min_boosts:
                    msg = messages.get('CUSTOM_ROLE_NO_BOOSTS', "Bạn cần có ít nhất {min_boosts} boost để dùng tính năng này.").format(min_boosts=min_boosts, boost_count=boost_count)
                    await interaction.followup.send(msg, ephemeral=True)
                    return

            if db.get_custom_role(interaction.user.id, interaction.guild.id):
                msg = messages.get('CUSTOM_ROLE_ALREADY_OWNED', "Bạn đã có một role tùy chỉnh rồi. Hãy dùng nút 'Quản lý Role' để chỉnh sửa.")
                await interaction.followup.send(msg, ephemeral=True)
                return

            price = int(custom_role_config.get('PRICE', 1000))
            user_data = db.get_or_create_user(interaction.user.id, interaction.guild.id)
            if user_data['balance'] < price:
                msg = messages.get('CUSTOM_ROLE_NO_COIN', "Bạn không đủ coin! Cần {price} coin nhưng bạn chỉ có {balance}.").format(price=price, balance=user_data['balance'])
                await interaction.followup.send(msg, ephemeral=True)
                return
            
            await interaction.response.send_modal(CustomRoleModal(bot=self.bot, guild_id=interaction.guild.id, guild_config=guild_config, price=price))

class ShopView(View):
    def __init__(self, bot): 
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(ShopActionSelect(bot=self.bot))

    @discord.ui.button(label="Tài Khoản Của Tôi", style=discord.ButtonStyle.secondary, custom_id="shop_view:account", emoji="<a:z_cat_yolo:1326542766330740818>")
    async def account_button_callback(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        guild_config = self.bot.guild_configs.get(str(interaction.guild.id))
        if not guild_config:
            return await interaction.followup.send("Lỗi: Không tìm thấy config cho server.", ephemeral=True)
        
        messages = guild_config.get('MESSAGES', {})
        embed_color = discord.Color(int(guild_config.get('EMBED_COLOR', '0xff00af'), 16))
        
        user_data = db.get_or_create_user(interaction.user.id, interaction.guild.id)

        embed = discord.Embed(
            title=messages.get('ACCOUNT_INFO_TITLE', "Tài khoản"),
            description=messages.get('ACCOUNT_INFO_DESC', ''),
            color=embed_color
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        balance_str = messages.get('BALANCE_FIELD_VALUE', "{balance} coin").format(balance=user_data['balance'])
        embed.add_field(name=f"```{messages.get('BALANCE_FIELD_NAME', 'Số dư')}```", value=balance_str, inline=False)
        
        currency_cog = self.bot.get_cog("CurrencyHandler")
        if currency_cog:
            multiplier = currency_cog._get_boost_multiplier(interaction.user)
            if multiplier > 1:
                embed.add_field(
                    name="<a:zgif_BoosterBadgesRoll:1406487084583358474> Ưu Đãi Booster",
                    value=f"```diff\n+ Bạn đang nhận được x{multiplier} coin từ mọi hoạt động!\n```",
                    inline=False
                )

        if guild_config.get('SHOP_EMBED_IMAGE_URL'):
            embed.set_image(url=guild_config['SHOP_EMBED_IMAGE_URL'])

        footer_text = guild_config.get('FOOTER_MESSAGES', {}).get('ACCOUNT_INFO', '')
        embed.set_footer(text=f"────────────────────\n{footer_text}", icon_url=self.bot.user.avatar.url)
        
        view = EarningRatesView(bot=self.bot, guild_config=guild_config, guild_id=interaction.guild.id)
        
        try:
            await interaction.user.send(embed=embed, view=view)
            await interaction.followup.send("✅ Đã gửi thông tin tài khoản vào tin nhắn riêng của bạn!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("<a:c_947079524435247135:1274398161200484446> Tôi không thể gửi tin nhắn riêng cho bạn. Vui lòng bật tin nhắn từ thành viên server.", ephemeral=True)

async def setup(bot):
    pass