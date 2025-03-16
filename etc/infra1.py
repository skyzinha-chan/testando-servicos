# %% [markdown]
# ## 1. Organização do Projeto
#
# ### a. Jupyter Notebook (.ipynb)
#
# O Jupyter Notebook é ótimo para desenvolvimento iterativo e testes, pois permite executar células individualmente e visualizar os resultados imediatamente.
#
# No entanto, para produção ou automação, é recomendável migrar o código para arquivos `.py`.
#
# ### b. Arquivos .py
#
# Você pode dividir o código em vários arquivos `.py` para organizar melhor o projeto. Por exemplo:
#
# - **infra.py**: Para criar recursos da AWS (buckets S3, políticas IAM, roles, etc.).
# - **lambda_functions.py**: Para o código das funções Lambda.
# - **api_gateway.py**: Para configurar o API Gateway.
# - **step_functions.py**: Para definir e criar a State Machine do Step Functions.
# - **main.py**: Para orquestrar a execução dos outros scripts.

# %% [markdown]
# Configurações iniciais

# %%
import json
import boto3
pip install boto3

# %%

# Inicializa os clientes do Boto3
iam_client = boto3.client('iam')
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')

# Configurações
# Bucket para armazenar as layers
bucket_layers_name = 'sprint4-grupo6-layers'
# Bucket para armazenar o código das Lambdas
bucket_lambda_code_name = 'sprint4-grupo6-lambda-code'
# Bucket para armazenar as imagens
bucket_imagens_name = 'sprint4-grupo6-imagens'
# Role para a execução das Lambdas
role_name = 'sprint4-grupo6-lambda-role'
policy_name = 'sprint4-grupo6-lambda-policy'                # Policy com permissões


# Layer contendo a biblioteca requests
layer_name = 'sprint4-grupo6-requests-layer'
# Função Lambda para upload
lambda_function_name = 'sprint4-grupo6-upload-lambda'
# Altere para a região desejada
region = 'us-east-1'

print("Configurações definidas.")

# %% [markdown]
# Criar o bucket S3

# %%
# Criar o bucket para as layers
try:
    s3_client.create_bucket(Bucket=bucket_layers_name)
    print(f"Bucket para layers '{bucket_layers_name}' criado com sucesso.")
except Exception as e:
    print(f"Erro ao criar o bucket para layers: {e}")

# Criar o bucket para o código das Lambdas
try:
    s3_client.create_bucket(Bucket=bucket_lambda_code_name)
    print(
        f"Bucket para código das Lambdas '{bucket_lambda_code_name}' criado com sucesso.")
except Exception as e:
    print(f"Erro ao criar o bucket para código das Lambdas: {e}")

# Criar o bucket para as imagens
try:
    s3_client.create_bucket(Bucket=bucket_imagens_name)
    print(f"Bucket para imagens '{bucket_imagens_name}' criado com sucesso.")
except Exception as e:
    print(f"Erro ao criar o bucket para imagens: {e}")

# %% [markdown]
# Criar a política IAM

# %%
policy_document = {
    "Version": "2012-10-17",
    "Statement": [
        # Permissões para CloudWatch Logs
        {
            "Effect": "Allow",
            "Action": "logs:CreateLogGroup",
            "Resource": f"arn:aws:logs:{region}:961341525606:*"
        },
        {
            "Effect": "Allow",
            "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
            "Resource": [
                f"arn:aws:logs:{region}:961341525606:log-group:/aws/lambda/{lambda_function_name}:*"
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
            "Resource": [
                f"arn:aws:s3:::{bucket_layers_name}/*",
                f"arn:aws:s3:::{bucket_lambda_code_name}/*",
                f"arn:aws:s3:::{bucket_imagens_name}/*"
            ]
        },
        # Permissões para Textract
        {
            "Effect": "Allow",
            "Action": ["textract:DetectDocumentText"],
            "Resource": "*"
        },
        # Permissões para Lambda
        {
            "Effect": "Allow",
            "Action": ["lambda:InvokeFunction"],
            "Resource": [
                f"arn:aws:lambda:{region}:961341525606:function:{lambda_function_name}"
            ]
        },
        # Permissões para Step Functions (se necessário)
        {
            "Effect": "Allow",
            "Action": [
                "states:StartExecution",
                "states:DescribeExecution",
                "states:GetExecutionHistory"
            ],
            "Resource": f"arn:aws:states:{region}:961341525606:stateMachine:*"
        },
        # Permissões para API Gateway (se necessário)
        {
            "Effect": "Allow",
            "Action": [
                "apigateway:POST",
                "apigateway:GET"
            ],
            "Resource": f"arn:aws:apigateway:{region}::/restapis/*"
        }
    ]
}

print("Política definida.")

# Criar a política no IAM
try:
    response = iam_client.create_policy(
        PolicyName=policy_name,
        PolicyDocument=json.dumps(policy_document)
    )
    policy_arn = response['Policy']['Arn']
    print(f"Política '{policy_name}' criada com sucesso. ARN: {policy_arn}")
except Exception as e:
    print(f"Erro ao criar a política: {e}")

# %% [markdown]
# ## Permissões para Outras Funções Lambda
#
# A política fornecida inclui permissões para invocar a função Lambda `sprint4-grupo6-bucketlambda`. Se você tiver outras funções Lambda, precisará adicionar suas permissões ao script.

# %% [markdown]
# Criar a role IAM

# %%
# Definir a política de confiança da role
assume_role_policy_document = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}

