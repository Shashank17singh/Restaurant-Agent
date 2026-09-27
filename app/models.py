from typing import Literal, Optional
from pydantic import BaseModel, Field

class OrderIntent(BaseModel):
    """What the LLM extracts from a user message."""
    intent: Literal["new_order", "accept_partial", "unrelated"] = Field(
        description=(
            "new_order: user is ordering a dish with a quantity. "
            "accept_partial: user agrees to take the smaller available quantity. "
            "unrelated: message has nothing to do with ordering food."
        )
    )
    dish_name: Optional[str] = Field(default=None, description="Dish name, lowercase, singular")
    quantity: Optional[int] = Field(default=None, description="Quantity requested (default 1 if omitted)")

class ChatRequest(BaseModel):
    """Payload for the chat endpoint."""
    thread_id: str = Field(..., description="Unique identifier for the conversational thread")
    message: str = Field(..., description="The user's message")
    menu: dict[str, int] | None = Field(default=None, description="Dynamic menu for the restaurant (dish to stock)")

class ChatResponse(BaseModel):
    """Response returned from the chat endpoint."""
    responses: list[str] = Field(description="A list of messages produced by the agent")
    status: str = Field(description="The current status of the order flow")
    final_result: str | None = Field(default=None, description="Final result of the order (if ended)")
