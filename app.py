from flask import Flask, jsonify, request
from flask_cors import CORS
from mysql.connector.pooling import MySQLConnectionPool
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuração do pool de conexões
config = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}

pool = MySQLConnectionPool(pool_name="martier_pool", pool_size=10, **config)

# Rota de teste
@app.route('/')
def home():
    return 'API conectada à Hostinger!'

# Rota GET: listar produções
@app.route('/producoes', methods=['GET'])
def listar_producoes():
    try:
        conn = pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, produto, tamanho, erp_id, status, criado_em
            FROM producao
            ORDER BY criado_em DESC
        """)
        dados = cursor.fetchall()
        return jsonify(dados)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

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

    try:
        conn = pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO producao (produto, tamanho, erp_id, status)
            VALUES (%s, %s, %s, %s)
        """, (produto, tamanho, erp_id, status))
        conn.commit()
        return jsonify({"mensagem": "Produção adicionada com sucesso!"}), 201
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Rota PUT: atualizar status da produção
@app.route('/producoes/<int:id>', methods=['PUT'])
def atualizar_status(id):
    dados = request.json
    novo_status = dados.get('status')

    if not novo_status:
        return jsonify({"erro": "Status ausente."}), 400

    try:
        conn = pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE producao SET status = %s WHERE id = %s", (novo_status, id))
        conn.commit()
        return jsonify({"mensagem": "Status atualizado com sucesso!"})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Iniciar servidor
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
