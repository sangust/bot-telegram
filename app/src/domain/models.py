from sqlalchemy import (
    Column, Integer, String, BigInteger,
    Boolean, Date, Numeric, UniqueConstraint)
from sqlalchemy.orm import declarative_base

Base = declarative_base()
class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("marca", "variante_id", name="marca_variante"),)

    id = Column(Integer, primary_key=True)
    marca = Column(String(100), nullable=False)
    nome = Column(String(200))
    tamanho = Column(String(50))
    preco_atual = Column(Numeric(10, 2), nullable=False)
    preco_real = Column(Numeric(10,2), nullable=False)
    imagem = Column(String)
    disponivel = Column(Boolean, nullable=False)
    link = Column(String)
    variante_id = Column(BigInteger, nullable=False)
    data_coleta = Column(Date)

