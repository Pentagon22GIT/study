# Dockerfile

# Python 3.9-slim をベースイメージとして使用
FROM python:3.9-slim

# 作業ディレクトリを /app に設定
WORKDIR /app

# 依存ライブラリのインストール
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# アプリケーションコードをコンテナにコピー
COPY . .

# Flask サーバー用のポートを公開（デフォルト5000）
EXPOSE 5000

# コンテナ起動時に bot.py を実行（bot.py 内で keepalive.start() を呼んでいる）
CMD ["python", "bot.py"]
