from flask import Flask, render_template, jsonify
from sshtunnel import SSHTunnelForwarder
import mysql.connector
import os
import decimal
import config

app = Flask(__name__)

SSH_HOST = config.SSH_HOST
SSH_USER = config.SSH_USER
SSH_KEY = config.SSH_KEY
DB_NAME = config.DB_NAME
DB_USER = config.DB_USER
DB_PASS = config.DB_PASS
SQL_DIR = config.SQL_DIR


def run_query(sql_file):
    with open(os.path.join(SQL_DIR, sql_file)) as f:
        sql = f.read()

    with SSHTunnelForwarder(
        (SSH_HOST, 22),
        ssh_username=SSH_USER,
        ssh_private_key=SSH_KEY,
        remote_bind_address=("127.0.0.1", 3306),
        local_bind_address=("127.0.0.1", 3307)
    ) as tunnel:
        conn = mysql.connector.connect(
            host="127.0.0.1",
            port=3307,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME
        )
        cur = conn.cursor()
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]

        def convert(value):
            return float(value) if isinstance(value, decimal.Decimal) else value

        data = [dict(zip(columns, [convert(v) for v in row])) for row in cur.fetchall()]
        cur.close()
        conn.close()
    return data


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/packets_per_port")
def packets_per_port():
    return render_template("packets_per_port.html")

@app.route("/api/packets_per_port")
def api_packets_per_port():
    return jsonify(run_query("packets_per_port.sql"))


@app.route("/link_throughput")
def link_throughput():
    return render_template("link_throughput.html")

@app.route("/api/link_throughput")
def api_link_throughput():
    return jsonify(run_query("link_throughput.sql"))


@app.route("/distinct_flows")
def distinct_flows():
    return render_template("distinct_flows.html")

@app.route("/api/distinct_flows")
def api_distinct_flows():
    return jsonify(run_query("distinct_flows.sql"))


@app.route("/flowlet_count")
def flowlet_count():
    return render_template("flowlet_count.html")

@app.route("/api/flowlet_count")
def api_flowlet_count():
    return jsonify(run_query("flowlet_counter.sql"))


@app.route("/average_payload")
def average_payload():
    return render_template("average_payload.html")

@app.route("/api/average_payload")
def api_average_payload():
    return jsonify(run_query("average_payload.sql"))


if __name__ == "__main__":
    app.run(debug=True)
