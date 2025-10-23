import discord
from discord.ui import Button, View, Select
from database import database as db
from .shop_modals import CustomRoleModal, SellModal
import math

ROLES_PER_PAGE = 5

class ConfirmDeleteView(View):
    def __init__(self, bot, role_to_delete: discord.Role, guild_id: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.role_to_delete = role_to_delete
        self.guild_id = guild_id
        self.message = None

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                item.disabled = True
            await self.message.edit(content="Đã hết thời gian xác nhận.", view=self)

    @discord.ui.button(label="Xác nhận Xóa", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_callback(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        try:
            shop_roles = db.get_shop_roles(self.guild_id)
            role_data = next((r for r in shop_roles if r['role_id'] == self.role_to_delete.id), None)
            
            if self.role_to_delete:
                await self.role_to_delete.delete(reason=f"Nguoi dung {interaction.user} tu xoa")
            
            db.delete_custom_role_data(interaction.user.id, self.guild_id)
            db.remove_role_from_shop(self.role_to_delete.id, self.guild_id)
            
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(content="✅ Đã xóa thành công role tùy chỉnh của bạn.", view=self, embed=None)

        except discord.Forbidden:
            await interaction.followup.send("❌ Tôi không có quyền để xóa role này. Vui lòng liên hệ Admin.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Đã xảy ra lỗi không xác định: {e}", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Hủy", style=discord.ButtonStyle.secondary)
    async def cancel_callback(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(content="Đã hủy thao tác.", view=self, embed=None)
        self.stop()

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
        self.embed_color = discord.Color(int(str(self.guild_config.get('EMBED_COLOR', '#ff00af')).lstrip('#'), 16))

    async def get_page_embed(self) -> discord.Embed:
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
                    if creator_id := role_data.get('creator_id'):
                        creator = self.interaction.guild.get_member(creator_id)
                        creator_mention = creator.mention if creator else f"ID: {creator_id}"
                        role_list_str += f"> **Người tạo:** {creator_mention}\n"
            
            base_desc = self.messages.get('SHOP_ROLES_DESC', '')
            embed.description = (base_desc + "\n\n" + role_list_str) if base_desc else role_list_str
        
        footer_text = f"Trang {self.current_page + 1}/{self.total_pages}"
        embed.set_footer(text=footer_text, icon_url=self.bot.user.avatar.url)
        return embed

    async def update_view(self):
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

class RoleDetailView(View):
    def __init__(self, bot, guild_config, role_obj: discord.Role, role_data: dict):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_config = guild_config
        self.role_obj = role_obj
        self.role_data = role_data
        self.embed_color = discord.Color(int(str(self.guild_config.get('EMBED_COLOR', '#ff00af')).lstrip('#'), 16))

    @discord.ui.button(label="Mua Ngay", style=discord.ButtonStyle.secondary, emoji="<:MenheraNya3:1406458270641819840>")
    async def buy_callback(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        
        price = self.role_data['price']
        user_data = db.get_or_create_user(interaction.user.id, interaction.guild.id)

        if self.role_obj in interaction.user.roles:
            button.disabled = True
            button.label = "Đã sở hữu"
            await interaction.edit_original_response(view=self)
            return await interaction.followup.send(f"Bạn đã sở hữu role {self.role_obj.mention} rồi!", ephemeral=True)

        if user_data['balance'] < price:
            return await interaction.followup.send(f"Bạn không đủ coin! Cần **{price} coin** nhưng bạn chỉ có **{user_data['balance']}**.", ephemeral=True)

        new_balance = user_data['balance'] - price
        try:
            await interaction.user.add_roles(self.role_obj, reason="Mua từ shop")
            db.update_user_data(interaction.user.id, interaction.guild.id, balance=new_balance)
            db.log_transaction(
                guild_id=interaction.guild.id, user_id=interaction.user.id,
                transaction_type='buy_role', item_name=self.role_obj.name,
                amount_changed=-price, new_balance=new_balance
            )
        except discord.Forbidden:
            return await interaction.followup.send("❌ Lỗi! Tôi không có quyền để gán role này. Giao dịch đã bị hủy.", ephemeral=True)

        button.disabled = True
        button.label = "Mua thành công"
        await interaction.edit_original_response(view=self)
        
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
        receipt_embed.add_field(name="Sản Phẩm", value=f"```{self.role_obj.name}```", inline=True)
        receipt_embed.add_field(name="Chi Phí", value=f"```- {price:,} coin```", inline=True)
        receipt_embed.add_field(name="Số Dư Mới", value=f"```{new_balance:,} coin```", inline=True)

        if self.guild_config.get('SHOP_EMBED_IMAGE_URL'):
            receipt_embed.set_image(url=self.guild_config.get('SHOP_EMBED_IMAGE_URL'))
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


class RoleListSelect(Select):
    def __init__(self, bot, guild_config: dict, roles: list):
        self.bot = bot
        self.guild_config = guild_config
        self.roles_data = {str(r['role_id']): r for r in roles}
        self.embed_color = discord.Color(int(str(self.guild_config.get('EMBED_COLOR', '#ff00af')).lstrip('#'), 16))
        
        options = []
        if roles:
            guild_id = roles[0]['guild_id']
            guild = bot.get_guild(guild_id)
            if guild:
                for i, role_data in enumerate(roles):
                    role = guild.get_role(role_data['role_id'])
                    if role:
                        # logic xd icon
                        final_emoji = "<:g_chamhoi:1326543673957027961>"
                        if isinstance(role.icon, discord.Emoji):
                            final_emoji = role.icon
                        elif role.icon is not None: 
                            final_emoji = "🖼️"
                        
                        options.append(discord.SelectOption(
                            label=f"{i+1}. {role.name}",
                            description=f"Giá: {role_data['price']:,} coin",
                            value=str(role.id),
                            emoji=final_emoji
                        ))

        super().__init__(
            placeholder="Chọn một role để xem chi tiết & mua...", 
            min_values=1, 
            max_values=1, 
            options=options[:25]
        )
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        role_id_str = self.values[0]
        role_data = self.roles_data.get(role_id_str)
        role = interaction.guild.get_role(int(role_id_str))

        if not role_data or not role:
            return await interaction.followup.send("Role này không còn tồn tại.", ephemeral=True)
        
        embed_title = f"Thông tin Role: {role.name}"
        embed = discord.Embed(
            description=f"Đây là thông tin chi tiết về role bạn đã chọn.",
            color=role.color if role.color.value != 0 else self.embed_color
        )
        
        # them icon
        if role.icon:
            if isinstance(role.icon, discord.Asset):
                embed.set_image(url=role.icon.url)
            elif isinstance(role.icon, discord.Emoji):
                embed_title = f"Thông tin Role: {role.icon} {role.name}"
        
        embed.title = embed_title
        
        creator_id = role_data.get('creator_id')
        if creator_id:
            creator = interaction.guild.get_member(creator_id)
            if creator:
                embed.set_thumbnail(url=creator.display_avatar.url)
                embed.add_field(name="Người Tạo", value=creator.mention, inline=True)
            else:
                if interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                embed.add_field(name="Người Tạo", value=f"ID: {creator_id} (đã rời)", inline=True)
        else:
            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)
            
        embed.add_field(name="Role", value=role.mention, inline=True)
        embed.add_field(name="Giá Mua", value=f"```{role_data['price']:,} coin```", inline=True)
        
        refund_percentage = self.guild_config.get('SELL_REFUND_PERCENTAGE', 0.65)
        refund_amount = int(role_data['price'] * refund_percentage)
        embed.add_field(name="Bán Lại", value=f"```{refund_amount:,} coin ({refund_percentage:.0%})```", inline=False)
        
        view = RoleDetailView(self.bot, self.guild_config, role, role_data)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

class RoleListView(View):
    def __init__(self, bot, guild_config: dict, roles: list):
        super().__init__(timeout=180)
        self.add_item(RoleListSelect(bot, guild_config, roles))


class QnASelect(Select):
    def __init__(self, bot, guild_config, guild_id: int):
        self.bot = bot
        self.guild_config = guild_config
        self.guild_id = guild_id 
        self.qna_data = self.guild_config.get("QNA_DATA", [])
        self.embed_color = discord.Color(int(str(self.guild_config.get('EMBED_COLOR', '#ff00af')).lstrip('#'), 16))

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
                label="Sửa Tên & Style",
                value="edit",
                description="Thay đổi tên, màu sắc và style của role.",
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
        
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            await interaction.response.send_message("Lỗi: Không tìm thấy server. Vui lòng thử lại.", ephemeral=True)
            return

        member = guild.get_member(interaction.user.id)
        if not member:
            await interaction.response.send_message("Lỗi: Không tìm thấy bạn trong server. Vui lòng thử lại.", ephemeral=True)
            return

        is_booster = member.premium_since is not None

        if action == 'edit':
            # Ktra so du truoc khi phan hoi
            edit_price = self.guild_config.get('CUSTOM_ROLE_CONFIG', {}).get('EDIT_PRICE', 0)
            if edit_price > 0:
                user_data = db.get_or_create_user(interaction.user.id, guild.id)
                if user_data['balance'] < edit_price:
                    await interaction.response.send_message(
                        f"Bạn không đủ coin để chỉnh sửa! Cần **{edit_price:,} coin** nhưng bạn chỉ có **{user_data['balance']:,}**.",
                        ephemeral=True
                    )
                    return
            
            # Phan luong phan hoi
            if is_booster:
                # Luong cho booster: defer -> followup voi view moi
                await interaction.response.defer(ephemeral=True)
                view = CustomRoleStyleSelectView(bot=self.bot, guild_config=self.guild_config, guild_id=self.guild_id, role_to_edit=self.role_to_edit, is_booster=True)
                await interaction.followup.send("✨ Vui lòng chọn style bạn muốn đổi sang:", view=view, ephemeral=True)
            else:
                # Luong cho member thuong: mo modal truc tiep
                modal = CustomRoleModal(bot=self.bot, guild_id=self.guild_id, guild_config=self.guild_config, style="Solid", is_booster=False, role_to_edit=self.role_to_edit)
                await interaction.response.send_modal(modal)

        elif action == "delete":
            embed = discord.Embed(
                title="Xác nhận Xóa Role",
                description=f"Bạn có chắc chắn muốn xóa vĩnh viễn role {self.role_to_edit.mention} không?\n**Hành động này không thể hoàn tác.**",
                color=discord.Color.red()
            )
            confirm_view = ConfirmDeleteView(bot=self.bot, role_to_delete=self.role_to_edit, guild_id=self.guild_id)
            await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)
            confirm_view.message = await interaction.original_response()


class ManageCustomRoleView(View):
    def __init__(self, bot, guild_config, role_to_edit: discord.Role, guild_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.add_item(ManageCustomRoleActionSelect(bot, guild_config, role_to_edit, guild_id))



class AccountActionSelect(Select):
    def __init__(self, bot, guild_config, guild_id: int, custom_role_data: dict = None):
        self.bot = bot
        self.guild_config = guild_config
        self.guild_id = guild_id
        self.messages = self.guild_config.get('MESSAGES', {})
        self.embed_color = discord.Color(int(str(self.guild_config.get('EMBED_COLOR', '#ff00af')).lstrip('#'), 16))

        options = [
            discord.SelectOption(
                label="Cách Đào Coin",
                value="show_rates",
                description="Xem tỷ lệ nhận coin từ tin nhắn và reaction.",
                emoji="💰"
            ),
            discord.SelectOption(
                label="Câu hỏi thường gặp",
                value="show_qna",
                description="Xem các câu hỏi và câu trả lời về bot.",
                emoji="❓"
            )
        ]

        if custom_role_data:
            options.append(discord.SelectOption(
                label="Quản lý Role cá nhân",
                value="manage_role",
                description="Sửa hoặc xóa role tùy chỉnh của bạn.",
                emoji="<a:g_l933518643407495238:1274398152941637694>"
            ))
        
        super().__init__(placeholder="Chọn một mục để xem thông tin...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        action = self.values[0]

        if action == "show_qna":
            qna_view = QnAView(bot=self.bot, guild_config=self.guild_config, guild_id=self.guild_id)
            await interaction.followup.send(
                content="<:g_chamhoi:1326543673957027961> **Các câu hỏi thường gặp**\nVui lòng chọn một câu hỏi từ menu bên dưới:", 
                view=qna_view, 
                ephemeral=True
            )
        
        elif action == "show_rates":
            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                return await interaction.followup.send("Lỗi: Không thể tìm thấy server tương ứng.", ephemeral=True)

            desc_parts = []
            if base_desc := self.messages.get('EARNING_RATES_DESC'): desc_parts.append(base_desc)
            if booster_info := self.messages.get('BOOSTER_MULTIPLIER_INFO'): desc_parts.append(booster_info)
            
            rates_lines = []
            currency_rates = self.guild_config.get('CURRENCY_RATES', {})
            if default_rates := currency_rates.get('default'):
                rates_lines.append(f"**<:g_chamhoi:1326543673957027961> Tỷ lệ mặc định**")
                if msg_rate := default_rates.get('MESSAGES_PER_COIN'): rates_lines.append(f"> <a:timchat:1406136711741706301> `{msg_rate}` tin nhắn = `1` <a:coin:1406137409384480850>")
                if react_rate := default_rates.get('REACTIONS_PER_COIN'): rates_lines.append(f"> <:reaction:1406136638421336104> `{react_rate}` reactions = `1` <a:coin:1406137409384480850>")
                rates_lines.append("")

            if categories_config := currency_rates.get('categories', {}):
                for cat_id, rates in categories_config.items():
                    category = guild.get_channel(int(cat_id))
                    if category:
                        rates_lines.append(f"**<:g_chamhoi:1326543673957027961> Danh mục: {category.name}**")
                        if msg_rate := rates.get('MESSAGES_PER_COIN'): rates_lines.append(f"> <a:timchat:1406136711741706301> `{msg_rate}` tin nhắn = `1` <a:coin:1406137409384480850>")
                        if react_rate := rates.get('REACTIONS_PER_COIN'): rates_lines.append(f"> <:reaction:1406136638421336104> `{react_rate}` reactions = `1` <a:coin:1406137409384480850>")
                        rates_lines.append("") 
            
            if channels_config := currency_rates.get('channels', {}):
                for chan_id, rates in channels_config.items():
                    channel = guild.get_channel(int(chan_id))
                    if channel:
                        rates_lines.append(f"**<:channel:1406136670709092422> Kênh: {channel.mention}**")
                        if msg_rate := rates.get('MESSAGES_PER_COIN'): rates_lines.append(f"> <a:timchat:1406136711741706301> `{msg_rate}` tin nhắn = `1` <a:coin:1406137409384480850>")
                        if react_rate := rates.get('REACTIONS_PER_COIN'): rates_lines.append(f"> <:reaction:1406136638421336104> `{react_rate}` reactions = `1` <a:coin:1406137409384480850>")
                        rates_lines.append("") 

            if rates_lines:
                if rates_lines[-1] == "": rates_lines.pop()
                desc_parts.append("\n".join(rates_lines))
            
            embed = discord.Embed(title=self.messages.get('EARNING_RATES_TITLE', "Tỷ lệ kiếm coin"), description="\n\n".join(desc_parts), color=self.embed_color)
            
            if guild.icon:
                embed.set_author(name=guild.name, icon_url=guild.icon.url)
                embed.set_thumbnail(url=guild.icon.url)
            else: embed.set_author(name=guild.name)

            if self.guild_config.get('EARNING_RATES_IMAGE_URL'): embed.set_image(url=self.guild_config.get('EARNING_RATES_IMAGE_URL'))
            
            footer_text = self.guild_config.get('FOOTER_MESSAGES', {}).get('EARNING_RATES', '')
            embed.set_footer(text=f"────────────────────\n{footer_text}", icon_url=self.bot.user.avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        elif action == "manage_role":
            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                return await interaction.followup.send("Lỗi: Không thể tìm thấy server tương ứng.", ephemeral=True)

            custom_role_data = db.get_custom_role(interaction.user.id, self.guild_id)
            if not custom_role_data:
                return await interaction.followup.send(self.messages.get('CUSTOM_ROLE_NOT_OWNED', "Bạn chưa tạo role tùy chỉnh nào cả."), ephemeral=True)

            role_obj = guild.get_role(custom_role_data['role_id'])
            if not role_obj:
                db.delete_custom_role_data(interaction.user.id, self.guild_id)
                return await interaction.followup.send("<a:c_947079524435247135:1274398161200484446> Role tùy chỉnh của bạn không còn tồn tại. Dữ liệu đã được xóa.", ephemeral=True)

            embed = discord.Embed(
                description=self.messages.get('CUSTOM_ROLE_MANAGE_PROMPT', "Đây là role tùy chỉnh của bạn. Sử dụng menu bên dưới để Sửa hoặc Xóa."),
                color=role_obj.color
            )
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.add_field(name="Tên Role Hiện Tại", value=f"```{role_obj.name}```", inline=True)
            embed.add_field(name="Màu Sắc", value=f"```{str(role_obj.color)}```", inline=True)
            
            if self.guild_config.get('SHOP_EMBED_IMAGE_URL'):
                embed.set_image(url=self.guild_config.get('SHOP_EMBED_IMAGE_URL'))
                
            view = ManageCustomRoleView(bot=self.bot, guild_config=self.guild_config, role_to_edit=role_obj, guild_id=self.guild_id)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class AccountView(View):
    def __init__(self, bot, guild_config, guild_id: int, custom_role: dict = None):
        super().__init__(timeout=120) 
        self.bot = bot
        self.guild_config = guild_config
        self.guild_id = guild_id
        self.message = None 
        
        self.add_item(AccountActionSelect(
            bot=self.bot, 
            guild_config=self.guild_config, 
            guild_id=self.guild_id,
            custom_role_data=custom_role
        ))
    
    async def on_timeout(self):
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class CustomRoleStyleSelect(Select):
    def __init__(self, bot, guild_config, guild_id, is_booster, min_creation_price=None, role_to_edit=None):
        self.bot = bot
        self.guild_config = guild_config
        self.guild_id = guild_id
        self.min_creation_price = min_creation_price
        self.is_booster = is_booster
        self.role_to_edit = role_to_edit

        options = [
            discord.SelectOption(label="Solid", description="Một màu đơn sắc.", emoji="🎨"),
            discord.SelectOption(label="Gradient", description="Chuyển màu giữa 2 màu.", emoji="🌈"),
            discord.SelectOption(label="Holographic", description="Hiệu ứng 7 sắc cầu vồng.", emoji="✨")
        ]
        super().__init__(placeholder="Chọn một kiểu hiển thị cho role...", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_style = self.values[0]
        modal = CustomRoleModal(
            bot=self.bot, 
            guild_id=self.guild_id, 
            guild_config=self.guild_config, 
            style=selected_style,
            min_creation_price=self.min_creation_price,
            is_booster=self.is_booster,
            role_to_edit=self.role_to_edit
        )
        
        await interaction.response.send_modal(modal)
        

        try:
            await interaction.delete_original_response()
        except (discord.NotFound, discord.HTTPException) as e:
            print(f"Non-critical error while deleting original response: {e}")
            pass

class CustomRoleStyleSelectView(View):
    def __init__(self, bot, guild_config, guild_id, is_booster, min_creation_price=None, role_to_edit=None):
        super().__init__(timeout=180)
        self.add_item(CustomRoleStyleSelect(bot, guild_config, guild_id, is_booster, min_creation_price, role_to_edit))

class ShopActionSelect(Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="Danh Sách Role", value="list_roles", description="Xem và mua các role đang được bán.", emoji="<:MenheraFlower:1406458230317645906>"),
            discord.SelectOption(label="Bán Role", value="sell", description="Bán lại role đã mua để nhận lại coin.", emoji="<a:MenheraNod:1406458257349935244>"),
            discord.SelectOption(label="Tạo Role Style (Booster)", value="custom_role_booster", description="Tạo role với style đặc biệt chỉ dành cho Booster.", emoji="<a:boost:1406487216649277510>"),
            discord.SelectOption(label="Tạo Role Thường", value="custom_role_member", description="Tạo một role với tên và màu sắc của riêng bạn.", emoji="<:g_chamhoi:1326543673957027961>")
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

            display_style = guild_config.get('SHOP_DISPLAY_STYLE', 'select_menu')

            if display_style == 'pagination':
                paginated_view = PaginatedRoleListView(self.bot, interaction, guild_config, shop_roles)
                initial_embed = await paginated_view.get_page_embed()
                paginated_view.prev_page.disabled = True
                paginated_view.next_page.disabled = paginated_view.total_pages <= 1
                await interaction.followup.send(embed=initial_embed, view=paginated_view, ephemeral=True)
            else: 
                view = RoleListView(self.bot, guild_config, shop_roles)
                await interaction.followup.send(
                    content="<:MenheraFlower:1406458230317645906> Vui lòng chọn một role từ menu bên dưới để xem thông tin chi tiết.",
                    view=view,
                    ephemeral=True
                )

        elif action == "sell":
            await interaction.response.send_modal(SellModal(bot=self.bot))
            
        elif action == "custom_role_booster":
            await interaction.response.defer(ephemeral=True)
            
            if db.get_custom_role(interaction.user.id, interaction.guild.id):
                msg = messages.get('CUSTOM_ROLE_ALREADY_OWNED', "Bạn đã có một role tùy chỉnh rồi. Hãy dùng nút 'Tài khoản của tôi' để quản lý.")
                return await interaction.followup.send(msg, ephemeral=True)
            
            user_data = db.get_or_create_user(interaction.user.id, interaction.guild.id)
            booster_config = guild_config.get('CUSTOM_ROLE_CONFIG', {})
            min_boosts = booster_config.get('MIN_BOOST_COUNT', 99)
            
            # lay so boost tu db da duoc dong bo
            fake_boosts = user_data.get('fake_boosts', 0)
            real_boosts = user_data.get('real_boosts', 0)
            boost_count = fake_boosts if fake_boosts > 0 else real_boosts

            if boost_count < min_boosts:
                msg = messages.get('CUSTOM_ROLE_NO_BOOSTS', "Bạn cần có ít nhất {min_boosts} boost để dùng tính năng này.").format(min_boosts=min_boosts, boost_count=boost_count)
                return await interaction.followup.send(msg, ephemeral=True)

            creation_price = int(booster_config.get('PRICE', 1000))
            if user_data['balance'] < creation_price:
                msg = messages.get('CUSTOM_ROLE_NO_COIN', "Bạn không đủ coin! Cần {price} coin để tạo role nhưng bạn chỉ có {balance}.").format(price=creation_price, balance=user_data['balance'])
                return await interaction.followup.send(msg, ephemeral=True)

            view = CustomRoleStyleSelectView(bot=self.bot, guild_config=guild_config, guild_id=interaction.guild.id, is_booster=True)
            await interaction.followup.send("✨ Vui lòng chọn style bạn muốn cho role đặc biệt của mình:", view=view, ephemeral=True)

        elif action == "custom_role_member":
            regular_config = guild_config.get('REGULAR_USER_ROLE_CREATION', {})
            if not regular_config.get('ENABLED', False):
                return await interaction.response.send_message("Tính năng tạo role cho thành viên thường đang tắt.", ephemeral=True)

            user_data = db.get_or_create_user(interaction.user.id, interaction.guild.id)
            min_creation_price = int(regular_config.get('CREATION_PRICE', 2000))

            if user_data['balance'] < min_creation_price:
                msg = messages.get('CUSTOM_ROLE_NO_COIN', "Bạn không đủ coin! Cần {price} coin để tạo role nhưng bạn chỉ có {balance}.").format(price=min_creation_price, balance=user_data['balance'])
                return await interaction.response.send_message(msg, ephemeral=True)
            
            modal = CustomRoleModal(bot=self.bot, guild_id=interaction.guild.id, guild_config=guild_config, style="Solid", min_creation_price=min_creation_price, is_booster=False)
            await interaction.response.send_modal(modal)


class ShopView(View):
    def __init__(self, bot): 
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(ShopActionSelect(bot=self.bot))

    @discord.ui.button(label="Tài khoản của tôi / Cách sử dụng", style=discord.ButtonStyle.secondary, custom_id="shop_view:account", emoji="<a:z_cat_yolo:1326542766330740818>")
    async def account_button_callback(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        guild_config = self.bot.guild_configs.get(str(interaction.guild.id))
        if not guild_config:
            return await interaction.followup.send("Lỗi: Không tìm thấy config cho server.", ephemeral=True)
        
        messages = guild_config.get('MESSAGES', {})
        embed_color = discord.Color(int(str(guild_config.get('EMBED_COLOR', '#ff00af')).lstrip('#'), 16))
        
        user_data = db.get_or_create_user(interaction.user.id, interaction.guild.id)

        embed = discord.Embed(
            title=messages.get('ACCOUNT_INFO_TITLE', "Tài khoản"),
            description=messages.get('ACCOUNT_INFO_DESC', ''),
            color=embed_color
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        balance_str = messages.get('BALANCE_FIELD_VALUE', "{balance} coin").format(balance=f"{user_data['balance']:,}")
        embed.add_field(name=f"```{messages.get('BALANCE_FIELD_NAME', 'Số dư')}```", value=balance_str, inline=False)
        
        shop_roles_db = db.get_shop_roles(interaction.guild.id)
        if shop_roles_db:
            shop_role_ids = {r['role_id'] for r in shop_roles_db}
            owned_roles = [f"`{role.name}`" for role in interaction.user.roles if role.id in shop_role_ids]
            
            owned_roles_str = "\n".join(owned_roles) if owned_roles else "Chưa sở hữu role nào."
            embed.add_field(name="<:MenheraFlower:1406458230317645906> Role Shop đã sở hữu", value=owned_roles_str, inline=False)

        currency_cog = self.bot.get_cog("CurrencyHandler")
        if currency_cog:
            multiplier = currency_cog._get_boost_multiplier(interaction.user, guild_config, user_data)
            
            # lay so boost tu db da duoc dong bo
            fake_boosts = user_data.get('fake_boosts', 0)
            real_boosts = user_data.get('real_boosts', 0)
            boost_count = fake_boosts if fake_boosts > 0 else real_boosts

            if multiplier > 1.0:
                embed.add_field(
                    name="<a:zgif_BoosterBadgesRoll:1406487084583358474> Ưu Đãi Booster",
                    value=f"```diff\n+ Bạn đang nhận x{multiplier:.1f} coin từ {boost_count} boost!\n```",
                    inline=False
                )

        if guild_config.get('SHOP_EMBED_IMAGE_URL'):
            embed.set_image(url=guild_config['SHOP_EMBED_IMAGE_URL'])

        footer_text = guild_config.get('FOOTER_MESSAGES', {}).get('ACCOUNT_INFO', '')
        embed.set_footer(text=f"────────────────────\n{footer_text}", icon_url=self.bot.user.avatar.url)
        
        custom_role = db.get_custom_role(interaction.user.id, interaction.guild.id)
        view = AccountView(bot=self.bot, guild_config=guild_config, guild_id=interaction.guild.id, custom_role=custom_role)
        
        try:
            message = await interaction.user.send(embed=embed, view=view)
            view.message = message # luu lai message de edit sau khi timeout
            await interaction.followup.send("✅ Đã gửi thông tin tài khoản vào tin nhắn riêng của bạn!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("<a:c_947079524435247135:1274398161200484446> Tôi không thể gửi tin nhắn riêng cho bạn. Vui lòng bật tin nhắn từ thành viên server.", ephemeral=True)

async def setup(bot):
    pass