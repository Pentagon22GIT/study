# keepalive.py
import os
from flask import Flask
import threading

app = Flask(__name__)


@app.route("/")
def index():
    return "Bot is running!", 200


def run_keepalive():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


def start():
    """バックグラウンドで Flask サーバーを起動する関数"""
    t = threading.Thread(target=run_keepalive)
    t.daemon = True  # メインスレッド終了時に自動終了
    t.start()
