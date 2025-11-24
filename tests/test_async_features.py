import asyncio
import pytest
from typing import TypedDict, List, Dict, Any
from harborflow import graph, node, parallel_node, Route, END, compile_graph, compile_graph_async
from harborflow import NodeConfig, NodeExecutionError, validate_state_transition, ConditionalRoute


class TestState(TypedDict):
    messages: List[str]
    count: int
    results: List[str]


class TestAsyncFeatures:
    """测试异步功能"""
    
    def test_async_node_support(self):
        """测试异步节点支持"""
        @graph(state=TestState, start="async_processor", finish=END)
        class AsyncFlow:
            @node
            async def async_processor(self, state: TestState):
                await asyncio.sleep(0.01)  # 模拟异步操作
                return Route.to("sync_processor", messages=state["messages"] + ["async_processed"])
            
            @node
            def sync_processor(self, state: TestState):
                return Route.finish(messages=state["messages"] + ["sync_processed"])
        
        flow = AsyncFlow()
        app = compile_graph(flow)
        
        # 测试异步调用（应该能正确处理异步节点）
        async def run_async():
            return await app.ainvoke({"messages": ["start"], "count": 0, "results": []})
        
        result = asyncio.run(run_async())
        assert "async_processed" in result["messages"]
        assert "sync_processed" in result["messages"]
    
    @pytest.mark.asyncio
    async def test_async_compile_and_invoke(self):
        """测试异步编译和调用"""
        @graph(state=TestState, start="async_starter", finish=END)
        class AsyncCompiledFlow:
            @node
            async def async_starter(self, state: TestState):
                await asyncio.sleep(0.05)
                return Route.to("middle_node", count=state["count"] + 1)
            
            @node
            def middle_node(self, state: TestState):
                return Route.finish(results=state["results"] + [f"count_{state['count']}"])
        
        flow = AsyncCompiledFlow()
        app = await compile_graph_async(flow)
        
        # 测试异步调用
        result = await app.ainvoke({"messages": [], "count": 0, "results": []})
        assert result["count"] == 1
        assert "count_1" in result["results"]
    
    def test_mixed_sync_async_nodes(self):
        """测试混合同步和异步节点"""
        @graph(state=TestState, start="mixed_start", finish=END)
        class MixedFlow:
            @node
            async def mixed_start(self, state: TestState):
                await asyncio.sleep(0.01)
                return Route.to("sync_middle", messages=state["messages"] + ["async_start"])
            
            @node
            def sync_middle(self, state: TestState):
                return Route.to("async_end", messages=state["messages"] + ["sync_middle"])
            
            @node
            async def async_end(self, state: TestState):
                await asyncio.sleep(0.01)
                return Route.finish(messages=state["messages"] + ["async_end"])
        
        flow = MixedFlow()
        app = compile_graph(flow)
        
        # 使用异步调用处理混合节点
        async def run_async():
            return await app.ainvoke({"messages": ["initial"], "count": 0, "results": []})
        
        result = asyncio.run(run_async())
        expected_messages = ["initial", "async_start", "sync_middle", "async_end"]
        assert result["messages"] == expected_messages


class TestErrorHandling:
    """测试错误处理功能"""
    
    def test_node_execution_error(self):
        """测试节点执行错误处理"""
        @graph(state=TestState, start="error_node", finish=END)
        class ErrorFlow:
            @node
            def error_node(self, state: TestState):
                raise ValueError("测试错误")
        
        flow = ErrorFlow()
        app = compile_graph(flow)
        
        with pytest.raises(Exception):  # LangGraph会包装异常
            app.invoke({"messages": [], "count": 0, "results": []})
    
    def test_node_config_timeout(self):
        """测试节点配置超时"""
        config = NodeConfig(timeout=0.1, max_retries=0)
        
        async def slow_function():
            await asyncio.sleep(0.5)  # 超过超时时间
            return "result"
        
        with pytest.raises(NodeExecutionError):
            asyncio.run(config.execute_with_retry("test_node", slow_function))
    
    def test_node_config_retry(self):
        """测试节点配置重试"""
        attempt_count = 0
        
        def failing_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ValueError(f"尝试 {attempt_count} 失败")
            return f"成功在尝试 {attempt_count}"
        
        config = NodeConfig(max_retries=3, retry_delay=0.01)
        result = asyncio.run(config.execute_with_retry("test_node", failing_function))
        
        assert result == "成功在尝试 3"
        assert attempt_count == 3


