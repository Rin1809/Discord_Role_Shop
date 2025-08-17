import discord
from discord.ext import commands
import json
import os
import logging
from database import database as db
from cogs.shop_views import ShopView

# --- Cau hinh logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')

# --- Tai cau hinh ---
try:
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
except FileNotFoundError:
    logging.error("Config file not found. Please create a 'config.json'.")
    exit()

# --- Thiet lap Intents ---
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
        # Tai cac cogs
        cogs_folder = './cogs'
        for filename in os.listdir(cogs_folder):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logging.info(f"Loaded cog: {filename}")
                except commands.ExtensionAlreadyLoaded:
                    pass
                except Exception as e:
                    logging.error(f"Failed to load cog {filename}: {e}")
        
        # tao thu muc neu chua co
        ui_dir = os.path.join(cogs_folder, 'ui')
        if not os.path.exists(ui_dir):
            os.makedirs(ui_dir)
            
        # them view
        if not self.persistent_views_added:
            self.add_view(ShopView(bot=self))
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
            
            inviter = None
            try:
                async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
                    if entry.target.id == self.user.id:
                        inviter = entry.user
                        break
            except discord.Forbidden:
                logging.warning(f"Missing 'View Audit Log' permission in {guild.name} to find inviter.")
                inviter = guild.owner 
            except Exception as e:
                logging.error(f"Error fetching audit log in {guild.name}: {e}")
                inviter = guild.owner 

            if not inviter:
                 inviter = guild.owner

            try:
                await inviter.send(
                    f"Xin chào, tôi là bot được thiết kế riêng cho server có ID `{self.config['GUILD_ID']}`."
                    " Tôi không được phép hoạt động ở server khác. Tôi sẽ rời khỏi server của bạn. Cảm ơn!"
                )
            except discord.Forbidden:
                logging.warning(f"Could not send a DM to the inviter/owner of {guild.name}.")
            await guild.leave()


# --- Khoi tao va chay bot ---
if __name__ == "__main__":
    db.init_db()
    
    bot = ShopBot()
    
    try:
        bot.run(config['BOT_TOKEN'])
    except discord.LoginFailure:
        logging.error("Invalid bot token provided. Please check your 'config.json'.")