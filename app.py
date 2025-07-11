from flask import Flask, jsonify, request
from flask_cors import CORS
from mysql.connector.pooling import MySQLConnectionPool
from mysql.connector import Error
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Conexão com banco da Hostinger
config = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}
pool = MySQLConnectionPool(pool_name="martier_pool", pool_size=3, **config)

@app.route('/')
def home():
    return 'API conectada à Hostinger!'

@app.route('/producoes', methods=["GET"])
def listar_producoes():
    try:
        conn = pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM producao")
        dados = cursor.fetchall()
        return jsonify(dados)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/producoes', methods=["POST"])
def inserir_producao():
    dados = request.get_json()
    produto = dados.get("produto")
    tamanho = dados.get("tamanho")
    erp_id = dados.get("erp_id")
    status = dados.get("status")
    quantidade = dados.get("quantidade", 1)
    origem = dados.get("origem")

    try:
        conn = pool.get_connection()
        cursor = conn.cursor()

        # Corrigir fuso horário para Brasília
        brasilia_now = datetime.utcnow() - timedelta(hours=3)

        cursor.execute(
            "INSERT INTO producao (produto, tamanho, erp_id, status, quantidade, origem, criado_em) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (produto, tamanho, erp_id, status, quantidade, origem, brasilia_now)
        )
        conn.commit()
        return jsonify({"mensagem": "Produção inserida com sucesso!"})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/producoes/<int:id>', methods=["PUT"])
def atualizar_status(id):
    try:
        dados = request.get_json()

        # Se o campo 'desativado' estiver presente, atualizar apenas ele
        if "desativado" in dados:
            desativado = dados.get("desativado", 0)

            conn = pool.get_connection()
            cursor = conn.cursor()
            sql = "UPDATE producao SET desativado = %s WHERE id = %s"
            cursor.execute(sql, (desativado, id))
            conn.commit()
            return jsonify({"mensagem": "Campo 'desativado' atualizado com sucesso"}), 200

        # Caso contrário, tratar mudança de status
        novo_status = dados.get("status")
        if novo_status not in ["on_demand", "fila", "construcao", "finalizado"]:
            return jsonify({"erro": "Status inválido"}), 400

        colunas_data = {
            "on_demand": "data_on_demand",
            "fila": "data_fila",
            "construcao": "data_construcao",
            "finalizado": "data_finalizado"
        }

        brasilia_now = datetime.utcnow() - timedelta(hours=3)
        coluna_data = colunas_data[novo_status]

        conn = pool.get_connection()
        cursor = conn.cursor()
        sql = f"""
            UPDATE producao
            SET status = %s, {coluna_data} = %s, desativado = 0
            WHERE id = %s
        """
        cursor.execute(sql, (novo_status, brasilia_now, id))
        conn.commit()

        return jsonify({"mensagem": "Status atualizado com sucesso"}), 200

    except Error as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/importar-produtos', methods=["GET"])
def importar_produtos():
    try:
        conn = pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT DISTINCT produto, tamanho, erp_id FROM producao WHERE produto IS NOT NULL AND tamanho IS NOT NULL AND erp_id IS NOT NULL")
        dados = cursor.fetchall()
        return jsonify(dados)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
