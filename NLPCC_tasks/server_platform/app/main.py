from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from logs import server_logger as logger

# Import routers and logger
from .api import agents, backtest, funds, live, reporting
from .core.backtest import backtest_sessions, load_historical_sessions
from .core.data_loader import init_data_loader
from reporting.fund_arena import warm_up_report_cache

# --- FastAPI App Initialization ---
app = FastAPI(
    title="LLM Agent Trading Arena API",
    description="An API for running backtests and live paper trading of LLM-powered trading agents.",
    version="0.1.0",
)


# --- Event Handlers ---
# Global flag to track if initialization has been done (prevents duplicate loading in multi-worker mode)
_initialized = False
_initialization_complete = False

@app.on_event("startup")
async def startup_event():
    """Handles application startup events."""
    global _initialized, _initialization_complete
    
    if _initialized:
        logger.debug("Already initialized, skipping startup initialization")
        return
    
    logger.info("Server platform is starting up...")
    try:
        from config import DATA_DIRS

        # Initialize data loader (only if not already initialized)
        init_data_loader(str(DATA_DIRS["PRICE_DATA"]), str(DATA_DIRS["NEWS_DATA"]))
        logger.info("DataLoader initialized successfully.")
        
        # Load historical sessions (only once at startup)
        load_historical_sessions(force_reload=True)
        logger.info(f"Loaded {len(backtest_sessions)} backtest sessions")
        
        # Mark as initialized
        _initialized = True
        
        warm_up_report_cache()
        
        # Mark initialization as complete - server is now ready to accept requests
        _initialization_complete = True
        
        logger.info("Server startup complete - all data loaded and cache warmed")
    except Exception as e:
        logger.critical(f"Failed to initialize: {e}", exc_info=True)
        _initialization_complete = True  # Still mark as complete so server can serve (even if degraded)


@app.on_event("shutdown")
async def shutdown_event():
    """Handles application shutdown events."""
    logger.info("Server platform is shutting down.")


# --- API Routers ---
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["backtest"])
app.include_router(live.router, prefix="/api/live", tags=["live"])
app.include_router(funds.router, prefix="/api/funds", tags=["funds"])
app.include_router(reporting.router, prefix="/api/reports", tags=["reports"])


# --- Root and Health Check Endpoints ---
@app.get("/api")
def read_root():
    """Provides basic API information."""
    return {"message": "Welcome to the LLM Agent Trading Arena API", "version": "0.1.0"}


@app.get("/api/health")
def health_check():
    """Provides a simple health check endpoint."""
    return {"status": "healthy", "service": "llm_agent_trading_arena"}


@app.get("/api/health/ready")
async def readiness_check():
    """
    Provides a readiness check endpoint.
    Returns 200 only after all data loading and cache warming is complete.
    Frontend should poll this endpoint before fetching visualization data.
    """
    if not _initialization_complete:
        return JSONResponse(
            status_code=503,
            content={"status": "initializing", "ready": False}
        )
    return {"status": "ready", "ready": True}


# --- Static Files for Frontend ---
frontend_dir = Path(__file__).parent.parent.parent / "frontend"
dist_dir = frontend_dir / "dist"


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
            if response.status_code == 404:
                raise HTTPException(status_code=404)
            return response
        except Exception:
            # For any path not found (404), serve index.html for client-side routing.
            # This handles SPA routing like /ui/leaderboard
            headers = {
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            }
            return FileResponse(self.directory / "index.html", headers=headers)


if dist_dir.exists() and dist_dir.is_dir():
    app.mount("/ui", SPAStaticFiles(directory=dist_dir, html=True), name="ui")
    logger.info(f"Serving production frontend from: {dist_dir}")
else:
    logger.warning(f"Frontend 'dist' directory not found at: {dist_dir}. UI will not be available.")
    logger.warning("Please run 'npm run build' in the 'frontend' directory.")
