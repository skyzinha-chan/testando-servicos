# Use uma imagem base do Python 3.12
FROM python:3.12-slim

# Crie um diretório para a camada
WORKDIR /layer

# Crie um subdiretório para a biblioteca
RUN mkdir python

# Instale a biblioteca requests_toolbelt no diretório python
RUN pip install requests_toolbelt -t python/

# Instale o zip
RUN apt-get update && apt-get install -y zip

# Compacte o diretório python em um arquivo ZIP
RUN zip -r my_lambda_layer.zip python