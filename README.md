# Notion Campaign Automation

Automatically sync campaign content from Notion to a content calendar.

## Setup

1. Install dependencies:
```bash
# Python dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Node.js dependencies
npm install
```

2. Configure environment variables in `.env`:
```
NOTION_TOKEN=your_token
CAMPAIGN_STRATEGY_DB_ID=your_db_id
CONTENT_CALENDAR_DB_ID=your_calendar_id
```

3. Deploy:
```bash
serverless deploy
```

## Features

- Automated content syncing from campaigns to content calendar
- Support for images and videos
- Webhook integration for immediate updates
- Scheduled processing every 5 minutes

## Development

To run locally:
```bash
python automation.py
```

## Architecture

- `automation.py`: Core automation logic
- `handler.py`: AWS Lambda handlers
- `serverless.yml`: Infrastructure configuration