# models/nota_fiscal_model.py
from pydantic import BaseModel

class NotaFiscal(BaseModel):
    nome_emissor: str = None
    CNPJ_emissor: str = None
    endereco_emissor: str = None
    CNPJ_CPF_consumidor: str = None
    data_emissao: str = None
    numero_nota_fiscal: str = None
    serie_nota_fiscal: str = None
    valor_total: float = None
    forma_pgto: str = None
