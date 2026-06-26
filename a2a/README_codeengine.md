# A2A エージェントを GitHub → IBM Code Engine にデプロイする手順

---

## Step 1 — リポジトリを GitHub に Push する

### 1-1. Git の初期設定（初回のみ）

```bash
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
```

### 1-2. GitHub でリポジトリを新規作成する

1. https://github.com/new を開く
2. **Repository name** を入力（例: `ki-a2a-agent`）
3. Public / Private を選択
4. **「Create repository」** をクリック

### 1-3. ローカルフォルダを Git リポジトリにして Push する

> 以下のコマンドはこのワークスペース（`ガバナンス機能ご紹介/`）のルートで実行してください。

```bash
# Git リポジトリを初期化（まだの場合）
git init

# .gitignore を作成して不要ファイルを除外
echo "__pycache__/" >> .gitignore
echo "*.pyc"        >> .gitignore
echo ".env"         >> .gitignore

# ファイルをステージング
git add a2a/

# コミット
git commit -m "Add A2A server for Code Engine deployment"

# GitHub のリモートを登録（URL は手順 1-2 で作成したリポジトリのもの）
git remote add origin https://github.com/<your-username>/ki-a2a-agent.git

# Push
git branch -M main
git push -u origin main
```

> **認証エラーが出る場合**  
> GitHub は 2021 年以降パスワード認証を廃止しています。  
> Personal Access Token (PAT) を使ってください。
>
> 1. https://github.com/settings/tokens/new を開く  
> 2. **Scopes**: `repo` にチェックを入れて **Generate token**  
> 3. 表示されたトークンを、パスワードの代わりに入力する

### Push 後に確認するファイル構成

```
（リポジトリルート）
└── a2a/
    ├── Dockerfile
    ├── a2a_server.py
    └── requirements_a2a.txt
```

---

## Step 2 — IBM Cloud コンソールで Code Engine プロジェクトを作成する

1. https://cloud.ibm.com にログイン
2. 左上のハンバーガーメニュー → **「Code Engine」** を選択  
   （または検索バーで「Code Engine」と入力）
3. **「プロジェクトの作成」** をクリック
4. 以下を設定して **「作成」**

   | 項目 | 設定値の例 |
   |---|---|
   | 名前 | `wxo-a2a-project` |
   | リージョン | `東京 (jp-tok)` |
   | リソース・グループ | `Default` |

---

## Step 3 — シークレットに GROQ_API_KEY を登録する

1. 作成したプロジェクトを開く
2. 左メニュー → **「シークレットおよびConfigmap」** をクリック
3. **「シークレットの作成」** をクリック
4. 以下を設定して **「作成」**

   | 項目 | 設定値 |
   |---|---|
   | タイプ | `一般 (Generic)` |
   | 名前 | `groq-secret` |
   | キー | `GROQ_API_KEY` |
   | 値 | `（Groq の API キー）` |

---

## Step 4 — アプリケーションを GitHub ソースから作成する

1. 左メニュー → **「アプリケーション」** → **「作成」**
2. **「ソース・コードを使用して構築する」** を選択

### 4-1. ソースの設定

| 項目 | 設定値 |
|---|---|
| ソース URL | `https://github.com/<your-username>/ki-a2a-agent` |
| ブランチ | `main` |
| コンテキスト・ディレクトリー | `a2a` |

> **プライベートリポジトリの場合**  
> 「GitHubアクセス」欄が表示されます。  
> **「新規 SSH キーの追加」** をクリックし、表示された公開鍵を  
> GitHub の Settings → Deploy keys に登録してください。

### 4-2. ビルドの設定

| 項目 | 設定値 |
|---|---|
| ビルド・ストラテジー | `Dockerfile` |
| Dockerfile | `Dockerfile`（自動検出される） |
| イメージ出力先 | `（プロジェクトの内部コンテナー・レジストリー）` |

### 4-3. ランタイムの設定

| 項目 | 設定値 |
|---|---|
| 名前 | `ki-a2a-server` |
| リスニング・ポート | `8080` |
| CPU / メモリ | `0.5 vCPU / 1 GB`（デフォルトで可） |
| 最小インスタンス数 | `0`（アイドル時にゼロスケール） |
| 最大インスタンス数 | `3` |

### 4-4. 環境変数の設定

1. **「環境変数の追加」** → **「シークレットの参照」** を選択
2. シークレット名 `groq-secret` を選択 → **「すべてのキーの参照」**
3. **「作成」** をクリックしてデプロイ開始

> ビルドには数分かかります。  
> 「アクティビティー」タブでビルドログを確認できます。

---

## Step 5 — デプロイ後の URL を確認する

1. アプリケーション一覧で `ki-a2a-server` をクリック
2. **「概要」** タブ → **「アプリケーション URL」** をコピー

   例: `https://ki-a2a-server.abcdef12.jp-tok.codeengine.appdomain.cloud`

---

## Step 6 — 動作確認

ブラウザまたは curl で以下の URL にアクセスして確認します。

### Agent Card

```
https://<CE_URL>/.well-known/agent-card.json
```

### ヘルスチェック

```
https://<CE_URL>/health
```

正常なら以下のレスポンスが返ります。

```json
{"status": "ok", "agent": "ki-web-search-agent-a2a", "protocol": "A2A/0.3.0"}
```

---

## Step 7 — agent_a2a.yaml の api_url を更新して wxO に登録する

[`agent_a2a.yaml`](agent_a2a.yaml) の `api_url` を Step 5 で確認した URL に書き換えます。

```yaml
api_url: "https://ki-a2a-server.abcdef12.jp-tok.codeengine.appdomain.cloud"
```

その後、watsonx Orchestrate に外部エージェントとして登録します。

```bash
orchestrate agents import -f a2a/agent_a2a.yaml
```

---

## 環境変数一覧

| 変数名 | 必須 | 説明 |
|---|---|---|
| `GROQ_API_KEY` | ✅ | Groq API キー（Step 3 で登録） |
| `AGENT_BASE_URL` | 任意 | Agent Card に返す `url` フィールド（省略可） |
| `PORT` | 自動 | Code Engine が自動設定（`8080`）|

---

## トラブルシューティング

| 症状 | 確認点 |
|---|---|
| ビルドが失敗する | 「コンテキスト・ディレクトリー」が `a2a` になっているか確認 |
| `GROQ_API_KEY` が見つからない | シークレット `groq-secret` のキー名が `GROQ_API_KEY` か確認 |
| Agent Card が返らない | アプリの「ログ」タブでエラーを確認 |
| wxO 登録後に接続できない | `agent_a2a.yaml` の `api_url` が Code Engine URL になっているか確認 |

---

*Made with IBM Bob*
