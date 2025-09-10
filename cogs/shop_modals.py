import discord
from discord.ui import Modal, TextInput
from database import database as db
import re
import asyncio
import logging

def is_valid_hex_color(s):
    return re.match(r'^#?([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$', s) is not None

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
    def __init__(self, bot, guild_id: int, guild_config, style: str, is_booster: bool, creation_price=None, role_to_edit: discord.Role = None):
        super().__init__(title=f"Tạo / Sửa Role: {style}")
        self.bot = bot
        self.guild_id = guild_id
        self.guild_config = guild_config
        self.style = style
        self.is_booster = is_booster
        self.creation_price = creation_price # chi dung khi tao moi
        self.role_to_edit = role_to_edit
        self.embed_color = discord.Color(int(str(guild_config.get('EMBED_COLOR', '#ff00af')).lstrip('#'), 16))

        self.add_item(TextInput(
            label="Tên role bạn muốn",
            placeholder="Ví dụ: Đại Gia Server",
            custom_id="custom_role_name",
            default=role_to_edit.name if role_to_edit else None
        ))
        
        # booster moi co style
        if self.is_booster:
            if self.style == "Gradient":
                self.add_item(TextInput(label="Màu 1 (HEX, vd: #ff00af)", custom_id="custom_role_color1", default="#ffaaaa"))
                self.add_item(TextInput(label="Màu 2 (HEX, vd: #5865F2)", custom_id="custom_role_color2", default="#89b4fa"))
            else: # Solid hoac Holographic
                self.add_item(TextInput(
                    label="Mã màu HEX (ví dụ: #ff00af)",
                    custom_id="custom_role_color",
                    default=str(role_to_edit.color) if role_to_edit and self.style == "Solid" else "#ff00af"
                ))
        else: # user thuong auto la Solid
             self.add_item(TextInput(
                label="Mã màu HEX (ví dụ: #ff00af)",
                custom_id="custom_role_color",
                default=str(role_to_edit.color) if role_to_edit else "#ffaaaa"
            ))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        role_name = self.children[0].value
        color1_str, color2_str = None, None
        
        # lay mau
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

        color_int = int(role_color_str.lstrip('#'), 16)
        new_color = discord.Color(color_int)

        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return await interaction.followup.send("Lỗi nghiêm trọng: Không tìm thấy server.", ephemeral=True)

        user_data = db.get_or_create_user(interaction.user.id, guild.id)

        # th: sua role (chi booster)
        if self.role_to_edit:
            try:
                await self.role_to_edit.edit(name=role_name, color=new_color, reason=f"User edit request")
                db.add_or_update_custom_role(interaction.user.id, guild.id, self.role_to_edit.id, role_name, role_color_str, self.style, color1_str, color2_str)
                
                await self.notify_admin(interaction, "sửa")
                await interaction.followup.send(f"✅ Đã gửi yêu cầu chỉnh sửa role **{role_name}** đến admin. Vui lòng chờ.", ephemeral=True)

            except discord.Forbidden:
                await interaction.followup.send("❌ Tôi không có quyền để chỉnh sửa role này.", ephemeral=True)
            return

        # th: tao role moi
        if user_data['balance'] < self.creation_price:
            return await interaction.followup.send(f"Bạn không đủ coin! Cần **{self.creation_price} coin** nhưng bạn chỉ có **{user_data['balance']}**.", ephemeral=True)

        new_balance = user_data['balance'] - self.creation_price

        try:
            member = guild.get_member(interaction.user.id)
            new_role = await guild.create_role(
                name=role_name, color=new_color, reason=f"Custom role for {interaction.user.name}"
            )
            
            db.update_user_data(interaction.user.id, guild.id, balance=new_balance)
            
            # them vao shop cong khai
            purchase_price = self.guild_config.get('CUSTOM_ROLE_CONFIG', {}).get('DEFAULT_PURCHASE_PRICE', 500)
            db.add_role_to_shop(new_role.id, guild.id, purchase_price)

            db.log_transaction(
                guild_id=guild.id, user_id=interaction.user.id,
                transaction_type='create_custom_role', item_name=role_name,
                amount_changed=-self.creation_price, new_balance=new_balance
            )

            # xu ly rieng cho booster
            if self.is_booster:
                for attempt in range(3):
                    try:
                        bot_member = guild.me
                        if bot_member and bot_member.top_role and bot_member.top_role.position > 1:
                            target_position = bot_member.top_role.position - 1
                            await new_role.edit(position=target_position, reason="Dua role len cao")
                            break
                    except Exception:
                        if attempt < 2: await asyncio.sleep(1)
                        else: break
                
                # them vao bang rieng cua booster
                db.add_or_update_custom_role(interaction.user.id, guild.id, new_role.id, role_name, role_color_str, self.style, color1_str, color2_str)
                await self.notify_admin(interaction, "tạo mới")
                await interaction.followup.send("✅ Yêu cầu của bạn đã được gửi đến admin để thiết lập style. Role cơ bản đã được tạo và gán.", ephemeral=True)
            else:
                # user thuong
                await interaction.followup.send(f"✅ Bạn đã tạo thành công role **{role_name}**! Role này giờ cũng có sẵn trong shop cho người khác mua.", ephemeral=True)

            await member.add_roles(new_role)

        except discord.Forbidden:
            await interaction.followup.send("❌ Đã xảy ra lỗi! Tôi không có quyền tạo hoặc gán role. Giao dịch đã bị hủy.", ephemeral=True)
        except Exception as e:
            logging.error(f"Loi khong mong muon: {e}")
            await interaction.followup.send(f"Đã xảy ra lỗi không mong muốn, vui lòng liên hệ admin.", ephemeral=True)

    async def notify_admin(self, interaction: discord.Interaction, action_type: str):
        admin_channel_id = self.guild_config.get('ADMIN_LOG_CHANNEL_ID')
        if not admin_channel_id:
            logging.warning(f"ADMIN_LOG_CHANNEL_ID not set for guild {self.guild_id}")
            return

        channel = self.bot.get_channel(int(admin_channel_id))
        if not channel:
            logging.warning(f"Cannot find admin channel {admin_channel_id}")
            return

        role_name = self.children[0].value
        embed = discord.Embed(
            title="Yêu Cầu Chỉnh Sửa Role Style",
            description=f"Thành viên {interaction.user.mention} vừa **{action_type}** một role tùy chỉnh và yêu cầu set style.",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Tên Role", value=f"```{role_name}```", inline=False)
        embed.add_field(name="Style Yêu Cầu", value=f"```{self.style}```", inline=True)

        if self.style == "Gradient":
            color1 = self.children[1].value
            color2 = self.children[2].value
            embed.add_field(name="Màu 1", value=f"```{color1}```", inline=True)
            embed.add_field(name="Màu 2", value=f"```{color2}```", inline=True)
        else:
            color = self.children[1].value
            embed.add_field(name="Màu Sắc", value=f"```{color}```", inline=True)

        embed.set_footer(text="Vui lòng chỉnh sửa thủ công cho thành viên.")

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logging.error(f"Cannot send message to admin channel {admin_channel_id}")


async def setup(bot):
    pass