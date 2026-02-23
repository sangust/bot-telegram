from .database import LocalDatabase, CloudDatabase
from ..domain.models import Product, Bot
from .schemas import ProductSchema
from sqlalchemy import func
import pandas as pd
import pandas_gbq

class LocalRepository:
    def __init__(self, db=None):
        db = db or LocalDatabase()
        self.session = db.SESSION()
                    
    def discount_products(self, stores):
        if stores:
            return self.session.query(
            Product.brand,
            Product.name,
            Product.discount_price,
            Product.full_price,
            Product.link,
            Product.image,
            func.string_agg(Product.size, ', ').label('size')
        ).filter(
            Product.brand.in_(stores),
            Product.discount_price < Product.full_price,
            Product.available == True
        ).group_by(
            Product.brand, 
            Product.name, 
            Product.full_price, 
            Product.link,
            Product.discount_price,
            Product.image
        ).order_by(
            Product.full_price.asc()
        ).all()
        
    

    def add(self, *models):
        try:
            for m in models:
                self.session.add(m)
        except Exception as e:
            print(e)
            raise e

    def update(self, product:ProductSchema):
        try:
            old_product = self.session.query(Product).filter(
                Product.brand == product.brand,
                Product.clothing_id == product.clothing_id).first()
            
            updated_product = Product(**product.model_dump())

            if not old_product:
                raise Exception
            
            old_product.discount_price = updated_product.discount_price
            old_product.full_price = updated_product.full_price
            old_product.available = updated_product.available
            
        except Exception as e:
           raise e   
        
    def update_bot(self, bot: Bot):
        try:
            existing = self.session.query(Bot).filter(
                Bot.user_id == bot.user_id
            ).first()

            if not existing:
                raise ValueError("Bot not found")

            if bot.bot_token is not None:
                existing.bot_token = bot.bot_token

            if bot.chat_id is not None:
                existing.chat_id = bot.chat_id

            if bot.stores is not None:
                existing.stores = bot.stores

            if bot.affiliate_link is not None:
                existing.affiliate_link = bot.affiliate_link

            if bot.today_sent is not None:
                existing.today_sent = bot.today_sent

            if bot.all_sent is not None:
                existing.all_sent = bot.all_sent

            if bot.status is not None:
                existing.status = bot.status

        except Exception as e:
            raise e


    def commit(self):
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            print("error",e)
            raise e
        finally:
            self.session.close()


""" class CloudProductRepository:
    def __init__(self, cloud_db = CloudDatabase(project_id="terraform-487103"), local_db = LocalDatabase()):
        self.cloud_db = cloud_db
        self.table_id = cloud_db.table      
        self.project_id = cloud_db.client.project

        self.local_engine = local_db.ENGINE

    def normalize_to_cloud(self):
        local_products = pd.read_sql_table("products", self.local_engine)
        local_products["discount_price"] = local_products["discount_price"].astype(float)
        local_products["full_price"]  = local_products["full_price"].astype(float)

        for c in ["brand","name","size","image","link"]:
            local_products[c] = local_products[c].astype(str)

        self.products = local_products

    def sync_local_to_cloud(self):
        local_products = self.products
        pandas_gbq.to_gbq(local_products, 
                        self.table_id, 
                        self.project_id,
                        if_exists="replace",
                        credentials=self.cloud_db.credentials) """

