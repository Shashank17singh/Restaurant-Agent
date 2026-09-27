from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.models import ChatRequest, ChatResponse
from app.graph import builder, initial_state

app = FastAPI(title="Restaurant Agent API", version="1.0.0")

# Add CORS Middleware so frontend apps can interact with this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory checkpointer for multi-turn conversations
memory = MemorySaver()
compiled_graph = builder.compile(checkpointer=memory, interrupt_before=["user_input"])

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    thread_id = request.thread_id
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}

    # Clean narrow no-break spaces to standard spaces for Windows console rendering
    user_msg_text = request.message.replace("\u202f", " ")

    # Check if this thread already has state
    current_state = compiled_graph.get_state(config)
    if not current_state.values:
        # Initialize state with the user's provided menu or default
        new_state = initial_state(menu=request.menu)
        compiled_graph.update_state(config, new_state)
    else:
        # Optionally update the menu if passed in on subsequent calls
        if request.menu is not None:
            compiled_graph.update_state(config, {"menu": request.menu})

    # Update state with the user's latest message as if they typed it at the interrupt
    compiled_graph.update_state(
        config,
        {"messages": [HumanMessage(content=user_msg_text)]},
        as_node="user_input"
    )

    ai_responses = []
    final_result = None
    status = ""
    seen_messages = len(compiled_graph.get_state(config).values.get("messages", [])) - 1

    try:
        # Stream the graph execution until it interrupts or ends
        for final in compiled_graph.stream(None, config=config, stream_mode="values"):
            # Check for new messages
            messages = final.get("messages", [])
            for m in messages[seen_messages:]:
                if isinstance(m, AIMessage):
                    ai_responses.append(m.content.replace("\u202f", " "))
            seen_messages = len(messages)
            
            final_result = final.get("final_result")
            status = final.get("status", "")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(
        responses=ai_responses,
        status=status,
        final_result=final_result
    )
