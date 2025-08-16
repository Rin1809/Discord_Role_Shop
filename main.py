# main.py
import discord
from discord.ext import commands # THAY ĐỔI: Import commands
import json
import os
import logging
from database import database as db

# --- Cấu hình logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')

# --- Tải cấu hình ---
try:
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
except FileNotFoundError:
    logging.error("Config file not found. Please create a 'config.json'.")
    exit()

# --- Thiết lập Intents ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

class ShopBot(commands.Bot):
    def __init__(self):
        # command_prefix là bắt buộc, nhưng không dùng nên có thể đặt bất kỳ
        super().__init__(command_prefix="!@#$", intents=intents) 
        self.config = config
        self.persistent_views_added = False

    async def setup_hook(self):
        # Tải cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logging.info(f"Loaded cog: {filename}")
                except Exception as e:
                    logging.error(f"Failed to load cog {filename}: {e}")

        # Thêm View vào bot để nó tồn tại sau khi khởi động lại
        if not self.persistent_views_added:
            shop_cog = self.get_cog("ShopInterface")
            if shop_cog:
                self.add_view(shop_cog.ShopView(bot=self))
                self.persistent_views_added = True
                logging.info("Persistent ShopView added.")
    
    async def on_ready(self):
        logging.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logging.info('------')
        
        guild_obj = discord.Object(id=self.config['GUILD_ID'])
        self.tree.copy_global_to(guild=guild_obj)
        await self.tree.sync(guild=guild_obj)
        logging.info(f"Synced commands for guild {self.config['GUILD_ID']}.")


    async def on_guild_join(self, guild):
        if guild.id != self.config['GUILD_ID']:
            logging.warning(f"Bot was added to an unauthorized guild: {guild.name} ({guild.id}). Leaving.")
            try:
                await guild.owner.send(
                    f"Xin chào, tôi là bot được thiết kế riêng cho server có ID `{self.config['GUILD_ID']}`."
                    " Tôi không được phép hoạt động ở server khác. Tôi sẽ rời khỏi server của bạn. Cảm ơn!"
                )
            except discord.Forbidden:
                logging.warning(f"Could not send a DM to the owner of {guild.name}.")
            await guild.leave()


# --- Khởi tạo và chạy bot ---
if __name__ == "__main__":
    db.init_db()
    
    bot = ShopBot()
    
    try:
        bot.run(config['BOT_TOKEN'])
    except discord.LoginFailure:
        logging.error("Invalid bot token provided. Please check your 'config.json'.")