import discord
from discord.ui import Modal, TextInput, View, Select, Button
from database import database as db
import re
import asyncio
import logging
import math

# ktra hex
def is_valid_hex_color(s):
    return re.match(r'^#?([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$', s) is not None

# emoji select menu
class EmojiSelect(Select):
    def __init__(self, emojis, page=0):
        start_index = page * 25
        end_index = start_index + 25
        current_emojis = emojis[start_index:end_index]

        options = [
            discord.SelectOption(
                label=emoji.name,
                value=str(emoji.id),
                emoji=emoji
            ) for emoji in current_emojis
        ] if current_emojis else [discord.SelectOption(label="Không có emoji", value="none")]

        super().__init__(placeholder=f"Trang {page + 1} - Chọn một emoji...", options=options, disabled=not current_emojis)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.defer()
            return
        await self.view.creation_view._finalize_role_creation(interaction, icon_id=self.values[0])

# view phan trang emoji
class EmojiPageView(View):
    def __init__(self, emojis, creation_view):
        super().__init__(timeout=180)
        self.emojis = emojis
        self.creation_view = creation_view
        self.current_page = 0
        self.total_pages = math.ceil(len(self.emojis) / 25)
        self.update_view()

    def update_view(self):
        self.clear_items()
        self.add_item(EmojiSelect(self.emojis, self.current_page))
        if self.total_pages > 1:
            prev_button = Button(label="Trước", style=discord.ButtonStyle.secondary, emoji="⬅️", disabled=self.current_page == 0)
            prev_button.callback = self.prev_page
            
            next_button = Button(label="Sau", style=discord.ButtonStyle.secondary, emoji="➡️", disabled=self.current_page >= self.total_pages - 1)
            next_button.callback = self.next_page

            self.add_item(prev_button)
            self.add_item(next_button)

    async def prev_page(self, interaction: discord.Interaction):
        self.current_page -= 1
        self.update_view()
        await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        self.current_page += 1
        self.update_view()
        await interaction.response.edit_message(view=self)


# menu chon kieu icon
class IconActionSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Chọn Emoji từ Server", value="select_emoji", emoji="😀"),
            discord.SelectOption(label="Tải Ảnh Lên (Qua Thread)", value="upload_image", emoji="🖼️"),
            discord.SelectOption(label="Tiếp Tục (Không có Icon)", value="no_icon", emoji="✅"),
            discord.SelectOption(label="Hủy Bỏ", value="cancel", emoji="✖️"),
        ]
        super().__init__(placeholder="Chọn một tùy chọn cho icon...", options=options)

    async def callback(self, interaction: discord.Interaction):
        action = self.values[0]
        
        if action == "select_emoji":
            sorted_emojis = sorted(interaction.guild.emojis, key=lambda e: not e.animated)
            if not sorted_emojis:
                await interaction.response.send_message("Server này không có emoji nào.", ephemeral=True)
                return
            
            page_view = EmojiPageView(emojis=sorted_emojis, creation_view=self.view)
            await interaction.response.edit_message(content="Vui lòng chọn một emoji:", view=page_view)

        elif action == "upload_image":
            await interaction.response.edit_message(content="<a:loading:1274398154694467614> Đang tạo thread riêng tư cho bạn...", view=None)
            
            try:
                thread = await interaction.channel.create_thread(
                    name=f"Tải ảnh icon cho {interaction.user.display_name}",
                    type=discord.ChannelType.private_thread,
                    auto_archive_duration=60
                )
                await thread.add_user(interaction.user)
            except Exception as e:
                logging.error(f"Loi tao thread: {e}")
                await interaction.edit_original_response(content=f"❌ Không thể tạo thread riêng. Vui lòng thử lại hoặc liên hệ admin. Lỗi: `{e}`")
                return

            try:
                gif1 = discord.File("asset/drag_and_drop_example.gif", filename="drag_and_drop_example.gif")
                gif2 = discord.File("asset/upload_example.gif", filename="upload_example.gif")
                
                await thread.send(
                    content=(
                        f"Chào {interaction.user.mention}! Vui lòng tải lên ảnh bạn muốn dùng làm icon cho role.\n"
                        f"**Yêu cầu:**\n"
                        f"- Ảnh phải dưới `256KB`.\n"
                        f"- Bạn có `2 phút` để gửi ảnh.\n\n"
                        f"Bạn có thể kéo-thả hoặc dùng nút `+` để tải ảnh lên như ví dụ sau:"
                    ),
                    files=[gif1, gif2]
                )
                await interaction.edit_original_response(content=f"✅ Đã tạo một thread riêng tư. Vui lòng vào {thread.mention} để tải ảnh lên.")
            except FileNotFoundError:
                 await thread.send(
                    content=(
                        f"Chào {interaction.user.mention}! Vui lòng tải lên ảnh bạn muốn dùng làm icon cho role.\n"
                        f"**Yêu cầu:**\n"
                        f"- Ảnh phải dưới `256KB`.\n"
                        f"- Bạn có `2 phút` để gửi ảnh."
                    )
                )
                 await interaction.edit_original_response(content=f"✅ Đã tạo một thread riêng tư. Vui lòng vào {thread.mention} để tải ảnh lên.")
            
            def check(m):
                return m.author.id == interaction.user.id and m.channel.id == thread.id and m.attachments
            
            try:
                msg = await self.view.bot.wait_for('message', check=check, timeout=120.0)
                attachment = msg.attachments[0]

                if attachment.size > 256 * 1024:
                    await thread.send("❌ Ảnh quá lớn (phải dưới 256KB). Vui lòng thử lại thao tác tạo role.")
                    await thread.edit(archived=True, locked=True)
                    return
                
                icon_bytes = await attachment.read()
                await self.view._finalize_role_creation(interaction, icon=icon_bytes, thread=thread)

            except asyncio.TimeoutError:
                await thread.send("⏰ Hết thời gian. Thread này sẽ được khóa.")
                await thread.edit(archived=True, locked=True)
        
        elif action == "no_icon":
            await self.view._finalize_role_creation(interaction, icon=None)

        elif action == "cancel":
            await interaction.response.edit_message(content="Đã hủy thao tác.", view=None)

