# app/main.py
import botocore.exceptions
import os
import logging
import time
from infra.create_infra import create_infra
from create_lambdas import create_lambdas_main
# Pode ser comentado se não for usado
# Importe a função para criar o Step Functions
from step_functions.create_step_functions import create_initial_step_functions
from api_gateway.create_api_gateway import create_api
import boto3

# Configuração do logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def wait_for_lambda_creation(lambda_name, timeout=300, sleep_interval=10):
    client = boto3.client('lambda')
    start_time = time.time()

    while True:
        try:
            response = client.get_function(FunctionName=lambda_name)
            logger.info(f"Lambda {lambda_name} criada com sucesso.")
            return response
        except client.exceptions.ResourceNotFoundException:
            logger.info(
                f"Lambda {lambda_name} ainda não criada, aguardando...")
            time.sleep(sleep_interval)
            if time.time() - start_time > timeout:
                logger.error(
                    f"Timeout ao aguardar a criação da Lambda {lambda_name}.")
                raise TimeoutError(
                    f"Timeout ao aguardar a criação da Lambda {lambda_name}.")
        except botocore.exceptions.ClientError as e:
            logger.error(
                f"Erro ao verificar a criação da Lambda {lambda_name}: {str(e)}")
            raise  # Re-raise the exception to handle it further up the call stack


def create_initial_lambdas(infra_config):
    # Lambdas que já estão prontas
    lambdas_existentes = ['s3_upload_lambda', 's3_move_lambda']

    # Pegamos os valores da infraestrutura
    role_arn = infra_config['role_arn']
    bucket_lambda_code_name = infra_config['bucket_lambda_code_name']
    bucket_imagens_name = infra_config['bucket_imagens_name']
    bucket_layers_name = infra_config['bucket_layers_name']

    # Construir o caminho dinâmico para o arquivo ZIP da layer
    # Diretório atual do script (main.py)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    layer_upload_zip_path = os.path.join(
        current_dir, "layers", "upload_layer", "upload_layer.zip")

    # Verificar se o arquivo existe
    if not os.path.exists(layer_upload_zip_path):
        logger.error(f"Arquivo '{layer_upload_zip_path}' não encontrado.")
        raise FileNotFoundError(
            f"Arquivo '{layer_upload_zip_path}' não encontrado.")

    # A configuração das Lambdas será passada diretamente para a função `create_lambdas_main()`
    lambda_config = {
        'role_arn': role_arn,
        'bucket_lambda_code_name': bucket_lambda_code_name,
        'bucket_layers_name': bucket_layers_name,
        'bucket_imagens_name': bucket_imagens_name,
        'lambdas': {
            's3_upload_lambda': {
                # Caminho para o arquivo ZIP da layer
                'layer_zip_path': layer_upload_zip_path,
                'handler': 's3_upload_lambda.lambda_handler',
                'description': 'Função Lambda para upload de arquivos S3',  # Adiciona a descrição
                # Adiciona a descrição da layer
                'layer_description': 'Layer de biblioteca para upload de arquivos S3'
            },
            's3_move_lambda': {
                'layer_zip_path': None,  # Não há layer para s3_move_lambda
                'handler': 's3_move_lambda.lambda_handler',
                'description': 'Função Lambda para mover arquivos S3',  # Adiciona a descrição
                'layer_description': None  # Não há layer para esta Lambda
            }
        }
    }

    # Agora chamamos a função para criar as Lambdas
    logger.info("Criando as Lambdas a partir da configuração fornecida...")
    create_lambdas_main(lambda_config)

    # Aguardar as Lambdas serem criadas e obter o ARN
    lambda_arns = {}
    for lambda_name in lambdas_existentes:
        lambda_response = wait_for_lambda_creation(
            lambda_name)  # Espera a Lambda ser criada
        # Armazena o ARN
        lambda_arns[lambda_name] = lambda_response['Configuration']['FunctionArn']

    return lambda_arns  # Retorna os ARNs das Lambdas criadas


