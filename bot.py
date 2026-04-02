import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import discord
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
SOUND_FILE = os.getenv("SOUND_FILE", "sounds/olha-ele-ae.mp3")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
FFMPEG_PATH = os.getenv("FFMPEG_PATH")
DEBOUNCE_SECONDS = float(os.getenv("DEBOUNCE_SECONDS", "1.0"))

if not TOKEN:
    raise RuntimeError("Defina BOT_TOKEN no arquivo .env")

sound_path = Path(SOUND_FILE)
if not sound_path.exists():
    raise RuntimeError(f"Arquivo de som não encontrado: {sound_path.resolve()}")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("olhaeleae-bot")

intents = discord.Intents.none()
intents.guilds = True
intents.voice_states = True

bot = discord.Client(intents=intents)


@dataclass
class GuildAudioWorker:
    guild_id: int
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    play_task: Optional[asyncio.Task] = None
    current_channel_id: Optional[int] = None
    pending_request: Optional[tuple[int, str]] = None
    debounce_tasks: dict[int, asyncio.Task] = field(default_factory=dict)

    async def enqueue(self, member_id: int, channel_id: int, member_name: str) -> None:
        old_task = self.debounce_tasks.get(member_id)
        if old_task and not old_task.done():
            old_task.cancel()

        task = asyncio.create_task(
            self._debounce_then_request(member_id, channel_id, member_name),
            name=f"debounce-{self.guild_id}-{member_id}",
        )
        self.debounce_tasks[member_id] = task

        logger.info(
            "Evento recebido | guild=%s channel=%s member=%s aguardando_debounce=%.1fs",
            self.guild_id,
            channel_id,
            member_name,
            DEBOUNCE_SECONDS,
        )

    async def _debounce_then_request(self, member_id: int, channel_id: int, member_name: str) -> None:
        try:
            await asyncio.sleep(DEBOUNCE_SECONDS)
            await self.request_play(channel_id, member_name)
        except asyncio.CancelledError:
            logger.info(
                "Debounce cancelado | guild=%s member=%s",
                self.guild_id,
                member_name,
            )
            raise
        finally:
            current = self.debounce_tasks.get(member_id)
            if current is asyncio.current_task():
                self.debounce_tasks.pop(member_id, None)

    async def request_play(self, channel_id: int, member_name: str) -> None:
        async with self.lock:
            if self.play_task and not self.play_task.done():
                if self.current_channel_id == channel_id:
                    logger.info(
                        "Mesmo canal já está tocando/foi acionado | guild=%s channel=%s ignorando_repeticao",
                        self.guild_id,
                        channel_id,
                    )
                    return

                self.pending_request = (channel_id, member_name)
                logger.info(
                    "Canal mais recente vai substituir o atual | guild=%s atual=%s novo=%s member=%s",
                    self.guild_id,
                    self.current_channel_id,
                    channel_id,
                    member_name,
                )

                guild = bot.get_guild(self.guild_id)
                voice_client = guild.voice_client if guild else None

                if voice_client and voice_client.is_connected():
                    try:
                        if voice_client.is_playing():
                            voice_client.stop()
                    except Exception:
                        logger.exception("Falha ao interromper áudio atual")

                self.play_task.cancel()
                return

            self.pending_request = None
            self.current_channel_id = channel_id
            self.play_task = asyncio.create_task(
                self._play_once(channel_id, member_name),
                name=f"play-{self.guild_id}-{channel_id}",
            )
            self.play_task.add_done_callback(
                lambda _task: asyncio.create_task(self._start_pending_if_any())
            )

    async def _start_pending_if_any(self) -> None:
        async with self.lock:
            self.play_task = None
            self.current_channel_id = None
            pending = self.pending_request
            self.pending_request = None

        if pending:
            channel_id, member_name = pending
            await self.request_play(channel_id, member_name)

    async def _play_once(self, channel_id: int, member_name: str) -> None:
        guild = bot.get_guild(self.guild_id)
        if guild is None:
            logger.warning("Guild %s não encontrada no cache", self.guild_id)
            return

        channel = guild.get_channel(channel_id)
        if channel is None or not isinstance(channel, discord.VoiceChannel):
            logger.warning("Canal %s inválido ou não é de voz", channel_id)
            return

        me = guild.me
        if me is None:
            logger.warning("Não consegui resolver guild.me para %s", self.guild_id)
            return

        permissions = channel.permissions_for(me)
        if not permissions.connect or not permissions.speak:
            logger.warning(
                "Sem permissão no canal %s | connect=%s speak=%s",
                channel.name,
                permissions.connect,
                permissions.speak,
            )
            return

        voice_client = guild.voice_client

        if voice_client and voice_client.is_connected():
            if voice_client.channel.id != channel.id:
                logger.info(
                    "Mudando do canal %s para %s",
                    voice_client.channel.name,
                    channel.name,
                )
                await voice_client.disconnect(force=True)
                voice_client = None

        if voice_client is None or not voice_client.is_connected():
            logger.info("Conectando em %s por causa de %s", channel.name, member_name)
            voice_client = await channel.connect(self_deaf=True)
        else:
            logger.info("Reutilizando conexão em %s", voice_client.channel.name)

        finished = asyncio.Event()

        def after_playback(error: Optional[Exception]) -> None:
            if error:
                logger.error("Erro durante reprodução: %s", error)
            bot.loop.call_soon_threadsafe(finished.set)

        source = discord.FFmpegPCMAudio(
            str(sound_path.resolve()),
            executable=FFMPEG_PATH or "ffmpeg",
        )

        voice_client.play(source, after=after_playback)

        try:
            await finished.wait()
            logger.info("Áudio finalizado em %s", channel.name)
        except asyncio.CancelledError:
            logger.info("Reprodução cancelada em %s", channel.name)
            raise
        finally:
            current_vc = guild.voice_client
            if current_vc and current_vc.is_connected():
                try:
                    if current_vc.is_playing():
                        current_vc.stop()
                except Exception:
                    pass

                try:
                    await current_vc.disconnect(force=True)
                    logger.info("Saindo do canal %s", channel.name)
                except Exception:
                    logger.exception("Falha ao desconectar do canal %s", channel.name)


workers: dict[int, GuildAudioWorker] = {}


def get_worker(guild_id: int) -> GuildAudioWorker:
    worker = workers.get(guild_id)
    if worker is None:
        worker = GuildAudioWorker(guild_id=guild_id)
        workers[guild_id] = worker
    return worker


@bot.event
async def on_ready() -> None:
    guild_names = ", ".join(g.name for g in bot.guilds) or "nenhuma"
    logger.info("Logado como %s (%s)", bot.user, bot.user.id if bot.user else "sem-id")
    logger.info("Servidores: %s", guild_names)
    logger.info("Som configurado: %s", sound_path.resolve())
    logger.info("Debounce configurado: %.1fs", DEBOUNCE_SECONDS)


@bot.event
async def on_voice_state_update(
    member: discord.Member,
    before: discord.VoiceState,
    after: discord.VoiceState,
) -> None:
    if member.bot:
        return

    if before.channel == after.channel:
        return

    if after.channel is None:
        return

    if not isinstance(after.channel, discord.VoiceChannel):
        return

    worker = get_worker(member.guild.id)
    await worker.enqueue(member.id, after.channel.id, str(member))


async def main() -> None:
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot encerrado manualmente.")