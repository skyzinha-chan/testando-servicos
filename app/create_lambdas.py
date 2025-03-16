# app/create_lambdas.py
import boto3
import os
import zipfile
import time
import logging


# Configuração do logger (ajustado para produção)
logger = logging.getLogger()
logger.setLevel(logging.WARNING)  # Apenas warning e erros em produção


def zip_lambda(lambda_name, source_file):
    # Função para compactar os arquivos das Lambdas
    zip_filename = f"{lambda_name}.zip"
    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        zipf.write(source_file, os.path.basename(source_file))
    return zip_filename


def get_s3_file_content(bucket_name, key):
    s3_client = boto3.client('s3')
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        return response['Body'].read()  # Retorna o conteúdo do arquivo
    except Exception as e:
        logger.error(f"Erro ao obter o arquivo do S3: {e}")
        return None


def compare_zip_files(local_zip_path, bucket_name, s3_key):
    with open(local_zip_path, 'rb') as local_file:
        local_content = local_file.read()

    s3_content = get_s3_file_content(bucket_name, s3_key)

    if s3_content is None:
        return False  # Não foi possível obter o conteúdo do S3

    return local_content == s3_content


def upload_to_s3(bucket_name, file_name, key):
    # Verifica se o arquivo já foi enviado
    if compare_zip_files(file_name, bucket_name, key):
        logger.info(
            f"O arquivo '{file_name}' não foi alterado. Pulando o upload.")
        return

    # Se o arquivo local for diferente, faça o upload
    # Função para enviar os arquivos para o S3
    s3_client = boto3.client('s3')
    try:
        s3_client.upload_file(file_name, bucket_name, key)
        logger.info(f"Arquivo '{file_name}' enviado para o S3 com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao enviar o arquivo '{file_name}' para o S3: {e}")


def create_lambda(lambda_name, role_arn, bucket_lambda_code_name, bucket_layers_name, layer_zip_path, bucket_imagens_name, layer_description, handler, description):
    # Função para criar uma Lambda
    lambda_client = boto3.client('lambda')

    # Compactar o arquivo da Lambda
    zip_filename = zip_lambda(lambda_name, f"lambdas/{lambda_name}.py")

    # Enviar o arquivo .zip para o S3
    upload_to_s3(bucket_lambda_code_name, zip_filename, f"{lambda_name}.zip")

    # Se layer_zip_path não for None, faça o upload da layer
    if layer_zip_path:
        # Nome da layer associado à Lambda
        layer_key = f"layers/{lambda_name}-layer.zip"
        upload_to_s3(bucket_layers_name, layer_zip_path, layer_key)

        # Criar a layer
        layer_arn = create_layer(
            # Nome da layer, que inclui o nome da Lambda para clareza
            layer_name=f"{lambda_name}-layer",
            bucket_name=bucket_layers_name,
            zip_file=layer_key,  # Usar a chave do arquivo no S3
            description=layer_description  # Passando a descrição da layer
        )
    else:
        layer_arn = None  # Defina como None se não houver layer

    # Verificar se a função Lambda já existe
    try:
        lambda_client.get_function(FunctionName=lambda_name)
        logger.info(f"Função Lambda '{lambda_name}' já existe. Atualizando...")

        # Aguardar até que a função Lambda não esteja em estado de atualização
        while True:
            function_config = lambda_client.get_function_configuration(
                FunctionName=lambda_name)
            if function_config['State'] == 'Active':
                break
            logger.info(
                f"Aguardando conclusão da atualização da função Lambda '{lambda_name}'...")
            time.sleep(5)

        # Atualizar o código da função Lambda
        response = lambda_client.update_function_code(
            FunctionName=lambda_name,
            S3Bucket=bucket_lambda_code_name,
            S3Key=f"{lambda_name}.zip"
        )

        # Atualizar a configuração da função Lambda
        lambda_client.update_function_configuration(
            FunctionName=lambda_name,
            Environment={
                'Variables': {
                    'SOURCE_BUCKET': bucket_imagens_name,
                    'STEP_FUNCTIONS_ARN': ''  # Placeholder ou vazio por enquanto
                }
            }
        )
        logger.info(f"Função Lambda '{lambda_name}' atualizada com sucesso.")
    except lambda_client.exceptions.ResourceNotFoundException:
        logger.info(f"Função Lambda '{lambda_name}' não existe. Criando...")
        # Criar a função Lambda
        response = lambda_client.create_function(
            FunctionName=lambda_name,
            Runtime='python3.12',
            Role=role_arn,
            Handler=handler,
            Code={
                'S3Bucket': bucket_lambda_code_name,
                'S3Key': f"{lambda_name}.zip"
            },
            Timeout=30,
            MemorySize=128,
            Layers=[layer_arn] if layer_arn else [],
            Environment={
                'Variables': {
                    'SOURCE_BUCKET': bucket_imagens_name,
                    'STEP_FUNCTIONS_ARN': ''  # Placeholder ou vazio por enquanto
                }
            },
            Description=description  # Adiciona a descrição aqui
        )
        logger.info(f"Função Lambda '{lambda_name}' criada com sucesso.")
        # Adiciona tags à função Lambda
        tags = {
            'Name': lambda_name,
            'Project': 'Sprint4-5-6-Grupo6',
            'CostCenter': 'CentroDeCusto123'
        }
        lambda_client.tag_resource(
            Resource=response['FunctionArn'],
            Tags=tags
        )
        logger.info(f"Tags adicionadas à função Lambda '{lambda_name}'.")

    except Exception as e:
        logger.error(
            f"Erro ao criar/atualizar a função Lambda '{lambda_name}': {e}")
        return None

    return response['FunctionArn']

