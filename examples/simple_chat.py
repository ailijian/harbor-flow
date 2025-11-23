from typing import TypedDict, List, Tuple

from harborflow import graph, node, Route, END


class State(TypedDict):
    messages: List[Tuple[str, str]]


@graph(state=State, start="agent", finish=END)
class SimpleChat:
    @node
    def agent(self, state: State):
        last = state["messages"][-1][1] if state["messages"] else "none"
        reply = f"echo: {last}"
        return Route.to("agent", messages=state["messages"] + [("assistant", reply)])