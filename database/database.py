import psycopg2
from psycopg2 import pool
from psycopg2.extras import Json
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

                # bang config
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS guild_configs (
                        guild_id BIGINT PRIMARY KEY,
                        shop_channel_id BIGINT,
                        leaderboard_thread_id BIGINT,
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
            with conn.cursor() as cur:
                cur.execute(query, params)
                
                if fetch == 'one':
                    result = cur.fetchone()
                    return dict(zip([desc[0] for desc in cur.description], result)) if result else None
                elif fetch == 'all':
                    results = cur.fetchall()
                    columns = [desc[0] for desc in cur.description]
                    return [dict(zip(columns, row)) for row in results]
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
        execute_query("INSERT INTO users (user_id, guild_id) VALUES (%s, %s)", (user_id, guild_id))
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
    configs = execute_query("SELECT * FROM guild_configs", fetch='all')
    config_map = {}
    if configs:
        for config in configs:
            guild_id_str = str(config['guild_id'])
            # gop config
            combined_config = config.get('config_data', {})
            if 'shop_channel_id' in config:
                combined_config['shop_channel_id'] = config['shop_channel_id']
            if 'leaderboard_thread_id' in config:
                combined_config['leaderboard_thread_id'] = config['leaderboard_thread_id']
            config_map[guild_id_str] = combined_config
    return config_map

def update_guild_config(guild_id, **kwargs):
    # tach rieng cot chinh va json
    main_cols = ['shop_channel_id', 'leaderboard_thread_id']
    main_col_updates = {k: v for k, v in kwargs.items() if k in main_cols}
    json_data_updates = {k: v for k, v in kwargs.items() if k not in main_cols}

    params = []
    
    # update cot chinh
    if main_col_updates:
        fields = ', '.join([f'"{key}" = %s' for key in main_col_updates])
        values = list(main_col_updates.values())
        params.extend(values)
        query = f"UPDATE guild_configs SET {fields} WHERE guild_id = %s"
        params.append(guild_id)
        execute_query(query, tuple(params))

    # update json
    if json_data_updates:
        # lay json hien tai
        current_config = execute_query("SELECT config_data FROM guild_configs WHERE guild_id = %s", (guild_id,), fetch='one')
        current_json = current_config['config_data'] if current_config and current_config['config_data'] else {}
        
        # merge
        current_json.update(json_data_updates)

        # update lai
        execute_query(
            "UPDATE guild_configs SET config_data = %s WHERE guild_id = %s",
            (Json(current_json), guild_id)
        )