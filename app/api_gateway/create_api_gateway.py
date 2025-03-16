# app/api_gateway/create_api_gateway.py
import boto3
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializa o cliente do API Gateway
api_gateway_client = boto3.client('apigateway')

# Configurações
api_name = 'InvoiceAPI'  # Nome do API Gateway
api_stage_name = 'prod'  # Nome do estágio (ex: prod, dev)
api_resource_path = 'api/v1/invoice'  # Caminho do recurso
region = 'us-east-1'  # Região da AWS

# Tipos de mídia binária
binary_media_types = [
    'image/jpeg',
    'image/png',
    'application/pdf',
    'multipart/form-data'
]


def create_api_gateway(lambda_function_arn, description='API para upload de arquivos'):
    try:
        # Verifica se o API Gateway já existe
        apis = api_gateway_client.get_rest_apis()['items']
        existing_api = next(
            (api for api in apis if api['name'] == api_name), None)

        if existing_api:
            api_id = existing_api['id']
            logger.info(f"API Gateway '{api_name}' já existe. ID: {api_id}")
            # Retorna a URL da API existente
            return f"https://{api_id}.execute-api.{region}.amazonaws.com/{api_stage_name}/{api_resource_path}"
        else:
            # Cria o API Gateway
            api_response = api_gateway_client.create_rest_api(
                name=api_name,
                description=description,
                version='1.0',
                binaryMediaTypes=binary_media_types  # Define os tipos de mídia binária
            )
            api_id = api_response['id']
            logger.info(
                f"API Gateway '{api_name}' criado com sucesso. ID: {api_id}")
            # Adiciona tags ao API Gateway
            tags = {
                'Name': 'InvoiceAPI',
                'Project': 'Sprint4-5-6-Grupo6',
                'CostCenter': 'CentroDeCusto123'
            }
            api_gateway_client.tag_resource(
                resourceArn=f"arn:aws:apigateway:{region}::/restapis/{api_id}",
                tags=tags
            )
            logger.info(f"Tags adicionadas ao API Gateway '{api_name}'.")

        # Obtém o ID do recurso raiz
        root_resource_id = api_gateway_client.get_resources(restApiId=api_id)[
            'items'][0]['id']

        # Cria o recurso '/api/v1/invoice'
        resource_id = root_resource_id
        for part in api_resource_path.split('/'):
            # Verifica se o recurso já existe
            resources = api_gateway_client.get_resources(restApiId=api_id)[
                'items']
            existing_resource = next(
                (res for res in resources if res.get('pathPart') == part), None)
            if existing_resource:
                resource_id = existing_resource['id']
                logger.info(f"Recurso '{part}' já existe. ID: {resource_id}")
            else:
                resource_response = api_gateway_client.create_resource(
                    restApiId=api_id,
                    parentId=resource_id,
                    pathPart=part
                )
                resource_id = resource_response['id']
                logger.info(
                    f"Recurso '{part}' criado com sucesso. ID: {resource_id}")

        # Verifica se o método POST já existe
        resource = api_gateway_client.get_resource(
            restApiId=api_id,
            resourceId=resource_id
        )
        methods = resource.get('resourceMethods', {})
        if 'POST' not in methods:
            # Cria o método POST
            api_gateway_client.put_method(
                restApiId=api_id,
                resourceId=resource_id,
                httpMethod='POST',
                authorizationType='NONE'
            )
            logger.info(
                f"Método POST criado no recurso '{api_resource_path}'.")

            # Configura a integração com a Lambda
            api_gateway_client.put_integration(
                restApiId=api_id,
                resourceId=resource_id,
                httpMethod='POST',
                type='AWS_PROXY',
                integrationHttpMethod='POST',
                uri=f"arn:aws:apigateway:{region}:lambda:path/2015-03-31/functions/{lambda_function_arn}/invocations"
            )
            logger.info(
                "Integração com Lambda s3_upload_lambda configurada para o método POST.")

        # Concede permissão para o API Gateway invocar a Lambda
        lambda_client = boto3.client('lambda')
        try:
            # Substitua {account_id} pelo ID da sua conta AWS
            account_id = boto3.client(
                'sts').get_caller_identity().get('Account')
            source_arn = f"arn:aws:execute-api:{region}:{account_id}:{api_id}/*/*/{api_resource_path}"

            lambda_client.add_permission(
                FunctionName=lambda_function_arn,
                StatementId='apigateway-invoke',
                Action='lambda:InvokeFunction',
                Principal='apigateway.amazonaws.com',
                SourceArn=source_arn
            )
            logger.info(
                "Permissão concedida para o API Gateway invocar a Lambda.")
        except lambda_client.exceptions.ResourceConflictException:
            logger.info(
                "Permissão já existe para o API Gateway invocar a Lambda.")
        except Exception as e:
            logger.error(f"Erro ao conceder permissão: {e}")

        # Implanta o API Gateway
        api_gateway_client.create_deployment(
            restApiId=api_id,
            stageName=api_stage_name
        )
        logger.info(f"API Gateway implantado no estágio '{api_stage_name}'.")

        # Retorna a URL do API Gateway
        api_url = f"https://{api_id}.execute-api.{region}.amazonaws.com/{api_stage_name}/{api_resource_path}"
        logger.info(f"API Gateway URL: {api_url}")
        return api_url

    except Exception as e:
        logger.error(f"Erro ao criar o API Gateway: {e}")
        return None


def create_api(lambda_function_arn):
    api_url = create_api_gateway(
        lambda_function_arn, description='API para upload de arquivos S3')
    if api_url:
        logger.info(f"API Gateway criado com sucesso. URL: {api_url}")
        return api_url
    else:
        logger.error("Falha ao criar o API Gateway.")
        return None


if __name__ == "__main__":
    # Obtém o ID da conta AWS
    account_id = boto3.client('sts').get_caller_identity().get('Account')
    # Exemplo de uso da função create_api
    # Substitua pelo ARN da sua Lambda
    lambda_function_arn = f'arn:aws:lambda:us-east-1:{account_id}:function:s3_upload_lambda'
    logger.info("Criando API Gateway...")
    api_url = create_api(lambda_function_arn)
    if api_url:
        logger.info(f"API Gateway criado com sucesso. URL: {api_url}")
    else:
        logger.error("Falha ao criar o API Gateway.")
