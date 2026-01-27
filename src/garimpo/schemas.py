from pydantic import BaseModel, Field
from datetime import datetime

class ProductSchema(BaseModel):
    marca: str
    nome: str
    tamanho: str
    preco: float = Field(gt=0)
    disponivel: bool
    imagem: str
    link: str
    variante_id: int
    data_coleta: datetime