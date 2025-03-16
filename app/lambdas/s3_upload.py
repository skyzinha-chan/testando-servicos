# app/lambdas/s3_upload.py    Salva os dados processados no Amazon S3
import json
import boto3
import os
import base64
from botocore.exceptions import NoCredentialsError
import logging
from requests_toolbelt.multipart import decoder
import time

# Configuração do logger (ajustado para produção)
logger = logging.getLogger()
logger.setLevel(logging.INFO)  # Apenas warning e erros em produção

# Cliente do Step Functions
stepfunctions_client = boto3.client('stepfunctions')


class S3Uploader:
    """Classe responsável por fazer upload de arquivos para o S3."""

    def __init__(self, bucket_name):
        self.s3 = boto3.client('s3')
        self.bucket_name = bucket_name

    def upload_file(self, file_name, file_content):
        """
        Faz o upload de um arquivo para o S3.

        Parâmetros:
            file_name (str): Nome do arquivo a ser salvo.
            file_content (bytes): Conteúdo do arquivo.

        Retorno:
            dict: Resposta com status e mensagem.
        """
        try:
            logger.info(f"Iniciando upload do arquivo {file_name} para o S3.")
            # Faz o upload do arquivo para o bucket S3
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=file_name,
                Body=file_content
            )
            logger.info(
                f"Upload do arquivo {file_name} concluído com sucesso.")
            return {
                'statusCode': 200,
                'body': json.dumps({'file_name': file_name})
            }
        except Exception as e:
            logger.error(f"Erro ao fazer upload: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Erro interno no servidor. Tente novamente mais tarde.'})
            }


class LambdaHandler:
    """Classe que gerencia o processamento do evento da Lambda."""

    def __init__(self, event):
        self.event = event
        # Obtém o nome do bucket de origem a partir da variável de ambiente
        self.bucket_name = os.environ['SOURCE_BUCKET']
        self.uploader = S3Uploader(self.bucket_name)

    def validate_event(self):
        """Valida o evento recebido."""
        logger.info("Validando evento recebido.")
        # Verifica se o corpo da requisição está no formato multipart/form-data
        if 'body' not in self.event:
            logger.warning("Evento sem corpo. Formato inválido.")
            return False, 'Formato de requisição inválido. Use multipart/form-data.'

        # Extrai o nome do arquivo e o conteúdo do corpo da requisição
        content_type = self.event['headers'].get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            logger.warning(f"Formato de conteúdo inválido: {content_type}")
            return False, 'Formato inválido. Envie como multipart/form-data.'

        body = self.event['body']
        if self.event.get('isBase64Encoded', False):
            try:
                logger.info("Decodificando corpo da requisição (Base64).")
                # Decodifica o corpo da requisição (que está em Base64)
                body = base64.b64decode(body)
            except Exception as e:
                logger.error(f"Erro ao decodificar Base64: {str(e)}")
                return False, 'Erro ao processar o arquivo.'

        # Decodifica o corpo da requisição (que é um multipart/form-data)
        try:
            logger.info("Decodificando multipart/form-data.")
            multipart_data = decoder.MultipartDecoder(body, content_type)
        except Exception as e:
            logger.error(f"Erro ao decodificar multipart: {str(e)}")
            return False, 'Erro ao processar arquivo.'

        # Extrai o nome do arquivo e o conteúdo do arquivo
        for part in multipart_data.parts:
            if part.headers.get(b'Content-Disposition'):
                disposition = part.headers[b'Content-Disposition'].decode()

                if 'filename=' in disposition:
                    file_name = disposition.split(
                        'filename=')[-1].strip().replace('"', '')
                    file_content = part.content

                    # Valida se o arquivo é uma imagem (PNG, JPG ou JPEG)
                    if not file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                        logger.warning(
                            f"Arquivo {file_name} não é uma imagem válida.")
                        return False, 'O arquivo deve ser uma imagem (PNG, JPG, JPEG).'

                    logger.info(f"Arquivo {file_name} validado com sucesso.")
                    return True, (file_name, file_content)

        logger.warning("Nenhum arquivo encontrado no corpo da requisição.")
        return False, 'Nenhum arquivo encontrado no corpo da requisição.'

    def handle(self):
        """
        Função principal que processa o evento e realiza o upload.

        Retorno:
            dict: Resposta com statusCode e corpo da mensagem (sucesso ou erro).
        """
        try:
            logger.info("Iniciando processamento do evento.")
            is_valid, validation_message = self.validate_event()
            if not is_valid:
                logger.warning(f"Evento inválido: {validation_message}")
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': validation_message})
                }

            file_name, file_content = validation_message
            logger.info(f"Processando arquivo {file_name}.")
            upload_response = self.uploader.upload_file(
                file_name, file_content)

            return upload_response

        except NoCredentialsError:
            logger.error("Credenciais da AWS não encontradas.")
            # Retorna erro caso as credenciais da AWS não sejam encontradas
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Credenciais da AWS não encontradas.'})
            }
        except Exception as e:
            # Retorna erro genérico com detalhes da exceção
            logger.error(f"Erro inesperado: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Erro interno no servidor. Tente novamente mais tarde.'})
            }


