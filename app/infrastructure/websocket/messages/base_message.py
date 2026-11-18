from typing import Any
from datetime import datetime

from pydantic import Field, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from domain.enums import WebSocketMessageTypeEnum


class BaseMessage(BaseModel):
    """
    Базовый конверт WebSocket-сообщения.

    Топик и payload задаются в наследниках
    (GameMessage, LobbyMessage, SystemMessage).
    """

    message_type: WebSocketMessageTypeEnum
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    payload: Any

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        from_attributes=True,
    )

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True)
