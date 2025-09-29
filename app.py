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
# ... (mantém exatamente igual ao seu código anterior para producao, cores, coleta, etc)

# -------- PROTOCOLO (fechar dia + histórico) --------
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
        sql = """
            SELECT
              protocolo_num                             AS protocolo_num,
              MIN(printed_at)                           AS printed_at,
              COALESCE(MAX(printed_by), '')             AS printed_by,
              COUNT(*)                                  AS qtd,
              ROUND(SUM(COALESCE(valorCliente,  0)), 2) AS total_cliente,
              ROUND(SUM(COALESCE(valorCorreios, 0)), 2) AS total_correios
            FROM coleta_protocolos
            WHERE protocolo_num IS NOT NULL
              AND printed_at   IS NOT NULL
              AND dateISO BETWEEN %s AND %s
            GROUP BY protocolo_num
            ORDER BY MIN(printed_at) DESC
        """
        cur.execute(sql, (frm, to))
        rows = cur.fetchall()

        for r in rows:
            pa = r.get("printed_at")
            if pa and not isinstance(pa, str):
                r["printed_at"] = pa.strftime("%Y-%m-%d %H:%M:%S")
            r["lucro"] = float(r.get("total_cliente") or 0) - float(r.get("total_correios") or 0)

        return jsonify({"ok": True, "from": frm, "to": to, "rows": rows})
    except Exception as e:
        app.logger.exception("Erro ao carregar histórico")
        return jsonify({"erro": str(e)}), 500
    finally:
        try: cur.close(); conn.close()
        except: pass

# --- alias compatível com historico.js
@app.get("/api/coleta/protocolos")
def coleta_historico_alias():
    return coleta_historico()

@app.post("/api/coleta/print")
def coleta_print_alias():
    return coleta_fechar_dia()

@app.get("/api/coleta/protocolo/<protocolo>")
def coleta_protocolo_itens(protocolo):
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
