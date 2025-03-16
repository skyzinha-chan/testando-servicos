import json
import boto3
import time
import logging

# Configuração do logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Cliente do Step Functions
stepfunctions_client = boto3.client('stepfunctions')


def create_initial_step_functions(lambda_arns, role_arn):
    """
    Cria o Step Functions inicialmente com as Lambdas disponíveis.

    Parâmetros:
        lambda_arns (dict): Dicionário com os ARNs das Lambdas existentes.
        role_arn (str): ARN da role criada em criar_infra.

    Retorno:
        str: ARN do Step Functions criado ou None em caso de erro.
    """
    try:
        # Definição inicial do Step Functions (apenas com as Lambdas existentes)
        step_function_definition = {
            "Comment": "Fluxo de processamento de nota fiscal",
            "StartAt": "TextractLambda",
            "States": {}
        }

        # Adiciona estados apenas para as Lambdas que existem
        if 'textract_lambda' in lambda_arns:
            step_function_definition['States']['TextractLambda'] = {
                "Type": "Task",
                "Resource": lambda_arns['textract_lambda'],
                "Next": "NLPLambda"
            }

        if 'nlp_lambda' in lambda_arns:
            step_function_definition['States']['NLPLambda'] = {
                "Type": "Task",
                "Resource": lambda_arns['nlp_lambda'],
                "Next": "MoveLambda"
            }

        if 'move_lambda' in lambda_arns:
            step_function_definition['States']['MoveLambda'] = {
                "Type": "Task",
                "Resource": lambda_arns['move_lambda'],
                "Next": "ReturnResult"
            }

        # Estado final
        step_function_definition['States']['ReturnResult'] = {
            "Type": "Pass",
            "InputPath": "$.NLPLambdaResult",
            "End": True
        }

        # Criando o Step Function
        response = stepfunctions_client.create_state_machine(
            name='ProcessamentoNotasFiscais',
            # Definição completa
            definition=json.dumps(step_function_definition),
            roleArn=role_arn  # Usa o ARN da role passado como parâmetro
        )
        step_function_arn = response['stateMachineArn']
        logger.info(f"Step Function criado com ARN: {step_function_arn}")

        # Verificar se o Step Function está ativo antes de prosseguir
        wait_for_step_function(step_function_arn)

        return step_function_arn

    except Exception as e:
        logger.error(f"Erro ao criar o Step Function: {e}")
        return None


def update_step_functions(step_function_arn, lambda_arns):
    """
    Atualiza o Step Functions para incluir novas Lambdas.

    Parâmetros:
        step_function_arn (str): ARN do Step Functions existente.
        lambda_arns (dict): Dicionário com os ARNs das Lambdas atualizados.
    """
    try:
        # Obtém a definição atual do Step Functions
        describe_response = stepfunctions_client.describe_state_machine(
            stateMachineArn=step_function_arn
        )
        current_definition = json.loads(describe_response['definition'])

        # Adiciona novos estados para as Lambdas que não estavam na definição original
        if 'textract_lambda' in lambda_arns and 'TextractLambda' not in current_definition['States']:
            current_definition['States']['TextractLambda'] = {
                "Type": "Task",
                "Resource": lambda_arns['textract_lambda'],
                "Next": "NLPLambda"
            }

        if 'nlp_lambda' in lambda_arns and 'NLPLambda' not in current_definition['States']:
            current_definition['States']['NLPLambda'] = {
                "Type": "Task",
                "Resource": lambda_arns['nlp_lambda'],
                "Next": "MoveLambda"
            }

        if 'move_lambda' in lambda_arns and 'MoveLambda' not in current_definition['States']:
            current_definition['States']['MoveLambda'] = {
                "Type": "Task",
                "Resource": lambda_arns['move_lambda'],
                "Next": "ReturnResult"
            }

        # Atualiza o Step Functions
        update_response = stepfunctions_client.update_state_machine(
            stateMachineArn=step_function_arn,
            definition=json.dumps(current_definition)
        )
        logger.info(
            f"Step Functions atualizado com sucesso. Nova versão: {update_response['updateDate']}")

    except Exception as e:
        logger.error(f"Erro ao atualizar o Step Functions: {e}")


def wait_for_step_function(step_function_arn):
    """
    Aguarda até que o Step Function esteja ativo.

    Parâmetros:
        step_function_arn (str): ARN do Step Function.
    """
    while True:
        try:
            response = stepfunctions_client.describe_state_machine(
                stateMachineArn=step_function_arn
            )
            logger.info(f"Step Function está ativo. Status: {response['status']}")
            break
        except stepfunctions_client.exceptions.StateMachineDoesNotExist:
            logger.info(
                "Step Function ainda não está disponível. Aguardando...")
            time.sleep(5)  # Esperar 5 segundos antes de tentar novamente
        except Exception as e:
            logger.error(f"Erro ao verificar o Step Function: {e}")
            break
