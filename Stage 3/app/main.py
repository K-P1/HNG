from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app import database
from app.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    database.init_db()
    yield
    # Shutdown (nothing to clean up yet)

app = FastAPI(title="Reflective Assistant - Telex Agent", lifespan=lifespan)

# Allow cross-origin calls (useful during Telex/webhook testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