# Criar a role
try:
    response = iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(assume_role_policy_document))
    role_arn = response['Role']['Arn']
    print(f"Role '{role_name}' criada com sucesso. ARN: {role_arn}")
except Exception as e:
    print(f"Erro ao criar a role: {e}")

# %% [markdown]
# Anexar a política à role

# %%
# Anexar a política à role
try:
    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn=policy_arn
    )
    print(f"Política '{policy_name}' anexada à role '{role_name}'.")
except Exception as e:
    print(f"Erro ao anexar a política à role: {e}")

# %% [markdown]
# Fazer upload do arquivo ZIP para o bucket S3 - Fazer upload da layer para o S3

# %%
# Caminho para o arquivo ZIP da layer
layer_zip_path = r'C:\Users\aishi\Documentos\Talita\Estágio\Sprint 4\Bucket S3 API REST\lambda_layers\layer_requests\output\my_lambda_layer.zip'
s3_layers_key = 'layers/my_lambda_layer.zip'

# Fazer upload do arquivo ZIP para o bucket de layers
try:
    s3_client.upload_file(layer_zip_path, bucket_layers_name, s3_layers_key)
    print(
        f"Arquivo '{layer_zip_path}' enviado para o bucket '{bucket_layers_name}' com a chave '{s3_layers_key}'.")
except Exception as e:
    print(f"Erro ao fazer upload do arquivo da layer: {e}")

# %% [markdown]
# Publicar a layer

# %%
# Publicar a layer
try:
    response = lambda_client.publish_layer_version(
        LayerName=layer_name,
        Content={
            'S3Bucket': bucket_layers_name,
            'S3Key': s3_layers_key
        },
        # Runtime atualizado para Python 3.12
        CompatibleRuntimes=['python3.12'],
        Description='Layer contendo a biblioteca requests'
    )
    layer_version_arn = response['LayerVersionArn']
    print(
        f"Layer '{layer_name}' publicada com sucesso. ARN: {layer_version_arn}")
except Exception as e:
    print(f"Erro ao publicar a layer: {e}")

# %% [markdown]
# ## Criar a Função Lambda
#
# Na AWS Lambda, o código da função precisa ser enviado como um arquivo ZIP (ou diretamente via editor de código no Console da AWS, mas isso é limitado). Se o seu código Lambda está em um arquivo `.py`, você precisa compactá-lo em um arquivo ZIP antes de enviá-lo para a Lambda. Vou explicar como fazer isso e como ajustar o script para enviar o arquivo ZIP.
#
# ### Por que enviar um arquivo ZIP?
#
# A AWS Lambda exige que o código seja enviado em um pacote, que pode ser:
#
# - Um arquivo ZIP contendo o código e as dependências.
# - Um diretório de camadas (layers) para dependências compartilhadas.
#
# No seu caso, como você já tem uma layer para a biblioteca `requests`, basta compactar o arquivo `.py` da sua função Lambda em um arquivo ZIP.
#
# ### Passo a passo para criar o arquivo ZIP
#
# #### Estrutura do arquivo ZIP:
#
# Se o seu código Lambda está em um arquivo chamado `lambda_function.py`, o arquivo ZIP deve conter esse arquivo na raiz.
#
# **Exemplo de estrutura:**
# ```lambda_function.py```
#
#

