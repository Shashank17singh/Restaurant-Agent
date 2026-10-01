import difflib
import random
from typing import Annotated, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from app.config import settings, logger
from app.models import OrderIntent

# Initialize the LLM based on settings
llm = ChatGroq(model=settings.model, api_key=settings.groq_api_key, temperature=0)

# Constants
ORDER_RETRIES = 3
COOK_RETRIES = 2
SERVE_RETRIES = 2
COOK_SUCCESS_PROB = 0.6
SERVE_SUCCESS_PROB = 0.6

# Default fallback menu just in case none is provided
DEFAULT_MENU: dict[str, int] = {
    "pizza": 5,
    "burger": 3,
    "biryani": 10,
    "dosa": 2,
    "pasta": 0,
}

Status = Literal[
    "new", "awaiting_user", "placed", "confirmed", "partial",
    "unavailable", "cook", "ready", "cook_failed", "serve",
    "complete", "serve_failed", "done", "failed"
]

class OrderDetails(dict):
    pass  # We use standard dict in State, but this helps hint it

class State(dict):
    messages: Annotated[list, add_messages]
    menu: dict[str, int]
    order: dict
    status: Status
    order_retries: int
    cook_retries: int
    serve_retries: int
    final_result: str

def initial_state(menu: dict[str, int] | None = None) -> State:
    """Initializes the graph state with default values and a menu."""
    return {
        "messages": [],
        "menu": menu if menu is not None else dict(DEFAULT_MENU),
        "order": {"dish_name": "", "required_quantity": 0, "available_quantity": 0},
        "status": "new",
        "order_retries": ORDER_RETRIES,
        "cook_retries": COOK_RETRIES,
        "serve_retries": SERVE_RETRIES,
        "final_result": "",
    }

def find_menu_item(name: str, menu: dict[str, int]) -> str | None:
    """Fuzzy-match a dish name to a MENU key. Returns the key, or None if nothing is close."""
    name = name.strip().lower()
    if name in menu:
        return name
    for key in menu:
        if key in name or name in key:
            return key
    close = difflib.get_close_matches(name, menu.keys(), n=1, cutoff=0.6)
    return close[0] if close else None

EXTRACT_PROMPT = """You are the order-taking assistant of a restaurant. You ONLY handle food orders.
Read the user's latest message and classify it.

- If they order a dish, return intent=new_order with dish_name (lowercase, singular) and quantity (1 if not stated).
- If they are agreeing to go ahead with the smaller available quantity that was offered to them
  (e.g. "yes", "ok go ahead", "fine, give me what you have"), return intent=accept_partial.
- If the message is not about ordering food (general questions, chit-chat, coding help...), return intent=unrelated.

Menu (dish -> in stock): {menu}
Was the user just offered a partial order? {partial_offer}
"""

def extract_order(state: State) -> OrderIntent:
    """Ask the LLM to pull dish + quantity (or intent) out of the latest user message."""
    partial_offer = "yes" if state["status"] == "awaiting_user" and state["order"]["available_quantity"] > 0 else "no"
    system = EXTRACT_PROMPT.format(menu=state["menu"], partial_offer=partial_offer)
    structured = llm.with_structured_output(OrderIntent)
    last_user = next(m for m in reversed(state["messages"]) if isinstance(m, HumanMessage))
    return structured.invoke([SystemMessage(content=system), last_user])

def say(instruction: str, state: State) -> str:
    """Ask the LLM to phrase a short message to the customer given the current state."""
    system = (
        "You are the friendly assistant of a restaurant's order system. "
        "Write ONE or TWO short sentences to the customer. No markdown.\n"
        f"Current order: {state['order']}\n"
        f"Retries left -> order: {state['order_retries']}, cook: {state['cook_retries']}, serve: {state['serve_retries']}\n"
        f"What to tell the customer: {instruction}"
    )
    return llm.invoke([SystemMessage(content=system)]).content.strip()

# Nodes
def user_input(state: State, config: RunnableConfig) -> dict:
    """Read the next order from the user. (Mainly for CLI/Testing)."""
    read = config.get("configurable", {}).get("input_fn", input)
    text = read("\nYou: ")
    return {"messages": [HumanMessage(content=text)]}

