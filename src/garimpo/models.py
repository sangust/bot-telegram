from sqlalchemy import (
    Column, Integer, String, BigInteger,
    Boolean, DateTime, Numeric, UniqueConstraint)
from .config import BASE, criar_table

class Product(BASE):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("marca", "variante_id", name="marca_variante"),)

    id = Column(Integer, primary_key=True)
    marca = Column(String(100), nullable=False)
    nome = Column(String(200))
    tamanho = Column(String(50))
    preco_atual = Column(Numeric(10, 2))
    preco_real = Column(Numeric(10,2))
    imagem = Column(String)
    disponivel = Column(Boolean)
    link = Column(String)
    variante_id = Column(BigInteger, nullable=False)
    data_coleta = Column(DateTime(timezone=True))
    
    #criar um compare_price

criar_table()