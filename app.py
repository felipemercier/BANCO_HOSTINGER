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
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

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

# Middleware de autenticação via token (cookie ou header)
def autenticar(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            token = request.cookies.get("token")
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

# Rota de login que define o token em um cookie HttpOnly
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
            "token",
            token,
            httponly=True,
            samesite="None",
            secure=True,
            max_age=60 * 60 * 6  # 6 horas
        )
        return resp
    else:
        return jsonify({"erro": "Credenciais inválidas"}), 401

# Listar produções
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
            WHERE status != 'finalizado'
               OR DATE(criado_em) = CURDATE()
            ORDER BY criado_em DESC
        """)
        dados = cursor.fetchall()
        return jsonify(dados)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Adicionar produção
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

# Atualizar status
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

        if novo_status == 'construcao':
            cursor.execute("""
                UPDATE producao 
                SET status = %s, data_construcao = NOW()
                WHERE id = %s
            """, (novo_status, id))
        elif novo_status == 'finalizado':
            cursor.execute("""
                UPDATE producao 
                SET status = %s, data_finalizado = NOW()
                WHERE id = %s
            """, (novo_status, id))
        elif novo_status == 'fila':
            cursor.execute("""
                UPDATE producao 
                SET status = %s, data_fila = NOW()
                WHERE id = %s
            """, (novo_status, id))
        elif novo_status == 'on_demand':
            cursor.execute("""
                UPDATE producao 
                SET status = %s, data_on_demand = NOW()
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

# Iniciar servidor
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
