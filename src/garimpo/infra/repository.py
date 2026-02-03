from .database import LocalDataBase, CloudDataBase
from ..domain.models import Product
from .schemas import ProductSchema
from datetime import datetime, timezone

class LocalProductRepository:
    def __init__(self, db=LocalDataBase()):
        self.session = db.SESSION()

    def add(self, product:ProductSchema):
        new_product = Product(**product.model_dump())
        
        self.session.add(new_product)


    def update(self, product:ProductSchema, product_id: int):
        try:
            old_product = self.session.query(Product).filter(Product.id == product_id).first()
            updated_product = Product(**product.model_dump())
        except Exception as e:
            print("ERROR:",e)
            self.session.close()
            return
            
        old_product.preco_atual = updated_product.preco_atual
        old_product.preco_real = updated_product.preco_real
        old_product.disponivel = updated_product.disponivel
        old_product.data_coleta = updated_product.data_coleta

    def commit(self):
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            print(f"ERROR: {e}")
        finally:
            self.session.close()
