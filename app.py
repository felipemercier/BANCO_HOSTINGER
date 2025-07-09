from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
from mysql.connector.pooling import MySQLConnectionPool
from datetime import datetime, timedelta
from functools import wraps
import os
import jwt
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["https://www.martiermedia.shop"])

SECRET_KEY = os.getenv("SECRET_KEY", "segredo123")

# Configuração da conexão com o banco de dados
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

# Função de autenticação baseada em token
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
            path="/martier-site"  # <- IMPORTANTE
        )
        return resp
    else:
        return jsonify({"erro": "Credenciais inválidas"}), 401

# Rota protegida de exemplo
@app.route('/producoes')
@autenticar
def producoes():
    try:
        conn = pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM producoes")
        dados = cursor.fetchall()
        return jsonify(dados)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == '__main__':
    app.run(debug=True)
