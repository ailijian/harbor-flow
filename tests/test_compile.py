from typing import TypedDict, List

from harborflow import graph, node, Route, END


def test_compile_graph_sequential():
    class State(TypedDict):
        a: int
        b: int

    @graph(state=State, start="n1", finish=END)
    class Flow:
        @node
        def n1(self, state: State):
            return {"a": 1}

        @node
        def n2(self, state: State):
            return {"b": 2}

    app = Flow().compile()
    out = app.invoke({})
    assert out["a"] == 1
    assert out["b"] == 2


def test_compile_graph_manual_jump():
    class State(TypedDict):
        trace: List[str]

    @graph(state=State, start="a", finish=END)
    class Flow2:
        @node
        def a(self, state: State):
            trace = (state.get("trace") or []) + ["a"]
            return Route.to("c", trace=trace)

        @node
        def b(self, state: State):
            return {}

        @node
        def c(self, state: State):
            trace = (state.get("trace") or [])
            if trace and trace[-1] == "c":
                return {"trace": trace}
            return {"trace": trace + ["c"]}

    app = Flow2().compile()
    out = app.invoke({"trace": []})
    assert out["trace"] == ["a", "c"]


def test_command_direct_return():
    from langgraph.types import Command

    class State(TypedDict):
        x: int
        y: int

    @graph(state=State, start="a", finish=END)
    class Flow3:
        @node
        def a(self, state: State):
            return Command(goto="b", update={"x": 1})

        @node
        def b(self, state: State):
            return {"y": 2}

    app = Flow3().compile()
    out = app.invoke({})
    assert out["x"] == 1
    assert out["y"] == 2


def test_route_with_update_chain():
    class State(TypedDict):
        foo: int
        bar: int

    @graph(state=State, start="a", finish=END)
    class Flow4:
        @node
        def a(self, state: State):
            r = Route.to("b", foo=1)
            return r.with_update(bar=2)

        @node
        def b(self, state: State):
            return {}

    app = Flow4().compile()
    out = app.invoke({})
    assert out["foo"] == 1
    assert out["bar"] == 2