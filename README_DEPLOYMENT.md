# Environment Variables for Deployment

## Required Variables

### TELEGRAM_TOKEN (Required)
Your Telegram bot token from BotFather
```
TELEGRAM_TOKEN=your_bot_token_here
```

## Optional Variables

### DATA_DIR (Optional)
Directory for storing bot data (subscribers, link states, etc.)
- Default: `.` (current directory)
- For Railway: use default or set to `/app/data`
```
DATA_DIR=/app/data
```

### POLL_MIN_SEC (Optional)
Minimum seconds between TestFlight checks
- Default: `240` (4 minutes)
```
POLL_MIN_SEC=240
```

### POLL_MAX_SEC (Optional)
Maximum seconds between TestFlight checks
- Default: `360` (6 minutes)
```
POLL_MAX_SEC=360
```

## Railway Deployment
For Railway deployment, only set:
```
TELEGRAM_TOKEN=your_actual_bot_token
```

The bot will automatically use the current directory for data storage, which works correctly in Railway's environment.

## Security Notes
- Never commit the actual TELEGRAM_TOKEN to the repository
- The bot will fail to start if TELEGRAM_TOKEN is not set
- All data files are automatically created in the DATA_DIR when needed