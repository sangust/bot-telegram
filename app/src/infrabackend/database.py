from google.cloud import bigquery
from google.oauth2 import service_account
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from .config import DATABASE_URL, CONNECT_ARGS, CREDENTIALS, PROJECT_ID, TABLE
from app.src.domain.models import BASE

class LocalDatabase():
    def __init__(self, url: str = DATABASE_URL):  
        self.DATABASE_URL = url
        self.ENGINE = create_engine(
            self.DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            connect_args=CONNECT_ARGS,
        )
        self.SESSION = sessionmaker(bind=self.ENGINE, autocommit=False, autoflush=False)
        self.BASE = BASE


class CloudDatabase():
    def __init__(self, credentials_path:str = CREDENTIALS, project_id: str = PROJECT_ID, table:str=TABLE):
        self.credentials = service_account.Credentials.from_service_account_file(credentials_path)
        self.client = bigquery.Client(credentials=self.credentials, project=project_id)
        self.table = table

