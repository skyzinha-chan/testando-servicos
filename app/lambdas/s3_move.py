# app/lambdas/s3_move_lambda.py  Move as notas fiscais no S3 com base no pagamento.
import json
import boto3
import os
from botocore.exceptions import NoCredentialsError, ClientError
import logging

# Configuração do logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class S3Mover:
    def __init__(self, source_bucket):
        # Inicializa o cliente S3
        self.s3 = boto3.client('s3')
        self.source_bucket = source_bucket

    def move_file(self, source_key,  destination_folder):
        """
        Move um arquivo na bucket S3.

        Parâmetros:
            source_key (str): Caminho do arquivo no bucket de origem.
            destination_folder (str): Pasta de destino no bucket de destino.

        Retorno:
            bool: True se o arquivo foi movido com sucesso, False caso contrário.
        """
        try:
            # Define o caminho de destino do arquivo no bucket de destino
            destination_key = f"{destination_folder}/{os.path.basename(source_key)}"

            # Copia o arquivo do bucket de origem para a bucket pasta de destino
            copy_source = {'Bucket': self.source_bucket, 'Key': source_key}
            self.s3.copy_object(CopySource=copy_source,
                                Bucket=self.source_bucket, Key=destination_key)

            # Exclui o arquivo do bucket de origem após a cópia
            self.s3.delete_object(Bucket=self.source_bucket, Key=source_key)

            logger.info(
                f"Arquivo movido com sucesso: {source_key} -> {destination_key}")
            return True
        except ClientError as e:
            # Log de erro caso ocorra uma falha ao mover o arquivo
            logger.error(f"Erro ao mover o arquivo: {e}")
            return False


class MoveLambdaHandler:
    def __init__(self, event):
        self.event = event
        # Obtém os nomes dos buckets de origem e destino das variáveis de ambiente
        self.source_bucket = os.environ['SOURCE_BUCKET']
        self.mover = S3Mover(self.source_bucket)

    def validate_event(self):
        """
        Valida os dados do evento recebido.

        Retorno:
            tuple: (bool, str ou tuple) - True se válido, False e mensagem de erro se inválido.
        """
        # Extrai os dados do evento
        # Caminho do arquivo no bucket de origem
        source_key = self.event.get('source_key')
        # Método de pagamento (ex: "dinheiro", "pix", "outros")
        payment_method = self.event.get('payment_method')

        # Valida se os campos obrigatórios foram fornecidos e são strings válidas
        if not source_key or not isinstance(source_key, str):
            return False, 'O campo "source_key" é obrigatório e deve ser uma string válida.'

        if not payment_method or not isinstance(payment_method, str):
            return False, 'O campo "payment_method" é obrigatório e deve ser uma string válida.'

        return True, (source_key, payment_method)

    def handle(self):
        """
        Processa o evento e move o arquivo no S3 com base no método de pagamento.
        """
        is_valid, validation_message = self.validate_event()
        if not is_valid:
            logger.error(f"Evento inválido: {validation_message}")
            raise ValueError(validation_message)

        source_key, payment_method = validation_message

        # Define a pasta de destino com base no método de pagamento
        destination_folder = "dinheiro" if payment_method.lower() in [
            "dinheiro", "pix"] else "outros"

        # Move o arquivo
        if not self.mover.move_file(source_key, destination_folder):
            raise RuntimeError(
                f"Erro ao mover o arquivo {source_key} para {destination_folder}.")


def lambda_handler(event, context):
    """
    Função principal da Lambda que processa o evento.
    """
    logger.info("Iniciando processamento do evento na Lambda s3_move_lambda.")
    try:
        handler = MoveLambdaHandler(event)
        handler.handle()
        logger.info("Processamento concluído com sucesso.")
    except ValueError as ve:
        logger.error(f"Erro de validação: {ve}")
    except RuntimeError as re:
        logger.error(f"Erro ao mover arquivo: {re}")
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