def create_remaining_lambdas(infra_config):
    # Defina as Lambdas que precisam ser criadas
    lambdas_futuras = ['other_lambda_1', 'other_lambda_2']

    # Pegue os valores da infraestrutura
    role_arn = infra_config['role_arn']
    bucket_lambda_code_name = infra_config['bucket_lambda_code_name']
    bucket_layers_name = infra_config['bucket_layers_name']
    bucket_imagens_name = infra_config['bucket_imagens_name']

    # A configuração das Lambdas será passada diretamente para a função `create_lambdas_main()`
    lambda_config = {
        'role_arn': role_arn,
        'bucket_lambda_code_name': bucket_lambda_code_name,
        'bucket_layers_name': bucket_layers_name,
        'bucket_imagens_name': bucket_imagens_name,
        'lambdas': {}
    }

    for lambda_name in lambdas_futuras:
        # Adiciona a configuração da Lambda à estrutura
        lambda_config['lambdas'][lambda_name] = {
            'layer_zip_path': None,  # Defina se houver uma layer
            # Defina o handler da Lambda
            'handler': f"{lambda_name}.lambda_handler"
        }

    # Agora chamamos a função para criar as Lambdas
    logger.info("Criando as Lambdas a partir da configuração fornecida...")
    create_lambdas_main(lambda_config)

    # Aguardar as Lambdas serem criadas e obter o ARN
    lambda_arns = {}
    for lambda_name in lambdas_futuras:
        lambda_arn = wait_for_lambda_creation(
            lambda_name)  # Espera a Lambda ser criada
        lambda_arns[lambda_name] = lambda_arn  # Armazena o ARN

    return lambda_arns  # Retorna os ARNs das Lambdas criadas


def update_lambda_with_step_function_arn(lambda_name, step_functions_arn):
    # Função para atualizar a Lambda com o ARN do Step Functions (comentada)
    client = boto3.client('lambda')
    client.update_function_configuration(
        FunctionName=lambda_name,
        Environment={'Variables': {'STEP_FUNCTIONS_ARN': step_functions_arn}}
    )
    logger.info(
        f"Lambda {lambda_name} atualizada com o ARN do Step Functions.")


def main():
    # Função principal que orquestra a criação de todos os recursos
    try:
        # Etapa 1: Criação da infraestrutura (S3, roles, políticas)
        logger.info("Criando a infraestrutura...")
        infra_config = create_infra()  # Agora pega a infraestrutura criada

        if not infra_config:
            logger.error("Falha ao criar a infraestrutura.")
            return

        # Etapa 2: Criação das Lambdas
        logger.info("Criando as Lambdas iniciais...")
        # Passa infra_config como argumento
        initial_lambda_arns = create_initial_lambdas(
            infra_config)  # Obtemos os ARNs das Lambdas

        # Etapa 3: Criação do Step Functions inicial
        logger.info("Criando o Step Functions inicial...")
        step_functions_arn = create_initial_step_functions(
            initial_lambda_arns, infra_config['role_arn'])
        if not step_functions_arn:
            logger.error("Falha ao criar o Step Functions inicial.")
            return

        # # Etapa 4: Criação das Lambdas restantes, podemos criar as próximas Lambdas
        # Se você não tem outras Lambdas prontas, comente a linha abaixo
        # logger.info("Criando as Lambdas restantes...")
        # remaining_lambda_arns = create_remaining_lambdas(infra_config)

        # Combine os ARNs das Lambdas COMPLETAS         all_lambda_arns = {**initial_lambda_arns, **remaining_lambda_arns}
        all_lambda_arns = initial_lambda_arns  # Use apenas as Lambdas iniciais

        # Etapa 4: Criação da API Gateway e integração com as Lambdas
        logger.info("Criando a API Gateway...")
        api_url = create_api(
            all_lambda_arns['s3_upload_lambda'])  # Passa o ARN da Lambda
        if api_url:
            logger.info(f"API Gateway criado com sucesso. URL: {api_url}")
        else:
            logger.error("Falha ao criar o API Gateway.")

        # Etapa 5: Criação do Step Functions (comentado, pois ainda está em desenvolvimento)
        # Atualiza o Step Functions com as novas Lambdas
        # logger.info("Atualizando o Step Functions com as novas Lambdas...")
        # all_lambda_arns = {**initial_lambda_arns, **remaining_lambda_arns}
        # update_step_functions(step_functions_arn, all_lambda_arns)

        # Etapa 6: Atualizar a Lambda com o ARN do Step Functions (comentado)
        # logger.info("Atualizando as Lambdas com o ARN do Step Functions...")
        # for lambda_name in all_lambda_arns.keys():
        #    update_lambda_with_step_function_arn(
        #        lambda_name, step_functions_arn)  # Atualiza cada Lambda

        logger.info(
            "Todos os recursos foram criados e configurados com sucesso.")

    except Exception as e:
        logger.error(f"Erro ao criar e configurar os recursos: {str(e)}")


# Chama a função principal para executar a criação dos recursos
if __name__ == '__main__':
    main()
