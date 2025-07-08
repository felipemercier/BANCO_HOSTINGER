from flask import Flask, jsonify, request
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Conexão com o banco de dados
def conectar():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

# Rota inicial de teste
@app.route('/')
def home():
    return 'API conectada à Hostinger!'

# Rota GET: listar produções
@app.route('/producoes', methods=['GET'])
def listar_producoes():
    conexao = conectar()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, produto, tamanho, erp_id, status, criado_em
        FROM producao
        ORDER BY criado_em DESC
    """)
    
    dados = cursor.fetchall()
    cursor.close()
    conexao.close()
    return jsonify(dados)

# Rota POST: adicionar nova produção
@app.route('/producoes', methods=['POST'])
def adicionar_producao():
    dados = request.json
    produto = dados.get('produto')
    tamanho = dados.get('tamanho')
    erp_id = dados.get('erp_id')
    status = dados.get('status')

    if not all([produto, tamanho, erp_id, status]):
        return jsonify({"erro": "Campos obrigatórios ausentes."}), 400

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO producao (produto, tamanho, erp_id, status)
        VALUES (%s, %s, %s, %s)
    """, (produto, tamanho, erp_id, status))

    conexao.commit()
    cursor.close()
    conexao.close()

    return jsonify({"mensagem": "Produção adicionada com sucesso!"}), 201

# Iniciar servidor
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
