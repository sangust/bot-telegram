from .database import LocalDataBase, CloudDataBase
from ..domain.models import Product
from .schemas import ProductSchema
from sqlalchemy import func
import pandas as pd
import pandas_gbq

class LocalProductRepository:
    def __init__(self, db=LocalDataBase()):
        self.session = db.SESSION()

    def discount_products(self):
        return self.session.query(
            Product.marca,
            Product.nome,
            Product.preco_atual,
            Product.preco_real,
            Product.link,
            Product.imagem,
            func.group_concat(Product.tamanho, ', ').label('tamanhos_disponiveis')
        ).filter(
            Product.preco_atual < Product.preco_real,
            Product.disponivel == True
        ).group_by(
            Product.marca, 
            Product.nome, 
            Product.preco_atual, 
            Product.link
        ).order_by(
            Product.preco_atual.asc()
        ).all()
    

    def add(self, product:ProductSchema):
        new_product = Product(**product.model_dump())
        self.session.add(new_product)


    def update(self, product:ProductSchema):
        try:
            old_product = self.session.query(Product).filter(
                Product.marca == product.marca,
                Product.variante_id == product.variante_id).first()
            
            updated_product = Product(**product.model_dump())

            if not old_product:
                raise Exception ("Product not found!!")
            
            old_product.preco_atual = updated_product.preco_atual
            old_product.preco_real = updated_product.preco_real
            old_product.disponivel = updated_product.disponivel
            old_product.data_coleta = updated_product.data_coleta
        except Exception as e:
           raise e   

    def commit(self):
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise e
        finally:
            self.session.close()


class CloudProductRepository:
    def __init__(self, cloud_db = CloudDataBase(), local_db = LocalDataBase()):
        self.cloud_db = cloud_db
        self.table_id = cloud_db.table      
        self.project_id = cloud_db.client.project

        self.local_engine = local_db.ENGINE

    def sync_local_to_cloud(self):
        local_products = pd.read_sql_table("products", self.local_engine)
        local_products['data_coleta'] = pd.to_datetime(local_products['data_coleta'])
        pandas_gbq.to_gbq(local_products, 
                        self.table_id, 
                        self.project_id,
                        if_exists="replace",
                        credentials=self.cloud_db.credentials)

