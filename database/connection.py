import os
import pymysql

def get_db_connection():
    DB_USER = os.getenv('LOGIN_DB')
    DB_PASSWORD = os.getenv('PASSWORD_DB')
    DB_HOST = 'localhost'
    DB_NAME = 'alpha_trade'
    if not DB_USER or not DB_PASSWORD:
        raise RuntimeError("LOGIN_DB ou PASSWORD_DB non définis dans les variables d'environnement système.")
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset='utf8mb4'
        )
        return conn
    except Exception as e:
        raise RuntimeError(f"Erreur de connexion à la base de données : {e}")

