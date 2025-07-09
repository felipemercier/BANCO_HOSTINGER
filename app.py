from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
from mysql.connector.pooling import MySQLConnectionPool
from datetime import datetime, timedelta
from functools import wraps
import os
import jwt
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["https://www.martiermedia.shop"])

SECRET_KEY = os.getenv("SECRET_KEY", "segredo123")

# Configuração do pool de conexões
config = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}
pool = MySQLConnectionPool(pool_name="martier_pool", pool_size=1, **config)

@app.route('/')
def home():
    return 'API conectada à Hostinger!'

# Decorador para autenticação por cookie
def autenticar(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("token")
        if not token:
            return jsonify({"erro": "Token ausente"}), 401
        try:
            jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"erro": "Sessão expirada"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"erro": "Token inválido"}), 401
        return f(*args, **kwargs)
    return decorated

# Rota de login
@app.route('/login', methods=["POST"])
def login():
    dados = request.get_json()
    username = dados.get("username")
    password = dados.get("password")

    if username == "admin" and password == "123456":
        payload = {
            "user": username,
            "exp": datetime.utcnow() + timedelta(hours=6)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        resp = make_response(jsonify({"mensagem": "Login realizado"}))
        resp.set_cookie(
            "token", token,
            httponly=True,
            samesite="Lax",
            max_age=60 * 60 * 6,
            path="/"
        )
        return resp
    else:
        return jsonify({"erro": "Credenciais inválidas"}), 401

# Rota protegida: listar produções
@app.route('/producoes', methods=["GET"])
@autenticar
def producoes():
    conn = None
    cursor = None
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

# Rota protegida: importar produtos da WBuy
@app.route('/importar-produtos', methods=["GET"])
@autenticar
def importar_produtos():
    try:
        headers = {
            "Authorization": os.getenv("WBUY_TOKEN"),
            "Content-Type": "application/json"
        }
        url = "https://sistema.sistemawbuy.com.br/api/v1/product/?ativo=1&limit=9999"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            produtos = data.get("data", [])
            return jsonify(produtos)
        else:
            return jsonify({
                "erro": "Erro ao buscar produtos",
                "status": response.status_code
            }), 500
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# Rota protegida: criar produção (POST)
@app.route('/producoes', methods=["POST"])
@autenticar
def criar_producao():
    dados = request.get_json()
    produto = dados.get("produto")
    tamanho = dados.get("tamanho")
    erp_id = dados.get("erp_id")
    status = dados.get("status", "fila")

    conn = None
    cursor = None
    try:
        conn = pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO producao (produto, tamanho, erp_id, status)
            VALUES (%s, %s, %s, %s)
        """, (produto, tamanho, erp_id, status))
        conn.commit()
        return jsonify({"mensagem": "Produção criada com sucesso"})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# Início do servidor
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
