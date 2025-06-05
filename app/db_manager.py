import asyncpg
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
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

class DatabaseManager:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.current_month = datetime.now().strftime("%Y%m")
        self.table_name = f"tickets_{self.current_month}"
        self.schema = os.getenv('DB_SCHEMA', 'public')

    async def init_pool(self):
        """Initialize the database connection pool"""
        if not self.pool:
            self.pool = await asyncpg.create_pool(
                host=os.getenv('DB_HOST', 'localhost'),
                port=int(os.getenv('DB_PORT', 5432)),
                database=os.getenv('DB_NAME', 'giveaway'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', 'postgres')
            )

    async def close_pool(self):
        """Close the database connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def create_tickets_table(self):
        """Create the tickets table if it doesn't exist"""
        async with self.pool.acquire() as conn:
            # Create schema if it doesn't exist
            await conn.execute(f'''
                CREATE SCHEMA IF NOT EXISTS {self.schema}
            ''')
            
            # Create table in the specified schema
            await conn.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.schema}.{self.table_name} (
                    ticket_number INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    is_valid BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    async def get_next_ticket_number(self) -> int:
        """Get the next available ticket number"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(f'''
                SELECT COALESCE(MAX(ticket_number), 0) + 1
                FROM {self.schema}.{self.table_name}
            ''')
            return result

    async def get_user_tickets(self, username: str) -> List[Tuple[int, bool]]:
        """Get all tickets for a user"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(f'''
                SELECT ticket_number, is_valid
                FROM {self.schema}.{self.table_name}
                WHERE username = $1
                ORDER BY ticket_number
            ''', username.lower())
            return [(row['ticket_number'], row['is_valid']) for row in rows]

    async def add_tickets(self, username: str, count: int):
        """Add new tickets for a user"""
        async with self.pool.acquire() as conn:
            # Get the next ticket number
            next_ticket = await self.get_next_ticket_number()
            
            # Insert new tickets
            for i in range(count):
                await conn.execute(f'''
                    INSERT INTO {self.schema}.{self.table_name} (ticket_number, username)
                    VALUES ($1, $2)
                ''', next_ticket + i, username.lower())

    async def invalidate_ticket(self, username: str):
        """Invalidate the lowest numbered ticket for a user"""
        async with self.pool.acquire() as conn:
            await conn.execute(f'''
                UPDATE {self.schema}.{self.table_name}
                SET is_valid = FALSE
                WHERE username = $1
                AND ticket_number = (
                    SELECT MIN(ticket_number)
                    FROM {self.schema}.{self.table_name}
                    WHERE username = $1
                    AND is_valid = TRUE
                )
            ''', username.lower())

    async def sync_user_tickets(self, username: str, required_entries: int):
        """Sync a user's tickets to match their required entries"""
        async with self.pool.acquire() as conn:
            # Get all tickets for the user, ordered by ticket number
            rows = await conn.fetch(f'''
                SELECT ticket_number, is_valid
                FROM {self.schema}.{self.table_name}
                WHERE username = $1
                ORDER BY ticket_number
            ''', username.lower())
            
            current_tickets = [(row['ticket_number'], row['is_valid']) for row in rows]
            valid_tickets = sum(1 for _, is_valid in current_tickets if is_valid)
            
            if valid_tickets > required_entries:
                # Need to invalidate some tickets, starting with the lowest numbers
                tickets_to_invalidate = valid_tickets - required_entries
                for ticket_number, is_valid in current_tickets:
                    if tickets_to_invalidate <= 0:
                        break
                    if is_valid:
                        await conn.execute(f'''
                            UPDATE {self.schema}.{self.table_name}
                            SET is_valid = FALSE
                            WHERE username = $1 AND ticket_number = $2
                        ''', username.lower(), ticket_number)
                        tickets_to_invalidate -= 1
            
            elif valid_tickets < required_entries:
                # Need to add more tickets
                tickets_to_add = required_entries - valid_tickets
                next_ticket = await self.get_next_ticket_number()
                
                for i in range(tickets_to_add):
                    await conn.execute(f'''
                        INSERT INTO {self.schema}.{self.table_name} (ticket_number, username)
                        VALUES ($1, $2)
                    ''', next_ticket + i, username.lower())

    async def sync_all_tickets(self, entries: Dict[str, int]):
        """Sync all users' tickets to match their required entries"""
        await self.init_pool()
        try:
            await self.create_tickets_table()
            
            # First, get all users who have tickets in the database
            async with self.pool.acquire() as conn:
                # Get all users with tickets
                rows = await conn.fetch(f'''
                    SELECT DISTINCT username
                    FROM {self.schema}.{self.table_name}
                    WHERE is_valid = TRUE
                ''')
                users_with_tickets = {row['username'] for row in rows}
                
                # Get users who should have tickets (from entries)
                users_with_entries = set(entries.keys())
                
                # Find users who have tickets but shouldn't
                users_to_invalidate = users_with_tickets - users_with_entries
                
                # Invalidate all tickets for users who shouldn't have any
                for username in users_to_invalidate:
                    await conn.execute(f'''
                        UPDATE {self.schema}.{self.table_name}
                        SET is_valid = FALSE
                        WHERE username = $1
                    ''', username)
                
                # Now sync tickets for users who should have them
                for username, entry_count in entries.items():
                    await self.sync_user_tickets(username, entry_count)
        finally:
            await self.close_pool() 