from flask import Flask, jsonify
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

def conectar():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

@app.route('/')
def home():
    return 'API conectada à Hostinger!'

@app.route('/producoes')
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
