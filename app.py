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
def atualizar_producao(id):
    try:
        dados = request.get_json()
        conn = pool.get_connection()
        cursor = conn.cursor()

        campos_sql = []
        valores = []

        # Atualizar status e sua respectiva data
        novo_status = dados.get("status")
        if novo_status in ["on_demand", "fila", "construcao", "finalizado"]:
            campos_sql.append("status = %s")
            valores.append(novo_status)

            colunas_data = {
                "on_demand": "data_on_demand",
                "fila": "data_fila",
                "construcao": "data_construcao",
                "finalizado": "data_finalizado"
            }

            coluna_data = colunas_data[novo_status]
            campos_sql.append(f"{coluna_data} = %s")
            valores.append(datetime.utcnow() - timedelta(hours=3))

        # Atualizar quantidade
        if "quantidade" in dados:
            campos_sql.append("quantidade = %s")
            valores.append(dados["quantidade"])

        # Atualizar campo desativado
        if "desativado" in dados:
            campos_sql.append("desativado = %s")
            valores.append(dados["desativado"])

        # Atualizar observacao (justificativa)
        if "observacao" in dados:
            campos_sql.append("observacao = %s")
            valores.append(dados["observacao"])

        # Verifica se tem algo pra atualizar
        if not campos_sql:
            return jsonify({"erro": "Nenhum campo válido enviado."}), 400

        # Monta SQL
        sql = f"UPDATE producao SET {', '.join(campos_sql)} WHERE id = %s"
        valores.append(id)

        cursor.execute(sql, valores)
        conn.commit()
        return jsonify({"mensagem": "Produção atualizada com sucesso"}), 200

    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@app.route('/producoes/<int:id>', methods=["DELETE"])
def deletar_producao(id):
    try:
        conn = pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM producao WHERE id = %s", (id,))
        conn.commit()
        return jsonify({"mensagem": "Produção excluída com sucesso"}), 200
    except Exception as e:
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
