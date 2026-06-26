"""
A2A プロトコル v0.3.0 準拠サーバー — KI Web検索エージェント

watsonx Orchestrate の A2A 外部エージェントとして接続するための
FastAPI サーバー実装。以下のエンドポイントを提供します:

  GET  /.well-known/agent-card.json  → Agent Card（エージェントのメタデータ）
  POST /                             → JSON-RPC 2.0 エンドポイント（A2A メッセージ処理）

起動方法:
  pip install -r requirements_a2a.txt
  export GROQ_API_KEY=your_groq_api_key
  uvicorn a2a_server:app --host 0.0.0.0 --port 8000

wxO への登録:
  orchestrate agents import -f agent_a2a.yaml
  （agent_a2a.yaml の api_url を実際のサーバー URL に変更してから実行）
"""

import os
import uuid
import operator
from typing import Annotated, Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables.config import RunnableConfig
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from duckduckgo_search import DDGS
from typing import TypedDict


# ─────────────────────────────────────────────
# Web 検索ツール（KI_langgraph_search_agent.py と同一）
# ─────────────────────────────────────────────

@tool
def web_search(query: str, max_results: int = 5) -> str:
    """
    DuckDuckGo APIを使用してWeb検索を実行します。

    Args:
        query: 検索クエリ
        max_results: 返す最大結果数（デフォルト: 5）

    Returns:
        検索結果の文字列
    """
    try:
        with DDGS() as ddgs:
            results = []
            for i, r in enumerate(ddgs.text(query, max_results=max_results), 1):
                results.append(
                    f"{i}. {r.get('title', 'タイトルなし')}\n"
                    f"   URL: {r.get('href', '')}\n"
                    f"   概要: {r.get('body', '')}\n"
                )
            if results:
                return f"検索クエリ「{query}」の結果:\n\n" + "\n".join(results)
            else:
                return f"検索クエリ「{query}」に対する結果が見つかりませんでした。"
    except Exception as e:
        return f"検索中にエラーが発生しました: {str(e)}"


# ─────────────────────────────────────────────
# LangGraph エージェント定義
# ─────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]


def agent_node(state: AgentState) -> AgentState:
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.7,
    )
    response = llm.bind_tools([web_search]).invoke(state["messages"])
    return {"messages": [response]}


def should_continue(state: AgentState):
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


def build_graph() -> StateGraph:
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode([web_search]))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    workflow.add_edge("tools", "agent")
    return workflow.compile()


# エージェントをサーバー起動時に一度だけコンパイル
_agent = build_graph()


# ─────────────────────────────────────────────
# A2A ヘルパー: メッセージ変換
# ─────────────────────────────────────────────

def _a2a_messages_to_langchain(a2a_messages: List[Dict]) -> List[BaseMessage]:
    """A2A メッセージ形式を LangChain BaseMessage リストに変換する。"""
    lc_messages = []
    for msg in a2a_messages:
        role = msg.get("role", "user")
        # parts は [{"type": "text", "text": "..."}] の形式
        parts = msg.get("parts", [])
        text = " ".join(
            p.get("text", "") for p in parts if p.get("type") == "text"
        )
        if role == "user":
            lc_messages.append(HumanMessage(content=text))
        else:
            lc_messages.append(AIMessage(content=text))
    return lc_messages


def _build_a2a_response(task_id: str, text: str) -> Dict:
    """A2A v0.3.0 の Task 完了レスポンスを構築する。"""
    return {
        "id": task_id,
        "status": {
            "state": "completed",
        },
        "artifacts": [
            {
                "artifactId": str(uuid.uuid4()),
                "parts": [
                    {
                        "type": "text",
                        "text": text,
                    }
                ],
            }
        ],
    }


# ─────────────────────────────────────────────
# FastAPI アプリケーション
# ─────────────────────────────────────────────

app = FastAPI(
    title="KI Web検索エージェント (A2A Server)",
    description="A2A プロトコル v0.3.0 準拠の LangGraph Web 検索エージェントサーバー",
    version="1.0.0",
)

# ─────────────────────────────────────────────
# Agent Card エンドポイント
# wxO が「orchestrate agents discover」でメタデータを取得する際に使用
# ─────────────────────────────────────────────

AGENT_CARD = {
    "name": "ki-web-search-agent-a2a",
    "displayName": "KI Web検索エージェント (A2A)",
    "description": (
        "DuckDuckGo を使ったWeb検索ができる LangGraph エージェント。"
        "Groq（llama-3.3-70b-versatile）を LLM として使用します。"
    ),
    "url": os.environ.get("AGENT_BASE_URL", "https://ki-a2a-agent-production.up.railway.app"),
    "version": "1.0.0",
    "capabilities": {
        "streaming": False,
        "pushNotifications": False,
        "stateTransitionHistory": False,
    },
    "defaultInputModes": ["text/plain"],
    "defaultOutputModes": ["text/plain"],
    "skills": [
        {
            "id": "web-search",
            "name": "Web検索",
            "description": "DuckDuckGo を使って最新のWeb情報を検索します。",
            "inputModes": ["text/plain"],
            "outputModes": ["text/plain"],
        }
    ],
}


@app.get("/.well-known/agent-card.json")
async def get_agent_card():
    """A2A Agent Card を返す。"""
    return JSONResponse(content=AGENT_CARD)


# ─────────────────────────────────────────────
# JSON-RPC 2.0 エンドポイント（A2A メインエンドポイント）
# wxO はここに message/send リクエストを送信する
# ─────────────────────────────────────────────

@app.post("/")
async def jsonrpc_handler(request: Request):
    """
    A2A v0.3.0 JSON-RPC 2.0 エンドポイント。
    サポートメソッド:
      - message/send  : ユーザーメッセージを受け取り、エージェントの応答を返す
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None},
        )

    jsonrpc_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    # ── message/send ──────────────────────────────────────────────
    if method == "message/send":
        try:
            message = params.get("message", {})
            task_id = params.get("taskId") or str(uuid.uuid4())

            # A2A の messages 形式を LangChain 形式に変換
            # wxO は sendHistory=true の場合に過去の会話も含めて送信してくる
            history: List[Dict] = params.get("history", [])
            all_messages = history + [message]
            lc_messages = _a2a_messages_to_langchain(all_messages)

            if not lc_messages:
                raise ValueError("メッセージが空です")

            # LangGraph エージェントを実行
            result = _agent.invoke({"messages": lc_messages})
            answer = result["messages"][-1].content

            task_response = _build_a2a_response(task_id, answer)

            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": jsonrpc_id,
                "result": task_response,
            })

        except Exception as e:
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": jsonrpc_id,
                "error": {
                    "code": -32000,
                    "message": f"エージェント実行エラー: {str(e)}",
                },
            })

    # ── 未対応メソッド ─────────────────────────────────────────────
    return JSONResponse(content={
        "jsonrpc": "2.0",
        "id": jsonrpc_id,
        "error": {
            "code": -32601,
            "message": f"Method not found: {method}",
        },
    })


# ─────────────────────────────────────────────
# ヘルスチェック
# ─────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "agent": "ki-web-search-agent-a2a", "protocol": "A2A/0.3.0"}


# ─────────────────────────────────────────────
# 起動エントリポイント
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"KI Web検索エージェント A2A サーバーを起動します（ポート: {port}）")
    print(f"Agent Card: http://localhost:{port}/.well-known/agent-card.json")
    print(f"JSON-RPC:   http://localhost:{port}/")
    uvicorn.run(app, host="0.0.0.0", port=port)

# Made with IBM Bob
