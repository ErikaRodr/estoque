from flask import Flask, Response, redirect, render_template, request, flash, url_for
import os
import pandas as pd
import mysql.connector
from PIL import Image
import qrcode
import cv2
import base64
import numpy as np
import configparser
from unidecode import unidecode

# Leitura das configurações do arquivo ini
config = configparser.ConfigParser()
config.read('config.ini')

# Configuração do Banco de Dados
db_config = {
    'host': config['database']['host'],
    'database': config['database']['database'],
    'user': config['database']['user'],
    'password': config['database']['password']
}

try:
    with mysql.connector.connect(**db_config) as conexao:
       
        if conexao.is_connected():
            cursor = conexao.cursor()

except mysql.connector.Error as err:
    print(f"Erro ao conectar ao banco de dados: {err}")

finally:
    if 'conexao' in locals() and conexao.is_connected():
        conexao.close()
        cursor.close()

estoque = []

# Carregar a planilha de estoque se existir, ou criar uma nova
planilha_estoque_path = 'inventario/estoque.xlsx'
try:
    if os.path.exists(planilha_estoque_path):
        df_estoque = pd.read_excel(planilha_estoque_path)
    else:
        df_estoque = pd.DataFrame(columns=['produto', 'tamanho', 'cor', 'tecido', 'preco', 'nome_arquivo'])
except Exception as e:
    print(f"Erro ao carregar a planilha: {str(e)}")
    df_estoque = pd.DataFrame(columns=['produto', 'tamanho', 'cor', 'tecido', 'preco', 'nome_arquivo'])

    # Função para validar entrada contendo apenas letras
def validar_letras(entrada):
    return entrada.isalpha()

# Função para validar entrada de tamanho
def validar_tamanho(tamanho):
    tamanhos_validos = ['P', 'M', 'G', 'GG', 'XG', 'XGG']
    return tamanho.upper() if tamanho.upper() in map(str.upper, tamanhos_validos) else None

# Função para formatar nome de arquivo
def formatar_nome_arquivo(nome):
    nome_sem_acentuacao = unidecode(nome)  # Remove acentuação
    nome_minusculo = nome_sem_acentuacao.lower()  # Converte para minúsculas
    return nome_minusculo + '.png'  # Adiciona extensão .png


app = Flask(__name__)
app.secret_key = 'casualive'


@app.route('/')
def index():
    nome = "Home"
    return render_template('index.html', nome=nome)

@app.route('/ler_qr')
def ler_qr():
    nome = "Leitor QR-Code"
    return render_template('ler_qr.html', nome=nome)

def processar_frame(frame):
    # Converta o frame para tons de cinza
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Use o detector de QR code do OpenCV
    qr_decoder = cv2.QRCodeDetector()
    retval, points, straight_qrcode = qr_decoder.detectAndDecodeMulti(gray)
    
    # Se um QR code for detectado, retorne as informações
    if points is not None:
        qr_info = retval.strip()
        return qr_info
    
    return None

@app.route('/processar_qr_camera', methods=['POST'])
def processar_qr_camera():
    # Inicialize a câmera traseira
    camera = cv2.VideoCapture(0)

    while True:
        # Capture um frame da câmera
        ret, frame = camera.read()
        if not ret:
            continue

        # Processar o frame
        qr_info = processar_frame(frame)
        if qr_info:
            # Se um QR code for detectado, pare o loop
            break

        # Exibir o frame na página
        ret, frame_encoded = cv2.imencode('.jpg', frame)
        frame_base64 = base64.b64encode(frame_encoded).decode('utf-8')
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_base64.encode('utf-8') + b'\r\n')

    # Libere a câmera
    camera.release()

    # Processar as informações do QR code
    # Aqui você pode fazer o que desejar com as informações do QR code
    flash(f"Informações do QR code: {qr_info}", "success")

    # Redirecionar para a página principal
    return redirect(url_for('index'))

@app.route('/video_feed')
def video_feed():
    return Response(processar_qr_camera(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/gerar_qr', methods=['GET', 'POST'])
def gerar_qr():
    if request.method == 'POST':
        try:
            produto = request.form['produto'].strip()
            tamanho = request.form['tamanho'].strip()
            cor = request.form['cor'].strip()
            tecido = request.form['tecido'].strip()
            preco = float(request.form['preco'])
        except ValueError as e:
            flash(f"Erro de validação: {str(e)}", "error")
            return render_template('gerar_qr.html')

        # Validar entradas
        if not (validar_letras(produto) and validar_letras(cor) and validar_letras(tecido)):
            flash("Entradas inválidas. Utilize apenas letras para produto, cor e tecido.", "error")
            return render_template('gerar_qr.html')

        tamanho_valido = validar_tamanho(tamanho)
        if tamanho_valido is None:
            flash("Tamanho inválido. Utilize P, M, G, GG, XG ou XGG.", "error")
            return render_template('gerar_qr.html')

        dados = f'Produto: {produto}, Tamanho: {tamanho}, Cor: {cor}, Tecido: {tecido}, Preço: {preco}'
        nome_arquivo = formatar_nome_arquivo(f'{produto}_{tamanho}_{cor}_{tecido}')

        try:
            # Gerar QR Code usando Pillow
            qr = qrcode.make(dados)
            caminho_arquivo = os.path.join('static', nome_arquivo)
            qr.save(caminho_arquivo)
        except Exception as e:
            flash(f"Erro ao gerar QR Code: {str(e)}", "error")
            return render_template('gerar_qr.html')

        estoque.append({
            'produto': produto,
            'tamanho': tamanho,
            'cor': cor,
            'tecido': tecido,
            'preco': preco,
            'nome_arquivo': nome_arquivo
        })

        flash("QR Code gerado com sucesso!", "success")
        return render_template('gerar_qr.html', qr_code=True, nome_arquivo=nome_arquivo)

    nome = "Gerador QR Code"
    return render_template('gerar_qr.html', nome=nome)

if __name__ == '__main__':
    app.run()

