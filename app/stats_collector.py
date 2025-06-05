import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
import aiohttp
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from collections import defaultdict
from db_manager import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('.env-local' if os.path.exists('.env-local') else '.env')

class StatsCollector:
    def __init__(self):
        self.base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
        self.endpoints = {
            'subscribers': os.getenv('ENDPOINT_SUBSCRIBERS', '/subscribers'),
            'followers': os.getenv('ENDPOINT_FOLLOWERS', '/followers'),
            'gift_subs': os.getenv('ENDPOINT_GIFT_SUBS', '/gift-subs')
        }
        self.excluded_users: Set[str] = {
            username.lower() for username in 
            os.getenv('EXCLUDED_USERS', '').split(',') 
            if username.strip()
        }
        self.db_manager = DatabaseManager()
        self.session: Optional[aiohttp.ClientSession] = None

    async def init_session(self):
        """Initialize the aiohttp session"""
        if not self.session:
            connector = aiohttp.TCPConnector(ssl=False)
            self.session = aiohttp.ClientSession(connector=connector)

    async def close_session(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None

    async def fetch_endpoint(self, endpoint: str) -> Dict:
        """Fetch data from a specific endpoint"""
        try:
            async with self.session.get(f"{self.base_url}{endpoint}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Error fetching {endpoint}: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Exception while fetching {endpoint}: {str(e)}")
            return {}

    async def calculate_entries(self) -> Dict[str, int]:
        """Calculate entries for each user"""
        entries: Dict[str, int] = {}
        
        # Get followers (1 entry each)
        followers = await self.fetch_endpoint(self.endpoints['followers'])
        if followers and 'followers' in followers:
            for follower in followers['followers']:
                username = follower['username'].lower()
                if username not in self.excluded_users:
                    entries[username] = entries.get(username, 0) + 1

        # Get subscribers (5 entries each)
        subscribers = await self.fetch_endpoint(self.endpoints['subscribers'])
        if subscribers and 'subscribers' in subscribers:
            for subscriber in subscribers['subscribers']:
                username = subscriber['username'].lower()
                if username not in self.excluded_users:
                    entries[username] = entries.get(username, 0) + 5

        # Get gifted subs (5 entries per gifted sub for the gifter)
        gift_subs = await self.fetch_endpoint(self.endpoints['gift_subs'])
        if gift_subs and 'gifts' in gift_subs:
            for gift in gift_subs['gifts']:
                username = gift['gifter'].lower()
                if username not in self.excluded_users:
                    entries[username] = entries.get(username, 0) + (5 * gift['quantity'])

        return entries

    def log_entries(self, entries: Dict[str, int]):
        """Log the entries list"""
        logger.info("Giveaway Entries:")
        for username, count in sorted(entries.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"{username}: {count}")

    async def collect_stats(self):
        """Collect and process stats"""
        await self.init_session()
        try:
            entries = await self.calculate_entries()
            self.log_entries(entries)
            
            # Sync tickets with the database
            await self.db_manager.sync_all_tickets(entries)
        finally:
            await self.close_session()

    async def start_polling(self):
        """Start periodic polling of stats"""
        while True:
            await self.collect_stats()
            await asyncio.sleep(int(os.getenv('POLLING_INTERVAL', 30)))

async def main():
    collector = StatsCollector()
    try:
        await collector.start_polling()
    except KeyboardInterrupt:
        logger.info("Stats collection stopped by user")
    finally:
        await collector.close_session()

if __name__ == "__main__":
    asyncio.run(main()) 