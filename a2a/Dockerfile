FROM python:3.11-slim

WORKDIR /app

# 依存ライブラリのインストール
COPY requirements_a2a.txt .
RUN pip install --no-cache-dir -r requirements_a2a.txt

# アプリケーションコードのコピー
COPY a2a_server.py .

# Code Engine はポートを PORT 環境変数で渡してくる（デフォルト 8080）
ENV PORT=8080
EXPOSE 8080

# uvicorn でサーバー起動（PORT 環境変数を参照するよう shell 形式で記載）
CMD uvicorn a2a_server:app --host 0.0.0.0 --port ${PORT}
