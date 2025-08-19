import psycopg2
from psycopg2 import pool
from psycopg2.extras import Json, RealDictCursor
import logging
import json
from contextlib import contextmanager

db_pool = None

@contextmanager
def get_db_connection():
    # lay ket noi tu pool
    if db_pool is None:
        raise Exception("Database pool khong duoc khoi tao.")
    conn = None
    try:
        conn = db_pool.getconn()
        yield conn
    finally:
        if conn:
            db_pool.putconn(conn) # tra ket noi ve pool

def init_db(database_url: str):
    global db_pool
    try:
        db_pool = psycopg2.pool.SimpleConnectionPool(1, 20, dsn=database_url)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # bang users
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        balance BIGINT DEFAULT 0,
                        message_count INTEGER DEFAULT 0,
                        reaction_count INTEGER DEFAULT 0,
                        PRIMARY KEY (user_id, guild_id)
                    )
                ''')

                # bang shop roles
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS shop_roles (
                        role_id BIGINT PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        price INTEGER NOT NULL
                    )
                ''')
                
                # bang custom roles
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS custom_roles (
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        role_id BIGINT NOT NULL,
                        role_name TEXT,
                        role_color TEXT,
                        PRIMARY KEY (user_id, guild_id)
                    )
                ''')

                # bang config, don gian hoa
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS guild_configs (
                        guild_id BIGINT PRIMARY KEY,
                        config_data JSONB
                    )
                ''')

                conn.commit()
        logging.info("Database PostgreSQL khoi tao thanh cong.")
    except Exception as e:
        logging.error(f"Loi khoi tao database: {e}")

def execute_query(query, params=(), fetch=None):
    try:
        with get_db_connection() as conn:
            # dung RealDictCursor de tu dong tra ve dict
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                
                if fetch == 'one':
                    return cur.fetchone()
                elif fetch == 'all':
                    return cur.fetchall()
                else:
                    conn.commit()
                    return None
    except Exception as e:
        logging.error(f"Query that bai: {e}")
        return None

# User Functions
def get_or_create_user(user_id, guild_id):
    user = execute_query("SELECT * FROM users WHERE user_id = %s AND guild_id = %s", (user_id, guild_id), fetch='one')
    if not user:
        execute_query("INSERT INTO users (user_id, guild_id) VALUES (%s, %s) ON CONFLICT(user_id, guild_id) DO NOTHING", (user_id, guild_id))
        user = execute_query("SELECT * FROM users WHERE user_id = %s AND guild_id = %s", (user_id, guild_id), fetch='one')
    return user

def update_user_data(user_id, guild_id, **kwargs):
    fields = ', '.join([f'{key} = %s' for key in kwargs])
    values = list(kwargs.values())
    values.extend([user_id, guild_id])
    query = f"UPDATE users SET {fields} WHERE user_id = %s AND guild_id = %s"
    execute_query(query, tuple(values))

def get_top_users(guild_id, limit=20):
    query = "SELECT user_id, balance FROM users WHERE guild_id = %s ORDER BY balance DESC LIMIT %s"
    return execute_query(query, (guild_id, limit), fetch='all')

def get_guild_users(guild_id):
    # lay all user trong guild tu db
    query = "SELECT user_id, balance FROM users WHERE guild_id = %s ORDER BY user_id"
    return execute_query(query, (guild_id,), fetch='all')

def get_user_profile(user_id, guild_id):
    # lay profile chi tiet
    query = """
    SELECT u.*, cr.role_id, cr.role_name, cr.role_color
    FROM users u
    LEFT JOIN custom_roles cr ON u.user_id = cr.user_id AND u.guild_id = cr.guild_id
    WHERE u.user_id = %s AND u.guild_id = %s;
    """
    return execute_query(query, (user_id, guild_id), fetch='one')


# Shop Role Functions
def add_role_to_shop(role_id, guild_id, price):
    query = """
    INSERT INTO shop_roles (role_id, guild_id, price) VALUES (%s, %s, %s)
    ON CONFLICT (role_id) DO UPDATE SET
        guild_id = EXCLUDED.guild_id,
        price = EXCLUDED.price;
    """
    execute_query(query, (role_id, guild_id, price))

def remove_role_from_shop(role_id, guild_id):
    execute_query("DELETE FROM shop_roles WHERE role_id = %s AND guild_id = %s", (role_id, guild_id))

def get_shop_roles(guild_id):
    return execute_query("SELECT * FROM shop_roles WHERE guild_id = %s ORDER BY price ASC", (guild_id,), fetch='all')

# Custom Role Functions
def get_custom_role(user_id, guild_id):
    return execute_query("SELECT * FROM custom_roles WHERE user_id = %s AND guild_id = %s", (user_id, guild_id), fetch='one')

def add_or_update_custom_role(user_id, guild_id, role_id, role_name, role_color):
    query = """
    INSERT INTO custom_roles (user_id, guild_id, role_id, role_name, role_color) VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (user_id, guild_id) DO UPDATE SET
        role_id = EXCLUDED.role_id,
        role_name = EXCLUDED.role_name,
        role_color = EXCLUDED.role_color;
    """
    execute_query(query, (user_id, guild_id, role_id, role_name, role_color))

def delete_custom_role_data(user_id, guild_id):
    execute_query("DELETE FROM custom_roles WHERE user_id = %s AND guild_id = %s", (user_id, guild_id))

# Guild Config Functions
def get_all_guild_configs():
    configs_list = execute_query("SELECT guild_id, config_data FROM guild_configs", fetch='all')
    config_map = {}
    if configs_list:
        for config_row in configs_list:
            guild_id_str = str(config_row['guild_id'])
            config_map[guild_id_str] = config_row.get('config_data', {})
    return config_map

def get_guild_config(guild_id: int):
    # Lay config cho 1 guild
    row = execute_query("SELECT config_data FROM guild_configs WHERE guild_id = %s", (guild_id,), fetch='one')
    return row.get('config_data', {}) if row else None

def update_guild_config(guild_id, **kwargs):
    # Ham nay don gian hon nhieu
    current_config = get_guild_config(guild_id)
    if current_config is None:
        current_config = {}
    
    # merge
    current_config.update(kwargs)

    # update lai vao db
    execute_query(
        """
        UPDATE guild_configs 
        SET config_data = %s 
        WHERE guild_id = %s
        """,
        (Json(current_config), guild_id)
    )