import os
import pymysql
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker

def get_sqlalchemy_engine():
    DB_USER = os.getenv('LOGIN_DB')
    DB_PASSWORD = os.getenv('PASSWORD_DB')
    DB_HOST = 'localhost'
    DB_NAME = 'alpha_trade'
    if not DB_USER or not DB_PASSWORD:
        raise RuntimeError("LOGIN_DB ou PASSWORD_DB non définis dans les variables d'environnement système.")
    url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}?charset=utf8mb4"
    engine = create_engine(url, echo=False, pool_recycle=3600)
    return engine

# Pour obtenir une session SQLAlchemy
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_sqlalchemy_engine())

# Pour obtenir la MetaData (utile pour reflection ou accès aux tables dynamiquement)
metadata = MetaData()
