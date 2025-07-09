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

# ✅ CORS ajustado para aceitar domínio com www e credenciais
CORS(app, resources={
    r"/*": {
        "origins": ["https://www.martiermedia.shop"],
        "allow_headers": ["Content-Type", "Authorization"],
        "methods": ["GET", "POST", "PUT", "OPTIONS"],
        "supports_credentials": True
    }
})

SECRET_KEY = os.getenv("SECRET_KEY", "segredo123")

# Pool de conexões
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

# Middleware de autenticação via token
def autenticar(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization") or request.cookies.get("token")
        if not token:
            return jsonify({"erro": "Token não fornecido."}), 401
        try:
            jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"erro": "Token expirado."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"erro": "Token inválido."}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    usuario = data.get("username")
    senha = data.get("password")

    if usuario == "admin" and senha == "senha123":
        token = jwt.encode({
            "user": usuario,
            "exp": datetime.utcnow() + timedelta(hours=6)
        }, SECRET_KEY, algorithm="HS256")

        resp = make_response(jsonify({"mensagem": "Login bem-sucedido"}))
        resp.set_cookie(
            "token", token,
            httponly=True,
            samesite="Lax",
            max_age=60 * 60 * 6
        )
        return resp
    return jsonify({"erro": "Credenciais inválidas"}), 401

@app.route('/producoes', methods=['GET'])
@autenticar
def listar_producoes():
    try:
        conn = pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, produto, tamanho, erp_id, status, criado_em,
                   data_construcao, data_finalizado, data_fila, data_on_demand
            FROM producao
            WHERE status != 'finalizado' OR DATE(criado_em) = CURDATE()
            ORDER BY criado_em DESC
        """)
        dados = cursor.fetchall()
        return jsonify(dados)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/producoes', methods=['POST'])
@autenticar
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

@app.route('/producoes/<int:id>', methods=['PUT'])
@autenticar
def atualizar_status(id):
    dados = request.json
    novo_status = dados.get('status')
    if not novo_status:
        return jsonify({"erro": "Status ausente."}), 400

    try:
        conn = pool.get_connection()
        cursor = conn.cursor()

        campos_data = {
            "construcao": "data_construcao",
            "finalizado": "data_finalizado",
            "fila": "data_fila",
            "on_demand": "data_on_demand"
        }

        if novo_status in campos_data:
            campo = campos_data[novo_status]
            cursor.execute(f"""
                UPDATE producao
                SET status = %s, {campo} = NOW()
                WHERE id = %s
            """, (novo_status, id))
        else:
            cursor.execute("""
                UPDATE producao
                SET status = %s
                WHERE id = %s
            """, (novo_status, id))

        conn.commit()
        return jsonify({"mensagem": "Status atualizado com sucesso!"})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
