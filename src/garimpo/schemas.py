from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ProductSchema(BaseModel):
    marca: str
    nome: str
    tamanho: str
    preco_real:  Optional[float] 
    preco_atual: float = Field(gt=0)
    disponivel: bool
    imagem: str
    link: str
    variante_id: int
    data_coleta: datetime