from typing import TypedDict, List, Dict, Any
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from harborflow import graph, node, Route, END
import json
import urllib.request


class State(TypedDict):
    query: str
    references: List[Dict[str, Any]]
    summary: str


@graph(state=State, start="decide", finish=END)
class AgenticSearch:
    @node
    def decide(self, state: State):
        q = (state.get("query") or "").strip()
        if not q:
            return Route(goto=END, update={"summary": "空查询", "references": []})
        return Route(goto="search_baidu")

    @node
    def search_baidu(self, state: State):
        api_key = os.getenv("APPBUILDER_API_KEY")
        if not api_key:
            raise RuntimeError("APPBUILDER_API_KEY 未设置")
        url = "https://qianfan.baidubce.com/v2/ai_search/web_search"
        payload = {
            "messages": [{"content": state["query"], "role": "user"}],
            "search_source": "baidu_search_v2",
            "resource_type_filter": [{"type": "web", "top_k": 10}],
            "search_recency_filter": "year",
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "X-Appbuilder-Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read()
        except Exception as e:
            return Route(
                goto="summarize",
                update={
                    "references": [
                        {
                            "title": "请求失败",
                            "url": "",
                            "content": str(e),
                            "date": "",
                        }
                    ]
                },
            )
        try:
            obj = json.loads(body.decode("utf-8"))
        except Exception as e:
            return Route(
                goto="summarize",
                update={
                    "references": [
                        {
                            "title": "响应解析失败",
                            "url": "",
                            "content": str(e),
                            "date": "",
                        }
                    ]
                },
            )
        refs = obj.get("references") or []
        simplified: List[Dict[str, Any]] = []
        for r in refs[:10]:
            simplified.append(
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),
                    "date": r.get("date", ""),
                }
            )
        return Route(goto="summarize", update={"references": simplified})

    @node
    def summarize(self, state: State):
        refs = state.get("references") or []
        if not refs:
            return Route(goto=END, update={"summary": "暂无结果", "references": []})
        lines: List[str] = []
        for r in refs[:10]:
            title = (r.get("title") or "").strip()
            url = (r.get("url") or "").strip()
            desc = (r.get("content") or "").strip()
            if len(desc) > 160:
                desc = desc[:160] + "..."
            lines.append(f"- {title} | {url}\n  {desc}")
        summary = "\n".join(lines)
        return Route(goto=END, update={"summary": summary, "references": refs})


if __name__ == "__main__":
    app = AgenticSearch().compile()
    result = app.invoke({"query": "北京有哪些旅游景区"})
    print(result.get("summary", ""))