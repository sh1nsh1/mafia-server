from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class BasePayload(BaseModel):
    """Базовый класс payload'а WebSocket-сообщения"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
    )