def retry_step_function_execution(input_data, stepfunctions_client, state_machine_arn, retries=3, backoff=2):
    """
    Tenta executar o Step Functions com retry.

    Parameters:
        input_data (dict): Dados para enviar ao Step Functions.
        stepfunctions_client (boto3.client): Cliente do Step Functions.
        state_machine_arn (str): ARN do Step Function.
        retries (int): Número máximo de tentativas.
        backoff (int): Multiplicador para tempo de espera entre tentativas.

    Returns:
        dict: Resposta do Step Functions.
    """
    for attempt in range(1, retries + 1):
        try:
            response = stepfunctions_client.start_sync_execution(
                stateMachineArn=state_machine_arn,
                input=json.dumps(input_data)
            )
            logger.info(
                f"Execução do Step Functions iniciada. ID: {response['executionArn']}")
            return {
                'statusCode': 200,
                # O resultado final do Step Functions
                'body': response['output']
            }  # Se bem-sucedido, retorna a resposta
        except Exception as e:
            logger.error(
                f"Tentativa {attempt} falhou ao iniciar Step Functions: {str(e)}")
            if attempt == retries:
                raise  # Levanta a exceção após o número máximo de tentativas
            time.sleep(backoff * attempt)  # Aguarda antes de tentar novamente


def lambda_handler(event, context):
    """Função de entrada da Lambda."""
    logger.info("Lambda iniciada.")
    handler = LambdaHandler(event)
    upload_response = handler.handle()

    # Verifica se o upload foi bem-sucedido
    if upload_response['statusCode'] == 200:
        # Verifica se o ARN do Step Functions está definido
        step_function_arn = os.environ.get('STEP_FUNCTIONS_ARN')
        if step_function_arn:
            logger.info("Iniciando execução do Step Functions.")
            # Inicia a execução do Step Functions
            stepfunctions_client = boto3.client('stepfunctions')

            # Prepara a entrada para o Step Functions
            input_data = {
                "bucket_name": handler.bucket_name,
                "file_name": json.loads(upload_response['body'])['file_name']
            }

        try:
            # Tentativas com backoff
            response = retry_step_function_execution(
                input_data, stepfunctions_client, step_function_arn)
            logger.info(
                f"Execução do Step Functions iniciada com sucesso. ID: {response['executionArn']}")
            upload_response['body'] = json.dumps({
                **json.loads(upload_response['body']),
                "execution_arn": response['executionArn']
            })
        except Exception as e:
            logger.error(
                f"Erro ao iniciar o Step Functions após várias tentativas: {str(e)}")
            upload_response['body'] = json.dumps(
                {'error': 'Falha ao iniciar Step Functions.'})
    else:
        logger.warning(
            "ARN do Step Functions não definido. Apenas o upload foi realizado.")

    return upload_response

# O código acima é responsável por fazer o upload de um arquivo para o Amazon S3 e iniciar a execução de um Step Functions. O Step Functions é responsável por orquestrar o processamento do arquivo, que será feito por outras lambdas.
