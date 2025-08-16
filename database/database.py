# database/database.py
import sqlite3
import logging

DB_PATH = './database/shop.db'

def init_db():
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        
        # Bảng users
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                balance INTEGER DEFAULT 0,
                message_count INTEGER DEFAULT 0,
                reaction_count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')

        # Bảng shop_roles
        cur.execute('''
            CREATE TABLE IF NOT EXISTS shop_roles (
                role_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                price INTEGER NOT NULL
            )
        ''')
        
        con.commit()
        con.close()
        logging.info("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")

def execute_query(query, params=(), fetch=None):
    try:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(query, params)
        
        if fetch == 'one':
            result = cur.fetchone()
        elif fetch == 'all':
            result = cur.fetchall()
        else:
            result = None
        
        con.commit()
        con.close()
        return result
    except Exception as e:
        logging.error(f"Database query failed: {e}")
        return None

# --- User Functions ---
def get_or_create_user(user_id, guild_id):
    user = execute_query("SELECT * FROM users WHERE user_id = ? AND guild_id = ?", (user_id, guild_id), fetch='one')
    if not user:
        execute_query("INSERT INTO users (user_id, guild_id) VALUES (?, ?)", (user_id, guild_id))
        user = execute_query("SELECT * FROM users WHERE user_id = ? AND guild_id = ?", (user_id, guild_id), fetch='one')
    return user

def update_user_data(user_id, guild_id, **kwargs):
    fields = ', '.join([f'{key} = ?' for key in kwargs])
    values = list(kwargs.values())
    values.extend([user_id, guild_id])
    query = f"UPDATE users SET {fields} WHERE user_id = ? AND guild_id = ?"
    execute_query(query, tuple(values))

# --- Shop Role Functions ---
def add_role_to_shop(role_id, guild_id, price):
    execute_query("INSERT OR REPLACE INTO shop_roles (role_id, guild_id, price) VALUES (?, ?, ?)", (role_id, guild_id, price))

def remove_role_from_shop(role_id, guild_id):
    execute_query("DELETE FROM shop_roles WHERE role_id = ? AND guild_id = ?", (role_id, guild_id))

def get_shop_roles(guild_id):
    return execute_query("SELECT * FROM shop_roles WHERE guild_id = ? ORDER BY price ASC", (guild_id,), fetch='all')