def llm_node(state: State) -> dict:
    """The brain. Reads status + counters, talks to the user, and decides the next status."""
    status = state["status"]
    order = dict(state["order"])

    if status in ("new", "awaiting_user"):
        parsed = extract_order(state)

        if parsed.intent == "accept_partial" and status == "awaiting_user" and order["available_quantity"] > 0:
            order["required_quantity"] = order["available_quantity"]
            msg = say(f"Confirm we are going ahead with {order['required_quantity']} x {order['dish_name']} and sending it to the kitchen.", {**state, "order": order})
            return {"messages": [AIMessage(content=msg)], "order": order, "status": "cook"}

        if parsed.intent == "new_order" and parsed.dish_name:
            order = {
                "dish_name": parsed.dish_name.strip().lower(),
                "required_quantity": max(1, parsed.quantity or 1),
                "available_quantity": 0,
            }
            return {"order": order, "status": "placed"}

        retries = state["order_retries"] - 1
        if retries <= 0:
            msg = say("Politely say you are a food-ordering assistant only, and since no valid order was placed after 3 attempts you are closing the session.", state)
            return {"messages": [AIMessage(content=msg)], "order_retries": 0, "status": "failed", "final_result": "NOT COMPLETED: no valid order after 3 attempts"}
        msg = say("Politely say you are an AI agent for food ordering only, not a general-purpose assistant, and ask them to place a food order (dish + quantity).", state)
        return {"messages": [AIMessage(content=msg)], "order_retries": retries, "status": "awaiting_user"}

    if status == "confirmed":
        msg = say(f"Confirm the order of {order['required_quantity']} x {order['dish_name']} is available and is being sent to the kitchen.", state)
        return {"messages": [AIMessage(content=msg)], "status": "cook"}

    if status in ("partial", "unavailable"):
        retries = state["order_retries"] - 1
        if retries <= 0:
            msg = say("Apologize: the order could not be fulfilled and all 3 order attempts are used up, so the session is closing.", state)
            return {"messages": [AIMessage(content=msg)], "order_retries": 0, "status": "failed", "final_result": "NOT COMPLETED: order attempts exhausted"}
        if status == "partial":
            instruction = (
                f"Only {order['available_quantity']} of the {order['required_quantity']} {order['dish_name']} requested are available. "
                f"Ask if they want to go ahead with {order['available_quantity']} or place a different order. Mention {retries} attempt(s) left."
            )
        else:
            instruction = f"'{order['dish_name']}' is not available at all. Ask them to place a different order. Mention the menu and {retries} attempt(s) left."
        msg = say(instruction, state)
        return {"messages": [AIMessage(content=msg)], "order_retries": retries, "status": "awaiting_user"}

    if status == "ready":
        msg = say("Say the food is ready and is now being served.", state)
        return {"messages": [AIMessage(content=msg)], "status": "serve"}

    if status == "cook_failed":
        if state["cook_retries"] > 0:
            logger.info(f"Cook failed -> retry cook (cook retries left: {state['cook_retries'] - 1})")
            msg = say("Say there was a problem in the kitchen and the dish is being cooked again.", state)
            return {"messages": [AIMessage(content=msg)], "status": "cook", "cook_retries": state["cook_retries"] - 1}
        msg = say("Apologize sincerely: the kitchen failed to prepare the dish even after retrying, so the order is cancelled.", state)
        return {"messages": [AIMessage(content=msg)], "status": "failed", "final_result": "NOT COMPLETED: cook failed"}

    if status == "complete":
        msg = say("Tell the customer their order is complete and enjoy the meal.", state)
        return {"messages": [AIMessage(content=msg)], "status": "done", "final_result": "COMPLETED"}

    if status == "serve_failed":
        if state["serve_retries"] > 0 and state["cook_retries"] > 0:
            logger.info(f"Serve failed -> retry cook+serve (cook retries left: {state['cook_retries'] - 1}, serve retries left: {state['serve_retries'] - 1})")
            msg = say("Say serving went wrong, the dish is being cooked once more and will be served again.", state)
            return {"messages": [AIMessage(content=msg)], "status": "cook", "cook_retries": state["cook_retries"] - 1, "serve_retries": state["serve_retries"] - 1}
        reason = "serve failed" if state["serve_retries"] <= 0 else "serve failed and cook retries exhausted"
        msg = say(f"Apologize sincerely: {reason}, so the order is cancelled.", state)
        return {"messages": [AIMessage(content=msg)], "status": "failed", "final_result": f"NOT COMPLETED: {reason}"}

    raise ValueError(f"llm node got unexpected status {status!r}")

def order_confirm(state: State) -> dict:
    """Confirms if the requested order is available in the menu and checks quantity."""
    order = dict(state["order"])
    menu = state["menu"]
    match = find_menu_item(order["dish_name"], menu)
    if match:
        order["dish_name"] = match
    available = menu[match] if match else 0
    order["available_quantity"] = available

    if available == 0:
        status = "unavailable"
    elif available < order["required_quantity"]:
        status = "partial"
    else:
        status = "confirmed"

    logger.info(f"order_confirm: {order['dish_name']}: need {order['required_quantity']}, have {available} -> {status}")
    return {"order": order, "status": status}

def _outcome(config: RunnableConfig, key: str, prob: float) -> bool:
    """Determines success or failure of an action, allowing scripted outcomes for testing."""
    scripted = config.get("configurable", {}).get(key)
    if scripted:
        return bool(scripted.pop(0))
    return random.random() < prob

def cook(state: State, config: RunnableConfig) -> dict:
    """Simulates the cooking process, which may randomly fail."""
    if _outcome(config, "cook_outcomes", COOK_SUCCESS_PROB):
        logger.info("cook: success -> ready")
        return {"status": "ready"}
    logger.info("cook: FAILED")
    return {"status": "cook_failed"}

def serve(state: State, config: RunnableConfig) -> dict:
    """Simulates the serving process, which may randomly fail."""
    if _outcome(config, "serve_outcomes", SERVE_SUCCESS_PROB):
        logger.info("serve: success -> complete")
        return {"status": "complete"}
    logger.info("serve: FAILED")
    return {"status": "serve_failed"}

def route_after_llm(state: State) -> str:
    """Determines the next node to execute based on the status set by the LLM node."""
    status = state["status"]
    if status == "awaiting_user":
        return "user_input"
    if status == "placed":
        return "order_confirm"
    if status in ("cook", "serve"):
        return status
    return END

# Build graph
builder = StateGraph(State)
builder.add_node("user_input", user_input)
builder.add_node("llm", llm_node)
builder.add_node("order_confirm", order_confirm)
builder.add_node("cook", cook)
builder.add_node("serve", serve)

builder.add_edge(START, "user_input")
builder.add_edge("user_input", "llm")
builder.add_edge("order_confirm", "llm")
builder.add_edge("cook", "llm")
builder.add_edge("serve", "llm")
builder.add_conditional_edges(
    "llm",
    route_after_llm,
    {"user_input": "user_input", "order_confirm": "order_confirm", "cook": "cook", "serve": "serve", END: END},
)

# Uncompiled builder exported for external compilation (e.g. adding memory)
