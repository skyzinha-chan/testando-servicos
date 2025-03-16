# app/infra/criar_infra.py  Criando infraestrutura no AWS com Boto3.
import boto3
import json
import logging
import botocore.exceptions

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializa os clientes do Boto3
iam_client = boto3.client('iam')
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')
sts_client = boto3.client('sts')  # Cliente para obter o ID da conta

# Configurações

# Bucket para armazenar as layers
# BUCKETS PRECISAM TER NOMES ÚNICOS
bucket_layers_name = 'sprint4-grupo6-layers-talita'
# Bucket para armazenar o código das Lambdas
bucket_lambda_code_name = 'sprint4-grupo6-lambda-code-talita'
# Bucket para armazenar as imagens
bucket_imagens_name = 'sprint4-grupo6-imagens-talita'
# Role para a execução das Lambdas
role_name = 'sprint4-grupo6-lambda-api-step-role'
# Policy com permissões
policy_name = 'sprint4-grupo6-lambda-api-step-policy'

# Altere para a região desejada
region = 'us-east-1'

logger.info("Configurações definidas.")


def get_id_account_aws():
    try:
        response = sts_client.get_caller_identity()
        account_id = response['Account']
        return account_id
    except botocore.exceptions.ClientError as e:
        logger.error(f"Erro ao obter o ID da conta AWS: {e}")
        return None


def bucket_exists(bucket_name):
    """Verifica se um bucket S3 já existe."""
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        return True
    except botocore.exceptions.ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            return False  # Bucket não existe
        elif error_code == '403':
            logger.error(
                f"Permissão negada para acessar o bucket '{bucket_name}'.")
            return False  # Permissão negada
        logger.error(f"Erro ao verificar o bucket '{bucket_name}': {e}")
        return False  # Erro desconhecido


def create_s3_bucket(bucket_name, description=None):
    """
    Cria um bucket S3 na região especificada.

    Args:
        bucket_name (str): Nome do bucket a ser criado.

    Returns:
        bool: True se o bucket foi criado com sucesso, False caso contrário.
    """
    if bucket_exists(bucket_name):
        logger.warning(f"Bucket '{bucket_name}' já existe.")
        return True
    try:
        create_bucket_params = {"Bucket": bucket_name}
        if region != "us-east-1":
            create_bucket_params["CreateBucketConfiguration"] = {
                'LocationConstraint': region}

        s3_client.create_bucket(**create_bucket_params)
        logger.info(f"Bucket '{bucket_name}' criado com sucesso.")
        # Adiciona a descrição como uma tag
        if description:
            tagging = {
                'TagSet': [
                    {
                        'Key': 'Description',
                        'Value': description
                    }
                ]
            }
            s3_client.put_bucket_tagging(Bucket=bucket_name, Tagging=tagging)
            logger.info(
                f"Tag de descrição adicionada ao bucket '{bucket_name}'.")

        return True
    except botocore.exceptions.ClientError as e:
        logger.error(f"Erro ao criar o bucket '{bucket_name}': {e}")
        return False


def create_s3_folder(bucket_name, folder_name):
    """
    Cria uma pasta (prefixo) em um bucket S3.

    Args:
        bucket_name (str): Nome do bucket S3.
        folder_name (str): Nome da pasta a ser criada.

    Returns:
        bool: True se a pasta foi criada com sucesso, False caso contrário.
    """
    try:
        s3_client.put_object(Bucket=bucket_name, Key=f"{folder_name}/")
        logger.info(
            f"Pasta '{folder_name}/' criada no bucket '{bucket_name}'.")
        return True
    except botocore.exceptions.ClientError as e:
        logger.error(
            f"Erro ao criar a pasta '{folder_name}/' no bucket '{bucket_name}': {e}")
        return False


def get_policy_arn(policy_name, account_id):
    """Verifica se uma política IAM já existe e retorna seu ARN."""
    policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"
    try:
        iam_client.get_policy(PolicyArn=policy_arn)
        return policy_arn
    except iam_client.exceptions.NoSuchEntityException:
        return None
    except botocore.exceptions.ClientError as e:
        logger.error(f"Erro ao verificar a política IAM: {e}")
        return None


