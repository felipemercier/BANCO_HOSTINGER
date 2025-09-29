# app.py
from flask import Flask, jsonify, request
from flask_cors import CORS
from mysql.connector.pooling import MySQLConnectionPool
import os, re
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ---------------- DB (Hostinger) ----------------
config = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
}
pool = MySQLConnectionPool(pool_name="martier_pool", pool_size=4, **config)

def _dict_conn_cursor():
    conn = pool.get_connection()
    cur  = conn.cursor(dictionary=True)
    return conn, cur

def _today_br_dateiso():
    return (datetime.utcnow() - timedelta(hours=3)).date().isoformat()

@app.route("/")
def home():
    return "API conectada à Hostinger!"

# ========================= PRODUCAO ==========================
@app.get("/producoes")
def listar_producoes():
    try:
        conn, cursor = _dict_conn_cursor()
        cursor.execute("SELECT * FROM producao")
        return jsonify(cursor.fetchall())
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        try: cursor.close(); conn.close()
        except: pass

@app.post("/producoes")
def inserir_producao():
    dados = request.get_json() or {}
    try:
        conn = pool.get_connection()
        cursor = conn.cursor()
        brasilia_now = datetime.utcnow() - timedelta(hours=3)
        cursor.execute(
            """
            INSERT INTO producao (produto, tamanho, erp_id, status, quantidade, origem, criado_em)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                dados.get("produto"),
                dados.get("tamanho"),
                dados.get("erp_id"),
                dados.get("status"),
                dados.get("quantidade", 1),
                dados.get("origem"),
                brasilia_now,
            ),
        )
        conn.commit()
        return jsonify({"mensagem": "Produção inserida com sucesso!"})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        try: cursor.close(); conn.close()
        except: pass

@app.put("/producoes/<int:id>")
def atualizar_producao(id):
    dados = request.get_json() or {}
    try:
        conn = pool.get_connection()
        cursor = conn.cursor()

        campos_sql, valores = [], []
        novo_status = dados.get("status")
        if novo_status in ["on_demand", "fila", "construcao", "finalizado"]:
            campos_sql.append("status = %s")
            valores.append(novo_status)
            colunas = {
                "on_demand": "data_on_demand",
                "fila": "data_fila",
                "construcao": "data_construcao",
                "finalizado": "data_finalizado",
            }
            campos_sql.append(f"{colunas[novo_status]} = %s")
            valores.append(datetime.utcnow() - timedelta(hours=3))

        if "quantidade" in dados:
            campos_sql.append("quantidade = %s")
            valores.append(dados["quantidade"])
        if "desativado" in dados:
            campos_sql.append("desativado = %s")
            valores.append(dados["desativado"])
        if "observacao" in dados:
            campos_sql.append("observacao = %s")
            valores.append(dados["observacao"])

        if not campos_sql:
            return jsonify({"erro": "Nenhum campo válido enviado."}), 400

        sql = f"UPDATE producao SET {', '.join(campos_sql)} WHERE id = %s"
        valores.append(id)
        cursor.execute(sql, valores)
        conn.commit()
        return jsonify({"mensagem": "Produção atualizada com sucesso"}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        try: cursor.close(); conn.close()
        except: pass

@app.delete("/producoes/<int:id>")
def deletar_producao(id):
    try:
        conn = pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM producao WHERE id=%s", (id,))
        if not cursor.fetchone():
            return jsonify({"erro": "Item não encontrado"}), 404
        cursor.execute("DELETE FROM producao WHERE id=%s", (id,))
        conn.commit()
        return jsonify({"mensagem": "Produção excluída com sucesso"}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        try: cursor.close(); conn.close()
        except: pass

@app.get("/importar-produtos")
def importar_produtos():
    try:
        conn, cursor = _dict_conn_cursor()
        cursor.execute("""
            SELECT DISTINCT produto, tamanho, erp_id
            FROM producao
            WHERE produto IS NOT NULL AND tamanho IS NOT NULL AND erp_id IS NOT NULL
        """)
        return jsonify(cursor.fetchall())
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        try: cursor.close(); conn.close()
        except: pass

# ========================= MAPA DE CORES ==========================
@app.get("/cores")
def listar_cores():
    try:
        conn, cursor = _dict_conn_cursor()
        cursor.execute("SELECT palavra, grupo_cor FROM mapa_cores")
        return jsonify(cursor.fetchall())
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        try: cursor.close(); conn.close()
        except: pass

@app.post("/cores")
def inserir_cor():
    dados = request.get_json() or {}
    palavra = (dados.get("palavra") or "").strip().lower()
    grupo_cor = (dados.get("grupo_cor") or "").strip()
    if not palavra or not grupo_cor:
        return jsonify({"erro": "Campos obrigatórios: palavra e grupo_cor"}), 400
    try:
        conn = pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO mapa_cores (palavra, grupo_cor) VALUES (%s,%s)", (palavra, grupo_cor))
        conn.commit()
        return jsonify({"mensagem": "Cor inserida com sucesso!"})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        try: cursor.close(); conn.close()
        except: pass

# ========================= COLETA (Protocolo) ==========================
@app.get("/api/coleta")
def coleta_list():
    d1 = request.args.get("from")
    d2 = request.args.get("to")
    include_deleted = request.args.get("include_deleted", "0") == "1"
    sql = "SELECT * FROM coleta_protocolos WHERE 1"
    params = []
    if not include_deleted:
        sql += " AND active=1"
    if d1:
        sql += " AND dateISO >= %s"; params.append(d1)
    if d2:
        sql += " AND dateISO <= %s"; params.append(d2)
    if not d1 and not d2:
        sql += " AND dateISO >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
    sql += " ORDER BY dateISO DESC, timeHHMMSS DESC, id DESC"
    try:
        conn, cur = _dict_conn_cursor()
        cur.execute(sql, params)
        return jsonify({"rows": cur.fetchall()})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        try: cur.close(); conn.close()
        except: pass

@app.post("/api/coleta")
def coleta_upsert():
    payload = request.get_json(silent=True) or {}
    items = payload if isinstance(payload, list) else [payload]
    sql = """
        INSERT INTO coleta_protocolos
          (dateISO, timeHHMMSS, code, service, uf, peso, nf,
           valorCorreios, valorCliente, pedido, registradoPor, active)
        VALUES
          (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
        ON DUPLICATE KEY UPDATE
          service=VALUES(service),
          uf=VALUES(uf),
          peso=VALUES(peso),
          nf=VALUES(nf),
          valorCorreios=VALUES(valorCorreios),
          valorCliente=VALUES(valorCliente),
          pedido=VALUES(pedido),
          registradoPor=VALUES(registradoPor),
          active=1,
          deleted_at=NULL
    """
    to_exec = []
    for r in items:
        to_exec.append((
            r.get("dateISO"),
            r.get("time") or r.get("timeHHMMSS"),
            r.get("code"),
            r.get("service"),
            r.get("uf"),
            r.get("peso"),
            r.get("nf"),
            r.get("valorCorreios"),
            r.get("valorCliente"),
            r.get("pedido"),
            r.get("registradoPor"),
        ))
    try:
        conn = pool.get_connection()
        cur  = conn.cursor()
        cur.executemany(sql, to_exec)
        conn.commit()
        return jsonify({"ok": True, "count": len(to_exec)})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        try: cur.close(); conn.close()
        except: pass

@app.delete("/api/coleta/<int:item_id>")
def coleta_soft_delete(item_id):
    try:
        conn = pool.get_connection()
        cur  = conn.cursor()
        cur.execute(
          "UPDATE coleta_protocolos SET active=0, deleted_at=NOW() WHERE id=%s AND active=1",
          (item_id,)
        )
        conn.commit()
        return jsonify({"ok": True, "id": item_id})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        try: cur.close(); conn.close()
        except: pass

@app.post("/api/coleta/<int:item_id>/restore")
def coleta_restore(item_id):
    try:
        conn = pool.get_connection()
        cur  = conn.cursor()
        cur.execute("UPDATE coleta_protocolos SET active=1, deleted_at=NULL WHERE id=%s", (item_id,))
        conn.commit()
        return jsonify({"ok": True, "id": item_id})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        try: cur.close(); conn.close()
        except: pass

# Funcionários
@app.get("/api/coleta/func")
def coleta_func_list():
    try:
        conn, cur = _dict_conn_cursor()
        cur.execute("SELECT * FROM coleta_funcionarios ORDER BY nome")
        return jsonify({"rows": cur.fetchall()})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        try: cur.close(); conn.close()
        except: pass

@app.post("/api/coleta/func")
def coleta_func_upsert():
    data = request.get_json(silent=True) or {}
    nome = (data.get("nome") or "").strip()
    is_default = 1 if data.get("is_default") else 0
    if not nome:
        return jsonify({"erro": "nome é obrigatório"}), 400
    try:
        conn = pool.get_connection()
        cur  = conn.cursor()
        cur.execute("INSERT IGNORE INTO coleta_funcionarios (nome) VALUES (%s)", (nome,))
        if is_default:
            cur.execute("UPDATE coleta_funcionarios SET is_default=0")
            cur.execute("UPDATE coleta_funcionarios SET is_default=1 WHERE nome=%s", (nome,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        try: cur.close(); conn.close()
        except: pass

# -------- NOVAS ROTAS: protocolo (fechar dia + histórico) --------
def _mk_protocolo_for_date(cur, date_iso: str) -> str:
    """Gera PR-YYYYMMDD-### sequencial para a data."""
    cur.execute("""
        SELECT protocolo_num
        FROM coleta_protocolos
        WHERE dateISO=%s AND protocolo_num IS NOT NULL
        ORDER BY printed_at DESC, protocolo_num DESC
        LIMIT 1
    """, (date_iso,))
    last = cur.fetchone()
    seq = 0
    if last and last.get("protocolo_num"):
        m = re.search(r"(\d{3})$", last["protocolo_num"])
        if m: seq = int(m.group(1))
    seq += 1
    return f"PR-{date_iso.replace('-', '')}-{seq:03d}"

@app.post("/api/coleta/fechar-dia")
def coleta_fechar_dia():
    """
    Fecha o dia atual (ou date enviado) e marca todos os registros
    ativos daquela data que ainda NÃO possuem protocolo.
    Body JSON: { "date": "YYYY-MM-DD", "printed_by": "nome" }
    """
    body = request.get_json(silent=True) or {}
    date_iso = (body.get("date") or _today_br_dateiso()).strip()
    printed_by = (body.get("printed_by") or "").strip() or None

    try:
        conn = pool.get_connection()
        cur  = conn.cursor(dictionary=True)

        cur.execute("""
           SELECT id FROM coleta_protocolos
           WHERE active=1 AND dateISO=%s AND (protocolo_num IS NULL OR protocolo_num='')
           LIMIT 1
        """, (date_iso,))
        if not cur.fetchone():
            return jsonify({"ok": True, "count": 0, "rows": []})

        protocolo = _mk_protocolo_for_date(cur, date_iso)

        cur2 = conn.cursor()
        cur2.execute("""
            UPDATE coleta_protocolos
            SET protocolo_num=%s, printed_at=NOW(), printed_by=%s
            WHERE active=1 AND dateISO=%s AND (protocolo_num IS NULL OR protocolo_num='')
        """, (protocolo, printed_by, date_iso))
        conn.commit()
        cur2.close()

        cur.execute("""
            SELECT code, pedido
            FROM coleta_protocolos
            WHERE dateISO=%s AND protocolo_num=%s
            ORDER BY id
        """, (date_iso, protocolo))
        items = cur.fetchall()

        return jsonify({
            "ok": True,
            "protocolo": protocolo,
            "date": date_iso,
            "count": len(items),
            "rows": items
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        try: cur.close(); conn.close()
        except: pass

@app.get("/api/coleta/historico")
def coleta_historico():
    """
    Lista protocolos fechados no período.
    Query: from, to (YYYY-MM-DD). Defaults: últimos 30 dias.
    """
    to  = request.args.get("to") or _today_br_dateiso()
    frm = request.args.get("from") or (datetime.fromisoformat(to) - timedelta(days=30)).date().isoformat()
    try:
        conn, cur = _dict_conn_cursor()
        cur.execute("""
            SELECT
              protocolo_num                                         AS protocolo_num,
              DATE_FORMAT(MIN(printed_at),'%Y-%m-%d %H:%i:%s')      AS printed_at,
              COALESCE(MAX(printed_by), '')                         AS printed_by,
              COUNT(*)                                              AS qtd,
              ROUND(SUM(COALESCE(valorCliente,  0)), 2)             AS total_cliente,
              ROUND(SUM(COALESCE(valorCorreios, 0)), 2)             AS total_correios
            FROM coleta_protocolos
            WHERE protocolo_num IS NOT NULL
              AND printed_at   IS NOT NULL
              AND dateISO BETWEEN %s AND %s
            GROUP BY protocolo_num
            ORDER BY MIN(printed_at) DESC
        """, (frm, to))
        rows = cur.fetchall()
        for r in rows:
            r["lucro"] = float(r.get("total_cliente") or 0) - float(r.get("total_correios") or 0)
        return jsonify({"ok": True, "from": frm, "to": to, "rows": rows})
    except Exception as e:
        app.logger.exception("Erro ao carregar histórico")
        return jsonify({"erro": str(e)}), 500
    finally:
        try: cur.close(); conn.close()
        except: pass

# --- alias para compatibilidade com o front (historico.js usa /protocolos)
@app.get("/api/coleta/protocolos")
def coleta_historico_alias():
    return coleta_historico()

@app.post("/api/coleta/print")
def coleta_print_alias():
    return coleta_fechar_dia()

@app.get("/api/coleta/protocolo/<protocolo>")
def coleta_protocolo_itens(protocolo):
    """Itens de um protocolo para reimpressão/consulta."""
    try:
        conn, cur = _dict_conn_cursor()
        cur.execute("""
            SELECT code, timeHHMMSS, service, uf, nf, pedido, valorCliente, valorCorreios
            FROM coleta_protocolos
            WHERE protocolo_num=%s
            ORDER BY id
        """, (protocolo,))
        items = cur.fetchall()
        return jsonify({"ok": True, "rows": items})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        try: cur.close(); conn.close()
        except: pass

# ================================================================
if __name__ == "__main__":
    app.run(debug=True)
