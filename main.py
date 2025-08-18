import discord
from discord.ext import commands
import json
import os
import logging
from database import database as db
from cogs.shop_views import ShopView

# logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')

# tai config
try:
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
except FileNotFoundError:
    logging.error("Khong tim thay config.json.")
    exit()

# intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True
intents.guilds = True 

class ShopBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!@#$", intents=intents) 
        self.config = config
        self.persistent_views_added = False

    async def setup_hook(self):
        # tai cogs
        cogs_folder = './cogs'
        for filename in os.listdir(cogs_folder):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logging.info(f"Loaded cog: {filename}")
                except commands.ExtensionAlreadyLoaded:
                    pass
                except Exception as e:
                    logging.error(f"Load cog {filename} that bai: {e}")
        
        # tao thu muc ui
        ui_dir = os.path.join(cogs_folder, 'ui')
        if not os.path.exists(ui_dir):
            os.makedirs(ui_dir)
            
        # them view
        if not self.persistent_views_added:
            self.add_view(ShopView(bot=self))
            self.persistent_views_added = True
            logging.info("Persistent ShopView da them.")
    
    async def on_ready(self):
        logging.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logging.info('------')
        
        for guild_id in self.config['AUTHORIZED_GUILD_IDS']:
            try:
                guild_obj = discord.Object(id=guild_id)
                self.tree.copy_global_to(guild=guild_obj)
                await self.tree.sync(guild=guild_obj)
                logging.info(f"Dong bo lenh cho guild {guild_id}.")
            except Exception as e:
                logging.error(f"Dong bo lenh cho guild {guild_id} that bai: {e}")

    async def on_guild_join(self, guild):
        if guild.id not in self.config['AUTHORIZED_GUILD_IDS']:
            logging.warning(f"Bot bi them vao guild la: {guild.name} ({guild.id}). Roi khoi.")
            
            inviter = guild.owner
            try:
                # tim nguoi moi
                async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
                    if entry.target.id == self.user.id:
                        inviter = entry.user
                        break
            except Exception:
                pass

            try:
                msg = (f"Xin chào, tôi là bot được thiết kế riêng cho các server được chủ sở hữu cho phép. "
                       f"Tôi không được phép hoạt động ở server khác. Tôi sẽ rời khỏi server của bạn. Cảm ơn!")
                await inviter.send(msg)
            except discord.Forbidden:
                logging.warning(f"Khong the DM cho nguoi moi/owner cua {guild.name}.")
            await guild.leave()

# chay bot
if __name__ == "__main__":
    if not config.get('DATABASE_URL'):
        logging.error("DATABASE_URL khong co trong config.json.")
    else:
        db.init_db(config['DATABASE_URL'])
        bot = ShopBot()
        try:
            bot.run(config['BOT_TOKEN'])
        except discord.LoginFailure:
            logging.error("Token bot khong hop le. Kiem tra config.json.")