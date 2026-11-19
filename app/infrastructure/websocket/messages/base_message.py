from datetime import datetime

from pydantic import Field, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class BaseMessage(BaseModel):
    """
    Базовый конверт WebSocket-сообщения.

    Топик задаётся в наследниках, тип сообщения и payload — в конкретном
    классе сообщения.
    """

    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        from_attributes=True,
    )

    def to_json(self) -> str:
        """Конвертация в JSON строку"""

        return self.model_dump_json(by_alias=True)
