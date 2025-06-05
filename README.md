# Twitch Giveaway Ticket System

A FastAPI-based system for managing Twitch giveaway tickets based on user actions (follows, subscriptions, and gifted subscriptions).

## Features

- Automatic ticket allocation based on user actions:
  - Follows: 1 entry
  - Subscriptions: 5 entries
  - Gifted Subscriptions: 5 entries per gift (to the gifter)
- Monthly ticket tables (e.g., `tickets_202506` for June 2025)
- Automatic ticket invalidation when users lose entries
- Real-time ticket synchronization
- Excluded users support
- PostgreSQL database integration

## Prerequisites

- Python 3.8+
- PostgreSQL
- Docker and Docker Compose (for containerized deployment)

## Environment Variables

Create a `.env-local` file with the following variables:

```env
# API Configuration
API_BASE_URL=http://host.docker.internal:8000
ENDPOINT_SUBSCRIBERS=/subscribers
ENDPOINT_FOLLOWERS=/followers
ENDPOINT_GIFT_SUBS=/gift-subs

# Polling Configuration
POLLING_INTERVAL=30  # in seconds

# Excluded Users
EXCLUDED_USERS=username1,username2

# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=giveaway
DB_USER=postgres
DB_PASSWORD=postgres
DB_SCHEMA=public
```

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up the database:
   ```bash
   # Create the database
   createdb giveaway
   ```

## Running the Application

### Local Development

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8081
```

### Docker

```bash
docker-compose up --build
```

## API Endpoints

### Health Check
```http
GET /health
```
Returns the health status of the API.

### Get User Tickets
```http
GET /tickets/{username}
```
Returns all tickets for a specific user.

Response:
```json
{
    "tickets": [
        {
            "number": 1,
            "is_valid": true
        },
        {
            "number": 2,
            "is_valid": true
        }
    ]
}
```

### Get All Tickets
```http
GET /tickets
```
Returns all valid tickets for all users.

Response:
```json
{
    "tickets": {
        "user1": [1, 2, 3],
        "user2": [4, 5]
    }
}
```

### Sync Tickets
```http
POST /tickets/sync
```
Forces a synchronization of all tickets based on current entries.

Response:
```json
{
    "status": "success",
    "message": "Tickets synchronized successfully"
}
```

## Ticket System Logic

1. **Entry Calculation**:
   - Follows: 1 entry
   - Subscriptions: 5 entries
   - Gifted Subscriptions: 5 entries per gift (to the gifter)

2. **Ticket Management**:
   - Tickets are stored in monthly tables (e.g., `tickets_202506`)
   - Each ticket has a unique number, username, and validity status
   - Tickets are invalidated when users lose entries
   - New tickets are added when users gain entries
   - Lowest ticket numbers are invalidated first when reducing entries

3. **Synchronization**:
   - Occurs every 30 seconds (configurable)
   - Validates all tickets against current entries
   - Invalidates tickets for users who shouldn't have any
   - Adds new tickets for users who need more
   - Maintains ticket number sequence

## Security

- CORS enabled for all origins (configurable)
- Trusted host middleware
- Security headers on responses
- Environment variable configuration
- Excluded users support

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request