class RoleCreationProcessView(View):
    def __init__(self, bot, guild_config, role_name, color_int, style, color1_str, color2_str, creation_price, is_booster, role_to_edit):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_config = guild_config
        self.role_name = role_name
        self.color_int = color_int
        self.style = style
        self.color1_str = color1_str
        self.color2_str = color2_str
        self.creation_price = creation_price
        self.is_booster = is_booster
        self.role_to_edit = role_to_edit
        self.embed_color = discord.Color(int(str(guild_config.get('EMBED_COLOR', '#ff00af')).lstrip('#'), 16))
        self.add_item(IconActionSelect())

    async def _finalize_role_creation(self, interaction: discord.Interaction, icon=None, icon_id=None, thread: discord.Thread = None):
        if thread:
            await thread.send("<a:loading:1274398154694467614> Đang xử lý, vui lòng chờ...")
        else:
            await interaction.response.edit_message(content="<a:loading:1274398154694467614> Đang xử lý...", view=None)

        final_icon_data = icon
        guild = interaction.guild
        new_role = None

        if icon_id:
            emoji_obj = guild.get_emoji(int(icon_id))
            if emoji_obj:
                try:
                    final_icon_data = await emoji_obj.read()
                except Exception as e:
                    logging.error(f"Khong the tai anh emoji {emoji_obj.id}: {e}")
                    msg_content = "❌ Lỗi: Không thể tải được dữ liệu của emoji này. Vui lòng thử lại."
                    if thread: await thread.send(msg_content)
                    else: await interaction.edit_original_response(content=msg_content, view=None)
                    return
            else:
                msg_content = "❌ Lỗi: Không thể tìm thấy emoji này trên server. Vui lòng thử lại."
                if thread: await thread.send(msg_content)
                else: await interaction.edit_original_response(content=msg_content, view=None)
                return

        new_color = discord.Color(self.color_int)

        try:
            if self.role_to_edit:
                await self.role_to_edit.edit(name=self.role_name, color=new_color, display_icon=final_icon_data, reason=f"User edit request")
                db.add_or_update_custom_role(interaction.user.id, guild.id, self.role_to_edit.id, self.role_name, f"#{self.color_int:06x}", self.style, self.color1_str, self.color2_str)
                await self.notify_admin(interaction, "sửa")
                
                msg_content = f"✅ Đã gửi yêu cầu chỉnh sửa role **{self.role_name}** đến admin. Vui lòng chờ."
                if thread:
                    await thread.send(msg_content)
                    await thread.edit(archived=True, locked=True)
                else: await interaction.edit_original_response(content=msg_content, view=None)
                return
            
            # buoc 1: thuc hien tren discord
            new_role = await guild.create_role(
                name=self.role_name, color=new_color, display_icon=final_icon_data, reason=f"Custom role for {interaction.user.name}"
            )
            await interaction.user.add_roles(new_role)

            if self.is_booster:
                try:
                    target_position = guild.me.top_role.position - 1
                    await new_role.edit(position=target_position)
                except Exception: pass
            
            # buoc 2: neu thanh cong, cap nhat database
            user_data = db.get_or_create_user(interaction.user.id, guild.id)
            new_balance = user_data['balance'] - self.creation_price
            db.update_user_data(interaction.user.id, guild.id, balance=new_balance)
            db.log_transaction(guild.id, interaction.user.id, 'create_custom_role', self.role_name, -self.creation_price, new_balance)

            if self.is_booster:
                db.add_or_update_custom_role(interaction.user.id, guild.id, new_role.id, self.role_name, f"#{self.color_int:06x}", self.style, self.color1_str, self.color2_str)
                await self.notify_admin(interaction, "tạo mới")
                msg_content = "✅ Yêu cầu của bạn đã được gửi đến admin để thiết lập style. Role cơ bản đã được tạo và gán."
            else:
                regular_config = self.guild_config.get('REGULAR_USER_ROLE_CREATION', {})
                multiplier = regular_config.get('SHOP_PRICE_MULTIPLIER', 1.2)
                shop_price = int(self.creation_price * multiplier)
                db.add_role_to_shop(new_role.id, guild.id, shop_price, creator_id=interaction.user.id, creation_price=self.creation_price)
                msg_content = f"✅ Bạn đã tạo thành công role **{self.role_name}**! Role này giờ cũng có sẵn trong shop."

            if thread:
                await thread.send(msg_content)
                await thread.edit(archived=True, locked=True)
            else: await interaction.edit_original_response(content=msg_content, view=None)

        except (discord.Forbidden, discord.HTTPException) as e:
            # hoan tac neu da tao role
            if new_role:
                await new_role.delete(reason="Giao dich that bai, hoan tac")
            
            error_msg = "❌ Lỗi quyền! Tôi không thể tạo/sửa/gán role. Giao dịch đã được hủy bỏ và không trừ tiền."
            if isinstance(e, discord.HTTPException):
                logging.error(f"Loi HTTP khi tao role: {e.status} - {e.text}")
                error_msg = f"❌ Đã xảy ra lỗi từ Discord. Giao dịch đã được hủy bỏ. (Chi tiết: {e.text})"

            if thread: 
                await thread.send(error_msg)
                await thread.edit(archived=True, locked=True)
            else: await interaction.edit_original_response(content=error_msg, view=None)
        except Exception as e:
            if new_role:
                await new_role.delete(reason="Giao dich that bai, hoan tac")
            logging.error(f"Loi khong mong muon: {e}")
            msg_content = f"Lỗi không mong muốn, vui lòng liên hệ admin. Giao dịch đã hủy."
            if thread:
                await thread.send(msg_content)
                await thread.edit(archived=True, locked=True)
            else: await interaction.edit_original_response(content=msg_content, view=None)


    async def notify_admin(self, interaction: discord.Interaction, action_type: str):
        admin_channel_id = self.guild_config.get('ADMIN_LOG_CHANNEL_ID')
        if not admin_channel_id: return

        channel = self.bot.get_channel(int(admin_channel_id))
        if not channel: return
        
        ping_content = " ".join([f"<@&{rid}>" for rid in self.guild_config.get('CUSTOM_ROLE_PING_ROLES', [])])

        embed = discord.Embed(
            title="Yêu Cầu Chỉnh Sửa Role Style",
            description=f"Member {interaction.user.mention} vừa **{action_type}** một role tùy chỉnh và yêu cầu set style.",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Tên Role", value=f"```{self.role_name}```", inline=False)
        embed.add_field(name="Style Yêu Cầu", value=f"```{self.style}```", inline=True)

        if self.style == "Gradient":
            embed.add_field(name="Màu 1", value=f"```{self.color1_str}```", inline=True)
            embed.add_field(name="Màu 2", value=f"```{self.color2_str}```", inline=True)
        else:
            embed.add_field(name="Màu Sắc", value=f"```#{self.color_int:06x}```", inline=True)

        embed.set_footer(text="Admin check giup.")
        await channel.send(content=ping_content, embed=embed)

class PurchaseModal(Modal, title="Mua Role"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.add_item(TextInput(
            label="Số thứ tự của role",
            placeholder="Nhập số tương ứng với role bạn muốn mua...",
            custom_id="purchase_role_id_input"
        ))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        guild_config = self.bot.guild_configs.get(str(interaction.guild.id))
        if not guild_config:
            return await interaction.followup.send("Lỗi: Không tìm thấy config cho server này.", ephemeral=True)

        embed_color = discord.Color(int(str(guild_config.get('EMBED_COLOR', '#ff00af')).lstrip('#'), 16))

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

            db.log_transaction(
                guild_id=interaction.guild.id, user_id=interaction.user.id,
                transaction_type='buy_role', item_name=role_obj.name,
                amount_changed=-price, new_balance=new_balance
            )
        except discord.Forbidden:
            return await interaction.followup.send("❌ Đã xảy ra lỗi! Tôi không có quyền để gán role này cho bạn. Giao dịch đã bị hủy.", ephemeral=True)

        receipt_embed = discord.Embed(
            title="Biên Lai Giao Dịch Mua Hàng",
            description="Giao dịch của bạn đã được xử lý thành công.",
            color=embed_color,
            timestamp=discord.utils.utcnow()
        )
        receipt_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        if interaction.guild.icon:
            receipt_embed.set_thumbnail(url=interaction.guild.icon.url)

        receipt_embed.add_field(name="Loại Giao Dịch", value="```Mua Role```", inline=False)
        receipt_embed.add_field(name="Sản Phẩm", value=f"```{role_obj.name}```", inline=True)
        receipt_embed.add_field(name="Chi Phí", value=f"```- {price} coin```", inline=True)
        receipt_embed.add_field(name="Số Dư Mới", value=f"```{new_balance} coin```", inline=True)

        if guild_config.get('SHOP_EMBED_IMAGE_URL'):
            receipt_embed.set_image(url=guild_config.get('SHOP_EMBED_IMAGE_URL'))

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
        self.add_item(TextInput(
            label="Số thứ tự của role muốn bán",
            placeholder="Nhập số tương ứng với role bạn muốn bán...",
            custom_id="sell_role_id_input"
        ))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        guild_config = self.bot.guild_configs.get(str(interaction.guild.id))
        if not guild_config:
            return await interaction.followup.send("Lỗi: Không tìm thấy config cho server ini.", ephemeral=True)

        embed_color = discord.Color(int(str(guild_config.get('EMBED_COLOR', '#ff00af')).lstrip('#'), 16))

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

        refund_percentage = guild_config.get('SELL_REFUND_PERCENTAGE', 0.65)
        refund_amount = int(price * refund_percentage)
        new_balance = user_data['balance'] + refund_amount

        try:
            await interaction.user.remove_roles(role_obj, reason="Bán lại cho shop")
            db.update_user_data(interaction.user.id, interaction.guild.id, balance=new_balance)

            db.log_transaction(
                guild_id=interaction.guild.id, user_id=interaction.user.id,
                transaction_type='sell_role', item_name=role_obj.name,
                amount_changed=refund_amount, new_balance=new_balance
            )
        except discord.Forbidden:
            return await interaction.followup.send("❌ Đã xảy ra lỗi! Tôi không có quyền để xóa role này khỏi bạn. Giao dịch đã bị hủy.", ephemeral=True)

        receipt_embed = discord.Embed(
            title="Biên Lai Giao Dịch Bán Hàng",
            description="Giao dịch của bạn đã được xử lý thành công.",
            color=embed_color,
            timestamp=discord.utils.utcnow()
        )
        receipt_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        if interaction.guild.icon:
            receipt_embed.set_thumbnail(url=interaction.guild.icon.url)

        receipt_embed.add_field(name="Loại Giao Dịch", value="```Bán Role```", inline=False)
        receipt_embed.add_field(name="Sản Phẩm", value=f"```{role_obj.name}```", inline=True)
        receipt_embed.add_field(name="Tiền Nhận Lại", value=f"```+ {refund_amount} coin```", inline=True)
        receipt_embed.add_field(name="Số Dư Mới", value=f"```{new_balance} coin```", inline=True)

        if guild_config.get('SHOP_EMBED_IMAGE_URL'):
            receipt_embed.set_image(url=guild_config.get('SHOP_EMBED_IMAGE_URL'))

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
    def __init__(self, bot, guild_id: int, guild_config, style: str, is_booster: bool, min_creation_price=None, role_to_edit: discord.Role = None):
        super().__init__(title=f"Tạo / Sửa Role: {style if is_booster else 'Thường'}")
        self.bot = bot
        self.guild_id = guild_id
        self.guild_config = guild_config
        self.style = style
        self.is_booster = is_booster
        self.min_creation_price = min_creation_price
        self.role_to_edit = role_to_edit

        self.add_item(TextInput(
            label="Tên role bạn muốn",
            placeholder="Ví dụ: Đại Gia Server",
            custom_id="custom_role_name",
            default=role_to_edit.name if role_to_edit else None
        ))
        
        if self.is_booster:
            if self.style == "Gradient":
                self.add_item(TextInput(label="Màu 1 (HEX, vd: #ff00af)", custom_id="custom_role_color1", default="#ffaaaa"))
                self.add_item(TextInput(label="Màu 2 (HEX, vd: #5865F2)", custom_id="custom_role_color2", default="#89b4fa"))
            else: 
                self.add_item(TextInput(
                    label="Mã màu HEX (ví dụ: #ff00af)",
                    custom_id="custom_role_color",
                    default=str(role_to_edit.color) if role_to_edit and self.style == "Solid" else "#ff00af"
                ))
        else:
            self.add_item(TextInput(
                label="Mã màu HEX (ví dụ: #ff00af)",
                custom_id="custom_role_color",
                default=str(role_to_edit.color) if role_to_edit else "#ffaaaa"
            ))
            self.add_item(TextInput(
                label=f"Giá bạn trả (tối thiểu {min_creation_price:,} coin)",
                placeholder="Giá càng cao, role trong shop càng đắt...",
                custom_id="creation_bid"
            ))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        role_name = self.children[0].value
        color1_str, color2_str, bid_str = None, None, None
        
        if self.is_booster and self.style == "Gradient":
            color1_str = self.children[1].value
            color2_str = self.children[2].value
            if not is_valid_hex_color(color1_str) or not is_valid_hex_color(color2_str):
                return await interaction.followup.send("Mã màu HEX không hợp lệ.", ephemeral=True)
            role_color_str = color1_str
        else:
            role_color_str = self.children[1].value
            if not is_valid_hex_color(role_color_str):
                return await interaction.followup.send("Mã màu HEX không hợp lệ.", ephemeral=True)
        
        if not self.is_booster:
            bid_str = self.children[2].value

        color_int = int(role_color_str.lstrip('#'), 16)
        
        user_data = db.get_or_create_user(interaction.user.id, self.guild_id)

        creation_price = 0
        if self.is_booster:
            creation_price = self.guild_config.get('CUSTOM_ROLE_CONFIG', {}).get('PRICE', 1000)
        else:
            try:
                creation_price = int(bid_str)
                if creation_price < self.min_creation_price:
                    return await interaction.followup.send(f"Giá bạn trả phải ít nhất là **{self.min_creation_price:,} coin**.", ephemeral=True)
            except (ValueError, TypeError):
                return await interaction.followup.send("Vui lòng nhập một số hợp lệ cho giá tiền.", ephemeral=True)

        if not self.role_to_edit and user_data['balance'] < creation_price:
            return await interaction.followup.send(f"Bạn không đủ coin! Cần **{creation_price:,} coin** nhưng bạn chỉ có **{user_data['balance']:,}**.", ephemeral=True)

        view = RoleCreationProcessView(
            bot=self.bot,
            guild_config=self.guild_config,
            role_name=role_name,
            color_int=color_int,
            style=self.style,
            color1_str=color1_str,
            color2_str=color2_str,
            creation_price=creation_price,
            is_booster=self.is_booster,
            role_to_edit=self.role_to_edit
        )
        
        await interaction.followup.send(
            "<:MenheraFlower:1406458230317645906> **Bước cuối: Thêm Icon cho Role (Tùy chọn)**\nSử dụng menu bên dưới để thêm icon hoặc tạo role ngay.",
            view=view,
            ephemeral=True
        )

async def setup(bot):
    pass
