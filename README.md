# Starting the Webpack build

> ## Development
> ```npm
> npm run dev
> ```

## Production
```npm
npm run prod
```
***

# Building Django statics
```
python3 manage.py collectstatic --noinput --clear
```

run project:
daphne -p 8000 Django.asgi:application

документация:
https://wiki.fromregion.xyz/books/webstreams/page/setup

Run docker command:
docker run -p 8000:8000 -v /root/database:/usr/app/database webstreams:latest

админ:
admin:ChattersAdmin2024

## Recent Updates

### Enhanced Error Handling & Proxy Rotation (v2.1)

#### New Features:
1. **Twitch Token Validation** - Added real-time token validation using Twitch API
2. **Improved Proxy Rotation** - Enhanced automatic proxy switching with retry logic
3. **Better Admin Error Handling** - No more "yellow error pages" for duplicate entries

#### Configuration:

**Twitch API Setup:**
Set the `TWITCH_CLIENT_ID` environment variable or add it to your settings:
```bash
export TWITCH_CLIENT_ID="your_twitch_app_client_id"
```

To get a Twitch Client ID:
1. Go to https://dev.twitch.tv/console/apps
2. Create a new application
3. Copy the Client ID

#### Improvements:
- **Token Validation**: Now validates tokens against Twitch API during admin save
- **Proxy Rotation**: Automatically switches to working proxies (5 attempts with 2s delay)
- **Error Handling**: Graceful error messages instead of Django debug pages
- **Logging**: Comprehensive logging for debugging and monitoring
- **Connection Stability**: Better reconnection logic for failed IRC connections

#### Technical Details:
- Enhanced `ChatManager` with intelligent proxy rotation
- Custom admin forms with proper error handling  
- Twitch API integration for token validation
- Improved logging throughout the system
