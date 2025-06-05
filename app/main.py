from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import uvicorn
import asyncio
from contextlib import asynccontextmanager
from stats_collector import StatsCollector
from db_manager import DatabaseManager
from typing import Dict, List, Optional
import logging
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('.env-local' if os.path.exists('.env-local') else '.env')

# Create a global collector instance
collector = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global collector
    collector = StatsCollector()
    asyncio.create_task(collector.start_polling())
    db_manager = DatabaseManager()
    try:
        await db_manager.init_pool()
        await db_manager.create_tickets_table()
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise e
    finally:
        await db_manager.close_pool()
    yield
    # Shutdown
    if collector:
        await collector.close_session()

app = FastAPI(
    title="Health API",
    description="A secure health check API",
    version="1.0.0",
    docs_url=None,  # Disable Swagger UI in production
    redoc_url=None,  # Disable ReDoc in production
    lifespan=lifespan
)

# Security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # In production, replace with specific hosts
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check(response: Response):
    """
    Health check endpoint that returns server status
    """
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return {"status": "healthy", "message": "Server is up and running"}

@app.get("/tickets/{username}")
async def get_user_tickets(username: str) -> Dict[str, List[Dict[str, int]]]:
    """Get all tickets for a user"""
    db_manager = DatabaseManager()
    try:
        await db_manager.init_pool()
        tickets = await db_manager.get_user_tickets(username.lower())
        return {
            "tickets": [
                {"number": number, "is_valid": is_valid}
                for number, is_valid in tickets
            ]
        }
    except Exception as e:
        logger.error(f"Error getting tickets for {username}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db_manager.close_pool()

@app.get("/tickets")
async def get_all_tickets() -> Dict[str, Dict[str, List[int]]]:
    """Get all valid tickets for all users"""
    db_manager = DatabaseManager()
    try:
        await db_manager.init_pool()
        # Ensure table exists
        await db_manager.create_tickets_table()
        
        async with db_manager.pool.acquire() as conn:
            rows = await conn.fetch(f'''
                SELECT username, ticket_number
                FROM {db_manager.schema}.{db_manager.table_name}
                WHERE is_valid = TRUE
                ORDER BY username, ticket_number
            ''')
            
            tickets_by_user = {}
            for row in rows:
                username = row['username']
                if username not in tickets_by_user:
                    tickets_by_user[username] = []
                tickets_by_user[username].append(row['ticket_number'])
            
            return {"tickets": tickets_by_user}
    except Exception as e:
        logger.error(f"Error getting all tickets: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db_manager.close_pool()

@app.post("/tickets/sync")
async def sync_tickets():
    """Force a sync of all tickets based on current entries"""
    stats_collector = StatsCollector()
    db_manager = DatabaseManager()
    try:
        entries = await stats_collector.calculate_entries()
        await db_manager.init_pool()
        await db_manager.sync_all_tickets(entries)
        return {"status": "success", "message": "Tickets synchronized successfully"}
    except Exception as e:
        logger.error(f"Error syncing tickets: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db_manager.close_pool()

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    db_manager = DatabaseManager()
    try:
        await db_manager.init_pool()
        await db_manager.create_tickets_table()
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise e
    finally:
        await db_manager.close_pool()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    db_manager = DatabaseManager()
    await db_manager.close_pool()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8081, reload=False) 