# %% [markdown]
# ### Como compactar:
#
# #### No Windows
#
# Você pode usar o Explorador de Arquivos para compactar o arquivo:
#
# 1. Selecione o arquivo `lambda_function.py`.
# 2. Clique com o botão direito e escolha **"Enviar para" > "Pasta compactada"**.
# 3. Um arquivo ZIP será criado no mesmo local.
#
# #### No terminal (Linux/Mac/WSL)
#
# Você pode usar o seguinte comando:
#
# ```bash
# zip lambda_function.zip sua_lambda_function.py

# %%
zip s3_upload_lambda.zip s3_upload_lambda.py

# %% [markdown]
# ### Fazer upload do código da Lambda para o S3

# %%
# Caminho para o arquivo ZIP do código da Lambda
lambda_zip_path = r'C:\Users\aishi\Documentos\Talita\Estágio\Sprint 4\Bucket S3 API REST\app\lambda_functions\s3_upload_lambda.zip'
s3_lambda_key = 'lambda/s3_upload_lambda.zip'  # Chave no S3

# Fazer upload do código da Lambda para o bucket de código das Lambdas
try:
    s3_client.upload_file(
        lambda_zip_path, bucket_lambda_code_name, s3_lambda_key)
    print(
        f"Arquivo '{lambda_zip_path}' enviado para o bucket '{bucket_lambda_code_name}' com a chave '{s3_lambda_key}'.")
except Exception as e:
    print(f"Erro ao fazer upload do arquivo Lambda: {e}")

# %% [markdown]
# ## Criar a função Lambda

# %%
# Criar a função Lambda
try:
    response = lambda_client.create_function(
        FunctionName=lambda_function_name,
        Runtime='python3.12',  # Runtime atualizado para Python 3.12
        Role=role_arn,
        Handler='s3_upload_lambda.lambda_handler',  # Altere para o handler correto
        Code={
            'S3Bucket': bucket_lambda_code_name,
            'S3Key': s3_lambda_key
        },
        Layers=[layer_version_arn],  # Associar a layer
        Timeout=30,
        MemorySize=128,
        Environment={
            'Variables': {
                'SOURCE_BUCKET': bucket_imagens_name  # Bucket para salvar as imagens
            }
        }
    )
    lambda_arn = response['FunctionArn']
    print(
        f"Função Lambda '{lambda_function_name}' criada com sucesso. ARN: {lambda_arn}")
except Exception as e:
    print(f"Erro ao criar a função Lambda: {e}")

# %% [markdown]
# ## Próximos passos
#
# Após criar a função Lambda, você pode testá-la no Console da AWS Lambda ou usando o SDK da AWS.
#
# Se precisar adicionar mais dependências, você pode incluí-las na layer ou no próprio pacote ZIP da Lambda.

# %% [markdown]
# ## 2. Migrando do Jupyter Notebook para Arquivos .py
#
# ### a. Exportar o Notebook para .py
#
# No Jupyter Notebook, vá em **File > Download as > Python (.py)**.
#
# Isso gerará um arquivo `.py` com todo o código do notebook.
#
# ### b. Dividir o Código
#
# Separe o código em arquivos menores, conforme a funcionalidade (como sugerido acima).
#
# Por exemplo, o código para criar a infraestrutura (buckets, políticas, roles) pode ir no `infra.py`.
#
# ### c. Exemplo de Estrutura de Projeto
#

# %% [markdown]
# ## 3. Executando o Projeto
#
# ### a. Execução Única
#
# Se você quiser executar tudo de uma vez, crie um script principal (`main.py`) que chama os outros scripts na ordem correta.
#
# **Exemplo de `main.py`:**
#
# ```python
# from infra import criar_infraestrutura
# from lambda_functions import criar_lambdas
# from api_gateway import criar_api_gateway
# from step_functions import criar_step_functions
#
# if __name__ == "__main__":
#     # Cria a infraestrutura (buckets, políticas, roles)
#     criar_infraestrutura()
#
#     # Cria as funções Lambda
#     criar_lambdas()
#
#     # Cria o API Gateway
#     criar_api_gateway()
#
#     # Cria a State Machine do Step Functions
#     criar_step_functions()
#
#     print("Todos os recursos foram criados com sucesso!")