class TestStateValidation:
    """测试状态验证功能"""
    
    def test_validate_state_transition_basic(self):
        """测试基础状态验证"""
        prev_state = {"name": "test", "count": 5}
        next_state = {"name": "test", "count": 6, "status": "active"}
        
        # 应该通过验证
        assert validate_state_transition(prev_state, next_state) is True
    
    def test_validate_required_fields(self):
        """测试必需字段验证"""
        prev_state = {"id": 1}
        next_state = {"id": 1, "name": "test"}  # 缺少 required_field
        
        with pytest.raises(Exception) as exc_info:
            validate_state_transition(prev_state, next_state, required_fields=["id", "required_field"])
        
        assert "缺少必需字段" in str(exc_info.value)
    
    def test_validate_immutable_fields(self):
        """测试不可变字段验证"""
        prev_state = {"id": 1, "name": "original"}
        next_state = {"id": 2, "name": "changed"}  # 修改了不可变字段
        
        with pytest.raises(Exception) as exc_info:
            validate_state_transition(prev_state, next_state, immutable_fields=["id", "name"])
        
        assert "不可变字段" in str(exc_info.value)


class TestConditionalRouting:
    """测试条件路由功能"""
    
    def test_conditional_route_basic(self):
        """测试基础条件路由"""
        def is_high_count(state: TestState) -> bool:
            return state["count"] > 5
        
        route = ConditionalRoute.when(is_high_count, "high_count_node", status="high")
        
        high_state = {"messages": [], "count": 10, "results": []}
        low_state = {"messages": [], "count": 3, "results": []}
        
        assert route.evaluate_condition(high_state) is True
        assert route.evaluate_condition(low_state) is False
    
    def test_conditional_route_branch(self):
        """测试条件分支路由"""
        def is_small(state: TestState) -> bool:
            return state["count"] < 5
        
        def is_medium(state: TestState) -> bool:
            return 5 <= state["count"] < 10
        
        def is_large(state: TestState) -> bool:
            return state["count"] >= 10
        
        conditions = [
            (is_large, "large_node"),
            (is_medium, "medium_node"),
            (is_small, "small_node"),
        ]
        
        routes = ConditionalRoute.branch(conditions, default_goto="default_node")
        
        # 验证分支数量
        assert len(routes) == 4  # 3个条件 + 1个默认
        
        # 验证优先级设置（第一个条件优先级最高）
        assert routes[0].priority == 3  # large条件优先级最高（conditions列表长度-索引）
        assert routes[1].priority == 2  # medium条件
        assert routes[2].priority == 1  # small条件
        assert routes[3].priority == 0  # 默认分支优先级最低
    
    @pytest.mark.asyncio
    async def test_async_conditional_route(self):
        """测试异步条件路由"""
        async def async_condition(state: TestState) -> bool:
            await asyncio.sleep(0.01)
            return state["count"] > 5
        
        route = ConditionalRoute.when(async_condition, "async_target")
        
        test_state = {"messages": [], "count": 10, "results": []}
        result = await route.evaluate_condition_async(test_state)
        
        assert result is True


class TestParallelExecution:
    """测试并行执行功能"""
    
    def test_parallel_node_decorator(self):
        """测试并行节点装饰器"""
        @graph(state=TestState, start="parallel_starter", finish=END)
        class ParallelFlow:
            @node
            def parallel_starter(self, state: TestState):
                return Route.to("task_a", results=state["results"] + ["started"])
            
            @parallel_node
            def task_a(self, state: TestState):
                return Route.finish(results=state["results"] + ["task_a_complete"])
        
        flow = ParallelFlow()
        app = compile_graph(flow)
        
        # 测试并行节点装饰器的基本功能（目前主要测试装饰器本身）
        result = app.invoke({"messages": [], "count": 0, "results": []})
        assert "started" in result["results"]
        assert "task_a_complete" in result["results"]
        
        # 验证节点被标记为并行节点
        from harborflow.compile import _iter_nodes
        nodes = _iter_nodes(flow)
        task_a_method = next(method for name, method in nodes if name == "task_a")
        assert getattr(task_a_method, "__hf_is_parallel__", False) == True


def test_type_preservation():
    """测试类型注解保持"""
    from typing import get_type_hints
    
    def original_function(x: int, y: str) -> bool:
        return len(y) > x
    
    # 应用装饰器
    decorated_function = node(original_function)
    
    # 检查类型注解是否保持
    original_hints = get_type_hints(original_function)
    decorated_hints = get_type_hints(decorated_function)
    
    assert original_hints == decorated_hints


if __name__ == "__main__":
    # 运行基础测试
    test = TestAsyncFeatures()
    test.test_async_node_support()
    
    error_test = TestErrorHandling()
    error_test.test_node_execution_error()
    
    validation_test = TestStateValidation()
    validation_test.test_validate_state_transition_basic()
    
    routing_test = TestConditionalRouting()
    routing_test.test_conditional_route_basic()
    
    parallel_test = TestParallelExecution()
    parallel_test.test_parallel_node_decorator()
    
    test_type_preservation()
    
    print("所有基础测试通过！")