import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from app.graph import builder, initial_state

# Compile graph for testing without checkpointer (tests run in one go)
graph = builder.compile()

def run_simulation(user_inputs: list[str], cook_outcomes: list[bool] | None = None, serve_outcomes: list[bool] | None = None):
    inputs = list(user_inputs)

    def fake_input(prompt: str) -> str:
        return inputs.pop(0) if inputs else "bye"

    config: RunnableConfig = {
        "configurable": {
            "input_fn": fake_input,
            "cook_outcomes": list(cook_outcomes or []),
            "serve_outcomes": list(serve_outcomes or [])
        },
        "recursion_limit": 100
    }
    
    final_state = None
    for final in graph.stream(initial_state(), config=config, stream_mode="values"):
        final_state = final

    return final_state

def test_tc1():
    """TC1: unrelated -> partial -> reject & reorder -> unavailable => END (order retries)"""
    s = run_simulation(["what is the weather today?", "I want 5 burgers", "no, give me 2 pasta instead"])
    assert s["order_retries"] == 0
    assert s["final_result"] == "NOT COMPLETED: order attempts exhausted"

def test_tc2():
    """TC2: available -> cook fail, cook ok -> serve fail -> cook ok -> serve ok => SUCCESS"""
    s = run_simulation(["2 pizzas"], cook_outcomes=[False, True, True], serve_outcomes=[False, True])
    assert s["final_result"] == "COMPLETED"
    assert s["cook_retries"] == 0 
    assert s["serve_retries"] == 1

def test_tc3():
    """TC3: partial -> reject -> available -> cook fail, ok -> serve fail -> cook ok -> serve fail => FAIL (cook exhausted)"""
    s = run_simulation(["5 burgers", "no, give me 1 dosa"], cook_outcomes=[False, True, True], serve_outcomes=[False, False])
    assert s["final_result"] == "NOT COMPLETED: serve failed and cook retries exhausted"
    assert s["cook_retries"] == 0
