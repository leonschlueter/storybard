from openai import OpenAI
from fastapi import FastAPI
from dotenv import load_dotenv
import os
import uvicorn
import openai

from api.turn import router as turn_router
from database.db_helper import init_db

# Load .env
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Create the client instance
openai_client = OpenAI(api_key=OPENAI_API_KEY)



# Init app
app = FastAPI()

# Inject the OpenAI client globally (via app state)
app.state.openai_client = openai_client

app.include_router(turn_router, prefix="/api")

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_db())
    uvicorn.run(app, host="127.0.0.1", port=8000)