def create_iam_policy(policy_name, account_id, buckets):
    """
    Cria uma política IAM com as permissões especificadas.

    Args:
        policy_name (str): Nome da política a ser criada.
        account_id (str): ID da conta AWS.
        region (str): Região AWS.
        buckets (list): Lista de nomes de buckets S3.
        bucket_imagens_name (str): Nome do bucket específico para imagens.
        step_function_arn (str): ARN do Step Functions específico.
        api_gateway_arn (str): ARN do API Gateway.

    Returns:
        str: ARN da política criada, ou None em caso de erro.
    """
    policy_arn = get_policy_arn(policy_name, account_id)
    if policy_arn:
        logger.info(
            f"A política '{policy_name}' já existe. Usando ARN: {policy_arn}")
        return policy_arn

    bucket_arns = [f"arn:aws:s3:::{bucket_name}" for bucket_name, _ in buckets]

    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            # Permissões para CloudWatch Logs (Lambdas)
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/lambda/*:*"
                ]
            },
            # Permissões para CloudWatch Logs (API Gateway)
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams"
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:API-Gateway-Execution-Logs_*/*"
                ]
            },
            # Permissões para S3
            {
                "Effect": "Allow",
                "Action": [
                    "s3:PutObject",
                    "s3:PutObjectAcl",
                    "s3:GetObject",
                    "s3:DeleteObject",
                    "s3:CopyObject"
                ],
                "Resource":  [f"{bucket_arn}/*" for bucket_arn in bucket_arns]
            },
            # Permissões para Textract
            {
                "Effect": "Allow",
                "Action": [
                    "textract:DetectDocumentText",
                    "textract:AnalyzeExpense"],
                "Resource": f"arn:aws:s3:::{bucket_imagens_name}/*"
            },
            # Permissão para invocar Lambdas
            {
                "Effect": "Allow",
                "Action": ["lambda:InvokeFunction"],
                "Resource": [
                    f"arn:aws:lambda:{region}:{account_id}:function:*"
                ]
            },
            # Permissões para o Step Functions E para o API Gateway
            {
                "Effect": "Allow",
                "Action": [
                    "states:StartExecution",
                    "states:DescribeExecution",
                    "states:StopExecution"
                ],
                "Resource": f"arn:aws:states:{region}:{account_id}:stateMachine:*"
            },
            # Permissões para acessar as layers
            {
                "Effect": "Allow",
                "Action": "lambda:GetLayerVersion",
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "apigateway:POST",
                    "apigateway:GET",
                    "apigateway:PUT",
                    "apigateway:DELETE",
                    "apigateway:PATCH"
                ],
                "Resource": "*"
            }
        ]
    }

    logger.info("Política definida.")

    try:
        response = iam_client.create_policy(
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        policy_arn = response['Policy']['Arn']
        logger.info(
            f"Política '{policy_name}' criada com sucesso. ARN: {policy_arn}")
        return policy_arn
    except botocore.exceptions.ClientError as e:
        logger.error(f"Erro ao criar a política: {e}")
        return None


def attach_policy_to_role(role_name, policy_arn):
    """Anexa uma política a uma role IAM."""
    try:
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn=policy_arn)
        logger.info(f"Política '{policy_arn}' anexada à role '{role_name}'.")
        return True
    except botocore.exceptions.ClientError as e:
        logger.error(f"Erro ao anexar a política à role: {e}")
        return False


def role_exists(role_name):
    """Verifica se uma role IAM já existe."""
    try:
        iam_client.get_role(RoleName=role_name)
        return True  # A role existe
    except iam_client.exceptions.NoSuchEntityException:
        return False  # A role não existe
    except botocore.exceptions.ClientError as e:
        logger.error(f"Erro ao verificar a role '{role_name}': {e}")
        return False  # Erro desconhecido


