from pydantic import BaseModel

class PlayerTurnInput(BaseModel):
    input_text: str
