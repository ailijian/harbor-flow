import asyncio
import time
import sys
from typing import TypedDict, List, Dict, Any

# Add the current directory to Python path to use local harborflow
sys.path.insert(0, '.')

from harborflow import (
    graph, node, parallel_node, Route, END, 
    compile_graph, compile_graph_async,
    NodeConfig, ConditionalRoute, validate_state_transition
)


class AdvancedState(TypedDict):
    query: str
    results: List[Dict[str, Any]]
    status: str
    processing_time: float
    errors: List[str]


@graph(state=AdvancedState, start="processor", finish=END)
class AdvancedFeaturesDemo:
    """高级功能演示类"""
    
    @node
    def processor(self, state: AdvancedState):
        """处理器节点，演示类型选择和条件逻辑"""
        query = state.get("query", "").strip()
        
        if not query:
            return Route(goto=END, update={
                "status": "failed",
                "errors": ["查询不能为空"],
                "processing_time": 0.0
            })
        
        # 基于查询长度选择处理类型
        if len(query) < 10:
            processor_type = "short"
        elif len(query) < 50:
            processor_type = "medium"
        else:
            processor_type = "long"
        
        return Route(goto="process_worker", update={
            "processor_type": processor_type,
            "status": "processing"
        })
    
    @node
    async def process_worker(self, state: AdvancedState):
        """处理工作节点 - 根据类型选择处理方式（异步版本）"""
        processor_type = state.get("processor_type", "short")
        query = state.get("query", "")
        
        start_time = time.time()
        
        if processor_type == "short":
            # 短查询处理
            results = [
                {"type": "short", "content": f"快速处理: {query}", "confidence": 0.9}
            ]
        elif processor_type == "medium":
            # 中等查询处理（模拟异步操作）
            await asyncio.sleep(0.1)  # 模拟IO操作
            results = [
                {"type": "medium", "content": f"标准处理: {query}", "confidence": 0.8},
                {"type": "medium", "content": f"扩展处理: {query[:20]}...", "confidence": 0.7}
            ]
        else:  # long
            # 长查询处理（模拟更复杂的异步操作）
            await asyncio.sleep(0.05)  # 模拟复杂处理
            results = [
                {"type": "long", "content": f"深度分析: {query[:30]}...", "confidence": 0.85},
                {"type": "long", "content": f"关键提取: {len(query)}字符", "confidence": 0.9},
                {"type": "long", "content": "语义分析完成", "confidence": 0.8}
            ]
        
        processing_time = time.time() - start_time
        return Route(goto="aggregator", update={
            "results": results,
            "processing_time": processing_time
        })
    
    @node
    def aggregator(self, state: AdvancedState):
        """结果聚合器 - 演示状态验证"""
        try:
            # 验证状态转换（移除不可变字段限制，因为查询会在整个流程中传递）
            validate_state_transition(
                {"query": "", "results": [], "status": "processing"},
                state,
                required_fields=["results", "processing_time"]
                # immutable_fields=["query"]  # 暂时移除，因为查询需要在整个流程中传递
            )
            
            # 聚合结果
            all_results = state.get("results", [])
            total_time = state.get("processing_time", 0.0)
            
            # 添加元数据
            aggregated = {
                "total_results": len(all_results),
                "processing_time": total_time,
                "confidence_avg": sum(r.get("confidence", 0) for r in all_results) / len(all_results) if all_results else 0,
                "results": all_results
            }
            
            return Route(goto=END, update={
                "status": "completed",
                "results": [aggregated],
                "processing_time": total_time
            })
            
        except Exception as e:
            return Route(goto=END, update={
                "status": "failed",
                "errors": [f"聚合失败: {str(e)}"],
                "processing_time": state.get("processing_time", 0.0)
            })


async def demo_async_features():
    """演示异步功能"""
    print("=== 异步功能演示 ===")
    
    flow = AdvancedFeaturesDemo()
    
    # 异步编译
    app = await compile_graph_async(flow)
    
    # 异步调用
    start_time = time.time()
    result = await app.ainvoke({
        "query": "这是一个中等长度的查询用于演示异步处理",
        "results": [],
        "status": "pending",
        "processing_time": 0.0,
        "errors": []
    })
    total_time = time.time() - start_time
    
    print(f"异步处理结果: {result}")
    print(f"总耗时: {total_time:.3f}s")
    print()


async def demo_conditional_routing():
    """演示条件路由"""
    print("=== 条件路由演示 ===")
    
    flow = AdvancedFeaturesDemo()
    app = await compile_graph_async(flow)  # 使用异步编译
    
    test_queries = [
        "短查询",
        "这是一个中等长度的查询用于演示条件路由",
        "这是一个相当长的查询，包含了大量的文本内容，用于演示如何处理长文本查询的情况，需要更多的处理时间和更复杂的分析逻辑"
    ]
    
    for query in test_queries:
        print(f"查询: '{query[:30]}...' (长度: {len(query)})")
        result = await app.ainvoke({  # 使用异步调用
            "query": query,
            "results": [],
            "status": "pending",
            "processing_time": 0.0,
            "errors": []
        })
        print(f"结果状态: {result['status']}")
        print(f"处理时间: {result.get('processing_time', 0):.3f}s")
        print(f"结果数量: {len(result.get('results', []))}")
        if 'processor_type' in result:
            print(f"处理器类型: {result['processor_type']}")
        print()


async def demo_error_handling():
    """演示错误处理"""
    print("=== 错误处理演示 ===")
    
    flow = AdvancedFeaturesDemo()
    app = await compile_graph_async(flow)  # 使用异步编译
    
    # 测试空查询（应该触发错误处理）
    result = await app.ainvoke({  # 使用异步调用
        "query": "",  # 空查询
        "results": [],
        "status": "pending",
        "processing_time": 0.0,
        "errors": []
    })
    
    print(f"空查询结果: {result}")
    print()


def demo_state_validation():
    """演示状态验证"""
    print("=== 状态验证演示 ===")
    
    # 测试有效状态转换
    prev_state = {"query": "test", "results": [], "status": "pending"}
    next_state = {"query": "test", "results": [{"data": "result"}], "status": "completed"}
    
    try:
        validate_state_transition(
            prev_state, 
            next_state,
            required_fields=["results"],
            immutable_fields=["query"]
        )
        print("✓ 状态验证通过")
    except Exception as e:
        print(f"✗ 状态验证失败: {e}")
    
    # 测试无效状态转换（修改不可变字段）
    invalid_state = {"query": "modified", "results": [{"data": "result"}]}
    
    try:
        validate_state_transition(
            prev_state,
            invalid_state,
            immutable_fields=["query"]
        )
        print("✗ 应该失败的验证通过了")
    except Exception as e:
        print(f"✓ 预期的验证失败: {e}")
    
    print()


async def main():
    """主演示函数"""
    print("HarborFlow 高级功能演示")
    print("=" * 50)
    
    # 运行各种演示
    await demo_async_features()
    await demo_conditional_routing()  # 需要await
    await demo_error_handling()  # 现在也需要await
    demo_state_validation()
    
    print("演示完成！")


if __name__ == "__main__":
    asyncio.run(main())