# Função para criar uma layer


def create_layer(layer_name, bucket_name, zip_file, description="Layer para Lambda", compatible_runtimes=['python3.12'], compatible_architectures=['x86_64']):
    lambda_client = boto3.client('lambda')
    try:
        response = lambda_client.publish_layer_version(
            LayerName=layer_name,  # Nome da layer
            Description=description,
            Content={
                'S3Bucket': bucket_name,
                'S3Key': zip_file
            },
            CompatibleRuntimes=compatible_runtimes,
            CompatibleArchitectures=compatible_architectures
        )
        layer_arn = response['LayerVersionArn']
        print(f"Layer '{layer_name}' criada com sucesso. ARN: {layer_arn}")
        return layer_arn
    except Exception as e:
        print(f"Erro ao criar a layer '{layer_name}': {e}")
        return None

# Função principal para ser chamada pelo main.py (será removido depois)


def create_lambdas_main(lambda_config):
    role_arn = lambda_config.get('role_arn')
    bucket_lambda_code_name = lambda_config.get('bucket_lambda_code_name')
    bucket_layers_name = lambda_config.get('bucket_layers_name')
    bucket_imagens_name = lambda_config.get('bucket_imagens_name')

    for lambda_name, config in lambda_config['lambdas'].items():
        create_lambda(
            lambda_name=lambda_name,
            role_arn=role_arn,
            bucket_lambda_code_name=bucket_lambda_code_name,
            bucket_layers_name=bucket_layers_name,
            layer_zip_path=config['layer_zip_path'],
            handler=config['handler'],
            bucket_imagens_name=bucket_imagens_name,
            # Passando a descrição da layer
            layer_description=config.get(
                'layer_description', 'Layer para Lambda'),
            # Adiciona a descrição aqui
            description=config.get(
                'description', f'Função Lambda para {lambda_name}')
        )


'''
O código que adicionado no final do criar_lambdas.py para testar a criação
da função Lambda de upload é apenas para fins de teste. 
Quando tudo estiver pronto e o main.py estiver configurado para 
orquestrar a criação das Lambdas e layers, REMOVA esse trecho de teste.

Após remover o trecho de teste, o criar_lambdas.py deve conter apenas 
as funções (zip_lambda, upload_to_s3, criar_lambda, criar_layer, criar_lambdas_main), 
sem o bloco if __name__ == "__main__":. Caso queira testar o arquivo INDIVIDUALMENTE então MANTENHA

O main.py será o único ponto de entrada do projeto, 
responsável por orquestrar a criação de toda a infraestrutura.

'''
if __name__ == "__main__":
    # Obtém o ID da conta AWS
    account_id = boto3.client('sts').get_caller_identity().get('Account')
    # Exemplo de configuração para criar Lambdas
    lambda_config = {
        # Substitua pelo ARN da sua role
        'role_arn': F'arn:aws:iam::{account_id}:role/sprint4-grupo6-lambda-api-step-role',
        # Substitua pelo nome do seu bucket
        'bucket_lambda_code_name': 'sprint4-grupo6-lambda-code-talita',
        # Substitua pelo nome do seu bucket de layers
        'bucket_layers_name': 'sprint4-grupo6-layers-talita',
        # Substitua pelo nome do seu bucket de imagens
        'bucket_imagens_name': 'sprint4-grupo6-imagens-talita',
        'lambdas': {
            's3_upload_lambda': {
                'layer_zip_path': 'app/layers/upload_layer/upload_layer.zip',
                'handler': 's3_upload_lambda.lambda_handler',
                'description': 'Função Lambda para upload de arquivos S3',
                'layer_description': 'Layer de biblioteca para upload de arquivos S3'
            }
        }
    }

    logger.info("Criando Lambdas com a configuração fornecida...")
    create_lambdas_main(lambda_config)
