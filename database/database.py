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
                # tao bang neu chua co
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT NOT NULL,
                        guild_id BIGINT NOT NULL,
                        balance BIGINT DEFAULT 0,
                        message_count INTEGER DEFAULT 0,
                        reaction_count INTEGER DEFAULT 0,
                        fake_boosts INTEGER DEFAULT 0,
                        PRIMARY KEY (user_id, guild_id)
                    )
                ''')
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS shop_roles (
                        role_id BIGINT PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        price INTEGER NOT NULL,
                        creator_id BIGINT,
                        creation_price INTEGER
                    )
                ''')
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
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS guild_configs (
                        guild_id BIGINT PRIMARY KEY,
                        config_data JSONB
                    )
                ''')
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS transactions (
                        transaction_id SERIAL PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        user_id BIGINT NOT NULL,
                        transaction_type TEXT NOT NULL,
                        item_name TEXT,
                        amount_changed BIGINT NOT NULL,
                        new_balance BIGINT NOT NULL,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # kiem tra & them cot moi vao bang custom_roles
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'custom_roles'")
                existing_custom_cols = [row[0] for row in cur.fetchall()]
                
                custom_cols_to_add = {
                    'role_style': 'TEXT', 'gradient_color_1': 'TEXT', 'gradient_color_2': 'TEXT'
                }
                for col, col_type in custom_cols_to_add.items():
                    if col not in existing_custom_cols:
                        cur.execute(f"ALTER TABLE custom_roles ADD COLUMN {col} {col_type}")

                # kiem tra & them cot moi vao bang shop_roles
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'shop_roles'")
                existing_shop_cols = [row[0] for row in cur.fetchall()]
                shop_cols_to_add = {
                    'creator_id': 'BIGINT', 'creation_price': 'INTEGER'
                }
                for col, col_type in shop_cols_to_add.items():
                    if col not in existing_shop_cols:
                        cur.execute(f"ALTER TABLE shop_roles ADD COLUMN {col} {col_type}")

                # kiem tra & them cot real_boosts vao bang users
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'")
                existing_user_cols = [row[0] for row in cur.fetchall()]
                if 'real_boosts' not in existing_user_cols:
                    cur.execute("ALTER TABLE users ADD COLUMN real_boosts INTEGER DEFAULT 0")


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

def wipe_guild_data(guild_id):
    # ham xoa toan bo du lieu cua 1 guild
    role_ids_to_delete = set()
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # lay va xoa custom roles
                cur.execute("DELETE FROM custom_roles WHERE guild_id = %s RETURNING role_id", (guild_id,))
                deleted_custom_roles = cur.fetchall()
                for role in deleted_custom_roles:
                    role_ids_to_delete.add(role[0])
                
                # lay va xoa shop roles
                cur.execute("DELETE FROM shop_roles WHERE guild_id = %s RETURNING role_id", (guild_id,))
                deleted_shop_roles = cur.fetchall()
                for role in deleted_shop_roles:
                    role_ids_to_delete.add(role[0])

                # xoa users va transactions
                cur.execute("DELETE FROM users WHERE guild_id = %s", (guild_id,))
                cur.execute("DELETE FROM transactions WHERE guild_id = %s", (guild_id,))
                
                conn.commit()
        
        logging.info(f"Da xoa toan bo du lieu database cho guild {guild_id}.")
        return list(role_ids_to_delete)
    except Exception as e:
        logging.error(f"Loi khi xoa du lieu guild {guild_id}: {e}")
        return []


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
    SELECT u.*, cr.role_id, cr.role_name, cr.role_color, cr.role_style, cr.gradient_color_1, cr.gradient_color_2
    FROM users u
    LEFT JOIN custom_roles cr ON u.user_id = cr.user_id AND u.guild_id = cr.guild_id
    WHERE u.user_id = %s AND u.guild_id = %s;
    """
    return execute_query(query, (user_id, guild_id), fetch='one')


# Shop Role Functions
def add_role_to_shop(role_id, guild_id, price, creator_id=None, creation_price=None):
    query = """
    INSERT INTO shop_roles (role_id, guild_id, price, creator_id, creation_price) VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (role_id) DO UPDATE SET
        guild_id = EXCLUDED.guild_id,
        price = EXCLUDED.price,
        creator_id = EXCLUDED.creator_id,
        creation_price = EXCLUDED.creation_price;
    """
    execute_query(query, (role_id, guild_id, price, creator_id, creation_price))

def remove_role_from_shop(role_id, guild_id):
    execute_query("DELETE FROM shop_roles WHERE role_id = %s AND guild_id = %s", (role_id, guild_id))

def get_shop_roles(guild_id):
    return execute_query("SELECT * FROM shop_roles WHERE guild_id = %s ORDER BY price ASC", (guild_id,), fetch='all')

# Custom Role Functions
def get_custom_role(user_id, guild_id):
    return execute_query("SELECT * FROM custom_roles WHERE user_id = %s AND guild_id = %s", (user_id, guild_id), fetch='one')

def get_all_custom_roles_for_guild(guild_id):
    return execute_query("SELECT user_id, role_id FROM custom_roles WHERE guild_id = %s", (guild_id,), fetch='all')

def add_or_update_custom_role(user_id, guild_id, role_id, role_name, role_color, role_style=None, color1=None, color2=None):
    query = """
    INSERT INTO custom_roles (user_id, guild_id, role_id, role_name, role_color, role_style, gradient_color_1, gradient_color_2) 
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (user_id, guild_id) DO UPDATE SET
        role_id = EXCLUDED.role_id,
        role_name = EXCLUDED.role_name,
        role_color = EXCLUDED.role_color,
        role_style = EXCLUDED.role_style,
        gradient_color_1 = EXCLUDED.gradient_color_1,
        gradient_color_2 = EXCLUDED.gradient_color_2;
    """
    execute_query(query, (user_id, guild_id, role_id, role_name, role_color, role_style, color1, color2))

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

def update_guild_config(guild_id: int, updates: dict):
    # ham cap nhat an toan
    if not updates:
        return
        
    current_config = get_guild_config(guild_id)
    if current_config is None:
        current_config = {}
    
    # merge
    current_config.update(updates)

    # update lai vao db
    query = """
        INSERT INTO guild_configs (guild_id, config_data)
        VALUES (%s, %s)
        ON CONFLICT (guild_id)
        DO UPDATE SET config_data = EXCLUDED.config_data;
    """
    execute_query(query, (guild_id, Json(current_config)))


# Transaction Log Functions
def log_transaction(guild_id, user_id, transaction_type, item_name, amount_changed, new_balance):
    query = """
    INSERT INTO transactions (guild_id, user_id, transaction_type, item_name, amount_changed, new_balance)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    execute_query(query, (guild_id, user_id, transaction_type, item_name, amount_changed, new_balance))

def get_guild_transactions(guild_id, limit=50, offset=0):
    query = "SELECT * FROM transactions WHERE guild_id = %s ORDER BY timestamp DESC LIMIT %s OFFSET %s"
    return execute_query(query, (guild_id, limit, offset), fetch='all')

def get_user_transactions(guild_id, user_id, limit=50, offset=0):
    query = "SELECT * FROM transactions WHERE guild_id = %s AND user_id = %s ORDER BY timestamp DESC LIMIT %s OFFSET %s"
    return execute_query(query, (guild_id, user_id, limit, offset), fetch='all')

def count_guild_transactions(guild_id):
    result = execute_query("SELECT COUNT(*) as total FROM transactions WHERE guild_id = %s", (guild_id,), fetch='one')
    return result['total'] if result else 0