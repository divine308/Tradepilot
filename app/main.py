from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.core.config import settings
from app.database.database import (
    AsyncSessionLocal,
    init_db,
)
from app.models.autonomous_agent import (
    AutonomousAgentState,
)
from app.agents.autonomous_agent import (
    autonomous_agent,
)
from app.routers import (
    api_keys,
    auth,
    dashboard,
    market,
    trading,
)


@asynccontextmanager
async def lifespan(app: FastAPI):

    # ============================================================
    # DATABASE
    # ============================================================

    await init_db()

    # ============================================================
    # RESTORE AUTONOMOUS AGENT STATE
    # ============================================================

    try:

        async with AsyncSessionLocal() as session:

            result = await session.execute(
                select(
                    AutonomousAgentState.enabled
                ).where(
                    AutonomousAgentState.id == 1
                )
            )

            enabled = result.scalar_one_or_none()

        # --------------------------------------------------------
        # Resume agent if it was ON before backend restart
        # --------------------------------------------------------

        if enabled:

            if settings.alpaca_paper:

                await autonomous_agent.start(
                    persist=False
                )

            else:

                print(
                    "Autonomous agent was previously enabled, "
                    "but Alpaca paper trading is disabled. "
                    "Agent will remain stopped."
                )

        else:

            print(
                "Autonomous agent is disabled."
            )

    except Exception as error:

        print(
            "Failed to restore autonomous agent:",
            error,
        )

    # ============================================================
    # APPLICATION RUNNING
    # ============================================================

    yield

    # ============================================================
    # APPLICATION SHUTDOWN
    # ============================================================

    # IMPORTANT:
    #
    # We intentionally DO NOT change the persistent
    # enabled state here.
    #
    # If the agent was ON before a restart, the database
    # remains ON and the lifespan startup code above
    # will restore it.
    #
    # We only cancel the in-memory asyncio task because
    # the Python process is shutting down anyway.

    if autonomous_agent.task:

        autonomous_agent.running = False

        autonomous_agent.task.cancel()

        try:

            await autonomous_agent.task

        except Exception:

            pass

        autonomous_agent.task = None


app = FastAPI(
    title=settings.app_name,
    description=(
        "AI-powered autonomous trading "
        "agent platform."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API ROUTERS
# ============================================================

app.include_router(auth.router)
app.include_router(api_keys.router)
app.include_router(trading.router)
app.include_router(dashboard.router)
app.include_router(market.router)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():

    return {
        "name": settings.app_name,
        "status": "online",
        "environment": settings.environment,
        "paper_trading": settings.alpaca_paper,
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health():

    return {
        "status": "healthy"
    }