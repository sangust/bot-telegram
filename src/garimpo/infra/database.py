from google.cloud import bigquery
from google.oauth2 import service_account
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine
from dotenv import load_dotenv
from .config import DATABASE_URL

class LocalDataBase():
    def __init__(self, url=DATABASE_URL):
        load_dotenv()
        self.DATABASE_URL = url
        self.ENGINE = create_engine(self.DATABASE_URL, echo=False)
        self.SESSION = sessionmaker(bind=self.ENGINE)
        self.BASE = declarative_base()

    def criar_table_orm(self):
        self.BASE.metadata.create_all(self.ENGINE)



class CloudDataBase():
    def __init__(self, credentials_path:str = "config.json", project_id: str = "eco-avenue-461519-f8", table:str="telegramdata.shops"):
        self.credentials = service_account.Credentials.from_service_account_file(credentials_path)
        self.client = bigquery.Client(credentials=self.credentials, project=project_id)
        self.table = table

