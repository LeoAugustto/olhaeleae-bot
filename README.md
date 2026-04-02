# OlhaEleAe Bot

A Discord bot that joins a voice channel when someone enters, plays a custom sound, and leaves automatically.

Built with Python, `discord.py`, Docker, and deployed 24/7 on Oracle Cloud.

> This project was built with AI assistance during planning, debugging, and deployment.

## Features

- Detects when someone joins a voice channel
- Joins automatically
- Plays a custom sound
- Leaves after playback finishes
- Debounce system to avoid spam from rapid channel switching
- Prioritizes the most recent voice channel event
- Avoids repeated playback for the same channel when triggered almost at the same time
- Docker-ready for cloud deployment

## Current behavior

- If multiple users join the same channel almost at the same time, it plays only once
- If a newer event happens in another channel, the current playback is cancelled and the bot switches to the most recent channel
- Very fast channel switching is handled with debounce

## Tech stack

- Python
- discord.py
- davey
- FFmpeg
- Docker
- Oracle Cloud

## Requirements

- Python 3.11+ for local use
- FFmpeg installed locally if running outside Docker
- Discord bot token
- Docker for container or cloud deployment

## Project structure

- `bot.py` -> bot source code
- `.env.example` -> environment template
- `sounds/olha-ele-ae.mp3` -> default sound
- `Dockerfile` -> container image
- `docker-compose.yml` -> container orchestration

## Environment example

Create a `.env` file based on `.env.example`:

```env
BOT_TOKEN=COLE_AQUI_O_TOKEN_DO_BOT
SOUND_FILE=sounds/olha-ele-ae.mp3
LOG_LEVEL=INFO
DEBOUNCE_SECONDS=1.0
```

## Local setup

1. Install Python
2. Install FFmpeg and add it to PATH
3. Open the project folder
4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Copy `.env.example` to `.env`
6. Edit `.env` with your bot token
7. Run the bot:

```bash
python bot.py
```

## Local auto-restart

### Windows

```bat
start_bot.bat
```

### Linux

```bash
./start_bot.sh
```

## Docker / 24-7 deployment

```bash
docker compose up -d --build
```

Check logs:

```bash
docker compose logs -f
```

Stop the bot:

```bash
docker compose down
```

## Invite the bot

Add the bot to your server:

[Add OlhaEleAe Bot](https://discord.com/oauth2/authorize?client_id=1489092018541166648)

## Notes

- Keep your `.env` private
- Never publish your bot token
- For production, Docker deployment is recommended

## Future ideas

- Per-server sound configuration
- Slash commands for setup
- Cooldown customization
- Admin panel or dashboard

## License

MIT
