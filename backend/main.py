# NOT the active entry point. Use: uvicorn api.main:app
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.websocket.manager import ConnectionManager
from backend.websocket.emitter import EventEmitter
from backend.state.store import StateStore
from backend.pubsub.manager import RedisPubSubManager
from backend.integration.engine_connector import EngineConnector
from backend.api.routes import router
from backend.api.demo import demo_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Redis (graceful fallback if Redis not running)
    try:
        await app.state.redis_manager.initialize()
        await app.state.manager.initialize()
    except Exception as e:
        print(f"[WARNING] Redis unavailable, running without pub/sub: {e}")
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core components
redis_manager = RedisPubSubManager()
manager = ConnectionManager(redis_manager)
emitter = EventEmitter(manager)
state_store = StateStore()
engine_connector = EngineConnector(state_store, emitter)

# Attach to app.state so routes can access them
app.state.redis_manager = redis_manager
app.state.manager = manager
app.state.emitter = emitter
app.state.state_store = state_store
app.state.engine_connector = engine_connector

app.include_router(router, prefix="/api")
app.include_router(demo_router, prefix="/api")


@app.get("/")
def home():
    return {"message": "Backend running"}


@app.websocket("/ws/{workflow_id}")
async def websocket_endpoint(websocket: WebSocket, workflow_id: str,
                              client_type: str = "frontend"):
    await manager.connect(websocket, workflow_id, client_type)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(workflow_id)
