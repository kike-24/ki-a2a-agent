# A2A エージェントを無償サービスにデプロイする手順

IBM Code Engine の代わりに **無償枠**で使えるクラウドサービスを利用して  
`a2a_server.py` をデプロイする手順です。

---

## サービス比較

| サービス | 無料枠 | コールド起動 | 注意点 |
|---|---|---|---|
| **Railway** ⭐推奨 | 毎月 $5 分のクレジット（約 500 時間） | なし | GitHub 連携が最も簡単 |
| **Render** | 750 時間 / 月（1 インスタンス） | あり（15 分無操作でスリープ） | スリープ明けに数秒遅延 |
| **Fly.io** | 3 台の shared-cpu-1x 無料 | なし | CLI セットアップが必要 |

---

## Option A — Railway（推奨）

### A-1. 事前準備

1. https://railway.app にアクセスし **「Login with GitHub」** でアカウント作成
2. https://github.com/new で新しいリポジトリを作成（例: `ki-a2a-agent`）
3. ローカルから Push する

```bash
# ワークスペースのルートで実行
git add a2a/
git commit -m "Add A2A server"
git remote add origin https://github.com/<your-username>/ki-a2a-agent.git
git branch -M main
git push -u origin main
```

> **GitHub 認証エラーの場合**  
> https://github.com/settings/tokens/new でトークンを生成し、パスワードの代わりに使用してください。

### A-2. Railway で新規プロジェクトを作成

1. https://railway.app/new を開く
2. **「Deploy from GitHub repo」** をクリック
3. `ki-a2a-agent` リポジトリを選択
4. **「Add variables」** をクリックして環境変数を追加

   | 変数名 | 値 |
   |---|---|
   | `GROQ_API_KEY` | Groq の API キー（https://console.groq.com/keys） |

5. **「Deploy」** をクリック

> Railway は `a2a/Dockerfile` を自動検出してビルドします。  
> ビルドログは「Deployments」タブで確認できます。

### A-3. ルートディレクトリを設定する

Railway がリポジトリのルートではなく `a2a/` フォルダをビルドするよう設定します。

1. デプロイしたサービスの **「Settings」** タブを開く
2. **「Root Directory」** に `a2a` と入力
3. **「Redeploy」** をクリック

### A-4. デプロイ後の URL を確認する

1. **「Settings」** タブ → **「Networking」** セクション
2. **「Generate Domain」** をクリック
3. 表示された URL をコピー（例: `https://ki-a2a-agent-production.up.railway.app`）

### A-5. 動作確認

```bash
# Agent Card の確認
curl https://<RAILWAY_URL>/.well-known/agent-card.json

# ヘルスチェック
curl https://<RAILWAY_URL>/health
```

正常なら以下が返ります:

```json
{"status": "ok", "agent": "ki-web-search-agent-a2a", "protocol": "A2A/0.3.0"}
```

---

## Option B — Render

### B-1. 事前準備

GitHub に Push する（Option A の A-1 と同様）。

### B-2. Render で Web Service を作成

1. https://render.com にアクセスし **「Sign Up with GitHub」** でアカウント作成
2. **「New +」** → **「Web Service」** をクリック
3. `ki-a2a-agent` リポジトリを選択して **「Connect」**
4. 以下を設定する

   | 項目 | 設定値 |
   |---|---|
   | **Name** | `ki-a2a-server` |
   | **Root Directory** | `a2a` |
   | **Runtime** | `Docker` |
   | **Instance Type** | `Free` |

5. **「Environment Variables」** セクションで追加

   | キー | 値 |
   |---|---|
   | `GROQ_API_KEY` | Groq の API キー |

6. **「Create Web Service」** をクリック

> ⚠️ Render の無料プランは **15 分間アクセスがないとスリープ**します。  
> 最初のリクエストに 30〜60 秒かかることがあります。  
> wxO からの接続タイムアウトが発生する場合は、後述の「スリープ対策」を参照してください。

### B-3. デプロイ後の URL を確認する

ダッシュボード上部に `https://ki-a2a-server.onrender.com` 形式の URL が表示されます。

### B-4. スリープ対策（任意）

無料の外部サービス（例: https://cron-job.org）で 10 分おきにヘルスチェック URL を  
`GET` するよう設定すると、スリープを防げます。

```
監視 URL: https://ki-a2a-server.onrender.com/health
間隔: 10 分
```

---

## Option C — Fly.io

### C-1. CLI のインストール

```bash
# macOS / Linux
curl -L https://fly.io/install.sh | sh

# Windows (PowerShell)
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

### C-2. ログインとアプリ作成

```bash
fly auth login

# a2a/ フォルダに移動してデプロイ
cd a2a
fly launch --name ki-a2a-server --dockerfile Dockerfile --no-deploy
```

### C-3. シークレットを設定してデプロイ

```bash
fly secrets set GROQ_API_KEY=<your-groq-api-key>
fly deploy
```

### C-4. URL の確認

```bash
fly status
# または
fly open /.well-known/agent-card.json
```

---

## Step 6 — agent_a2a.yaml を更新して wxO に登録する

[`agent_a2a.yaml`](agent_a2a.yaml) の `api_url` を上記でデプロイした URL に書き換えます。

```yaml
# Railway の例
api_url: "https://ki-a2a-agent-production.up.railway.app"

# Render の例
api_url: "https://ki-a2a-server.onrender.com"

# Fly.io の例
api_url: "https://ki-a2a-server.fly.dev"
```

その後、watsonx Orchestrate に外部エージェントとして登録します。

```bash
orchestrate agents import -f a2a/agent_a2a.yaml
```

---

## トラブルシューティング

| 症状 | 確認点 |
|---|---|
| ビルドが失敗する | Railway / Render の **Root Directory** が `a2a` になっているか確認 |
| `GROQ_API_KEY` が見つからない | サービスの環境変数設定でキー名が `GROQ_API_KEY` か確認 |
| Agent Card が返らない | サービスのログタブでエラーを確認 |
| Render でタイムアウトする | スリープ中の可能性あり。30〜60 秒待って再試行 |
| wxO 登録後に接続できない | `agent_a2a.yaml` の `api_url` がデプロイ先の URL になっているか確認 |
| ポートが合わない | Render / Fly.io は `PORT` 環境変数を自動設定するため変更不要 |

---

## 環境変数一覧

| 変数名 | 必須 | 説明 |
|---|---|---|
| `GROQ_API_KEY` | ✅ | Groq API キー（https://console.groq.com/keys で取得） |
| `AGENT_BASE_URL` | 任意 | Agent Card に返す `url` フィールド（省略時は `http://localhost:8000`） |
| `PORT` | 自動 | 各サービスが自動設定（`8080` または `10000` など） |

---

*Made with IBM Bob*
