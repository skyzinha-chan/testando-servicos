from s3_utils import upload_to_s3

# Simula um arquivo enviado pelo usuário


class FileObj:
    def __init__(self, filename):
        self.filename = filename

    def read(self):
        return b"conteudo do arquivo"


file = FileObj("nota_fiscal_teste.png")
bucket_name = "notas-fiscais-api"
region = "us-east-1"

try:
    s3_url = upload_to_s3(file, bucket_name, region)
    print(f"Arquivo enviado com sucesso! URL: {s3_url}")
except Exception as e:
    print(f"Erro: {str(e)}")