def create_iam_role(role_name):
    """Cria uma role IAM para execução das funções Lambda e Step Functions."""
    assume_role_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": [
                        "lambda.amazonaws.com",  # Permite que o Lambda assuma a role
                        "apigateway.amazonaws.com",  # Permite que o API Gateway assuma a role
                        "states.amazonaws.com"  # Permite que o Step Functions assuma a role
                    ]
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }

    try:
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy_document))
        role_arn = response['Role']['Arn']
        logger.info(f"Role '{role_name}' criada com sucesso. ARN: {role_arn}")
        return role_arn
    except botocore.exceptions.ClientError as e:
        logger.error(f"Erro ao criar a role: {e}")
        return None


def get_role_arn(role_name):
    """Obtém o ARN de uma role IAM existente."""
    try:
        response = iam_client.get_role(RoleName=role_name)
        return response['Role']['Arn']
    except iam_client.exceptions.NoSuchEntityException:
        return None
    except botocore.exceptions.ClientError as e:
        logger.error(f"Erro ao obter a role '{role_name}': {e}")
        return None


def create_infra():
    """Cria toda a infraestrutura necessária na AWS."""
    account_id = get_id_account_aws()
    if not account_id:
        return None

    # Criar os buckets S3
    buckets = [
        (bucket_layers_name, 'Bucket para armazenar as layers da aplicação'),
        (bucket_lambda_code_name, 'Bucket para armazenar o código das Lambdas'),
        (bucket_imagens_name, 'Bucket para armazenar as imagens da aplicação')
    ]
    for bucket_name, description in buckets:
        if not create_s3_bucket(bucket_name, description):
            logger.error(f"Falha ao criar o bucket: {bucket_name}")

    # Criar as pastas 'dinheiro' e 'outros' dentro do bucket de imagens
    folders = ['dinheiro', 'outros']
    for folder in folders:
        if not create_s3_folder(bucket_imagens_name, folder):
            return None

    # Verifica se a política IAM já existe
    policy_arn = get_policy_arn(policy_name, account_id)
    if not policy_arn:
        # Criar a política IAM se não existir
        policy_arn = create_iam_policy(policy_name, account_id, buckets)
        if not policy_arn:
            return None

# Verifica se a role IAM já existe
    if not role_exists(role_name):
        # Criar a role IAM se não existir
        role_arn = create_iam_role(role_name)
        if not role_arn:
            return None
    else:
        logger.info(f"A role '{role_name}' já existe.")
        role_arn = get_role_arn(role_name)  # Obter o ARN da role existente

    # Anexar a política à role
    if not attach_policy_to_role(role_name, policy_arn):
        return None

    # Retornar resultados
    return {
        "role_arn": role_arn,
        "bucket_lambda_code_name": bucket_lambda_code_name,
        "bucket_imagens_name": bucket_imagens_name,
        "bucket_layers_name": bucket_layers_name,
        "account_id": account_id
    }


if __name__ == "__main__":
    infra_result = create_infra()
    if infra_result:
        logger.info(f"Role ARN: {infra_result['role_arn']}")
        logger.info(
            f"Bucket Lambda Code Name: {infra_result['bucket_lambda_code_name']}")
        logger.info(
            f"Bucket Imagens Name: {infra_result['bucket_imagens_name']}")
        logger.info(
            f"Bucket Layers Name: {infra_result['bucket_layers_name']}")
        logger.info(f"Account ID: {infra_result['account_id']}")
    else:
        logger.error("Falha ao criar a infraestrutura.")

"""
Documentação do criar_infra.py

Descrição:
Este script é responsável por criar a infraestrutura inicial necessária no AWS para o funcionamento do projeto.
Ele utiliza a biblioteca Boto3 (SDK da AWS para Python) para criar recursos como:
- Buckets S3 (para layers, código Lambda e imagens).
- IAM Role e Policy (para permissões das funções Lambda).
- Obtém dinamicamente o ID da conta AWS para garantir que as políticas e roles sejam criadas corretamente.

Quando será usado:
1. Primeira execução do projeto: Para criar todos os recursos necessários na AWS.
2. Ambientes de desenvolvimento e teste: Para recriar a infraestrutura em contas de teste.
3. CI/CD: Em pipelines de integração contínua/entrega contínua.
4. Recuperação de infraestrutura: Em caso de exclusão acidental dos recursos.

"""
