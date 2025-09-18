import discord
from discord.ext import commands
import json
import os
import logging
import threading
import asyncio
import socketio
from database import database as db
from cogs.shop_views import ShopView

# logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')

# tai config toan cuc
try:
    with open('config.json', 'r', encoding='utf-8') as f:
        global_config = json.load(f)
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
        self.global_config = global_config
        self.guild_configs = {} # cache config
        self.persistent_views_added = False
        
    async def reload_guild_config(self, guild_id: int):
        # ham nay an toan de goi tu thread khac
        logging.info(f"Reloading config cho guild {guild_id}...")
        try:
            guild_id_int = int(guild_id)
            config = db.get_guild_config(guild_id_int)
            if config:
                self.guild_configs[str(guild_id_int)] = config
                logging.info(f"Config cho guild {guild_id_int} da duoc reload.")
                return True
            logging.warning(f"Khong tim thay config cho guild {guild_id_int} de reload.")
            return False
        except Exception as e:
            logging.error(f"Loi khi reload config cho guild {guild_id}: {e}")
            return False

    def setup_socketio_listener(self):
        sio = socketio.Client()

        @sio.event
        def connect():
            logging.info("Da ket noi toi server dashboard qua SocketIO!")

        @sio.event
        def disconnect():
            logging.info("Da ngat ket noi voi server dashboard!")

        @sio.on('config_updated')
        def on_config_updated(data):
            guild_id = data.get('guild_id')
            if guild_id:
                logging.info(f"Nhan duoc tin hieu reload config cho guild: {guild_id}")
                asyncio.run_coroutine_threadsafe(self.reload_guild_config(guild_id), self.loop)
        
        try:
            sio.connect('http://127.0.0.1:5001')
            sio.wait()
        except socketio.exceptions.ConnectionError as e:
            logging.error(f"Khong the ket noi den dashboard SocketIO: {e}. Bot van hoat dong nhung se khong tu dong reload config.")
        except Exception as e:
            logging.error(f"Loi SocketIO client: {e}")

    async def setup_hook(self):
        # tai config tu db
        self.guild_configs = db.get_all_guild_configs()
        logging.info(f"Loaded {len(self.guild_configs)} guild configurations from database.")
        
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

        # khoi chay socketio listener
        socket_thread = threading.Thread(target=self.setup_socketio_listener, daemon=True)
        socket_thread.start()
    
    async def on_ready(self):
        logging.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logging.info('------')
        
        for guild_id in self.global_config['AUTHORIZED_GUILD_IDS']:
            try:
                guild_obj = discord.Object(id=guild_id)
                self.tree.copy_global_to(guild=guild_obj)
                await self.tree.sync(guild=guild_obj)
                logging.info(f"Dong bo lenh cho guild {guild_id}.")
            except Exception as e:
                logging.error(f"Dong bo lenh cho guild {guild_id} that bai: {e}")

    async def on_guild_join(self, guild):
        if guild.id not in self.global_config['AUTHORIZED_GUILD_IDS']:
            logging.warning(f"Bot bi them vao guild la: {guild.name} ({guild.id}). Roi khoi.")
            
            inviter = guild.owner
            try:
                async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
                    if entry.target.id == self.user.id:
                        inviter = entry.user
                        break
            except Exception:
                pass

            try:
                msg = (f"Xin chào, tớ là bot được thiết kế riêng cho các server Rin cho phép. "
                       f"Tớ không được phép hoạt động ở server khác. Tớ sẽ rời khỏi server của câu. Cảm ơn!")
                await inviter.send(msg)
            except discord.Forbidden:
                logging.warning(f"Khong the DM cho nguoi moi/owner cua {guild.name}.")
            await guild.leave()

# chay bot
if __name__ == "__main__":
    db_url = global_config.get('DATABASE_URL')
    if not db_url:
        logging.error("DATABASE_URL khong co trong config.json.")
    else:
        db.init_db(db_url)
        bot = ShopBot()
        try:
            bot.run(global_config.get('BOT_TOKEN'))
        except discord.LoginFailure:
            logging.error("Token bot khong hop le. Kiem tra config.json.")