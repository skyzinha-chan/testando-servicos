import boto3
from botocore.exceptions import NoCredentialsError


def upload_to_s3(file, bucket_name, region):
    """
    Faz o upload de um arquivo para o S3 e retorna a URL do arquivo.
    :param file: Arquivo enviado pelo usuário.
    :param bucket_name: Nome do bucket S3.
    :param region: Região do bucket S3.
    :return: URL do arquivo no S3.
    """
    s3 = boto3.client('s3', region_name=region)
    try:
        # Faz o upload do arquivo
        s3.upload_fileobj(file, bucket_name, file.filename)
        # Retorna a URL do arquivo no S3
        return f"https://{bucket_name}.s3.{region}.amazonaws.com/{file.filename}"
    except NoCredentialsError:
        raise Exception("Credenciais da AWS não encontradas.")
    except Exception as e:
        raise Exception(f"Erro ao fazer upload do arquivo: {str(e)}")


'''
A função upload_to_s3 recebe três parâmetros:

file: O arquivo enviado pelo usuário.

bucket_name: O nome do bucket S3 onde o arquivo será armazenado.

region: A região do bucket S3.

Ela faz o upload do arquivo para o S3 e retorna a URL do arquivo.
'''
