"""
Nuguri's Casino 봇 - 메인 실행 파일
"""
import discord
from discord.ext import commands
import asyncio
import logging
from config import Config
from utils.logger import setup_logger
from database.db_manager import DatabaseManager

# 로거 설정
setup_logger()
logger = logging.getLogger(__name__)

# 봇 설정
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True  # 멤버 정보 접근 권한

bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    description="Nuguri's casino에 오신것을 환영합니다."
)


@bot.event
async def on_ready():
    """봇이 준비되었을 때"""
    logger.info(f'{bot.user} 로그인 완료!')
    logger.info(f'Bot ID: {bot.user.id}')
    logger.info(f'연결된 서버: {len(bot.guilds)}개')
    logger.info('------')
    
    # 슬래시 커맨드 동기화
    try:
        synced = await bot.tree.sync()
        logger.info(f"동기화된 슬래시 커맨드: {len(synced)}개")
        for cmd in synced:
            logger.info(f"  - {cmd.name}")
    except Exception as e:
        logger.error(f"커맨드 동기화 실패: {e}")


@bot.event
async def on_command_error(ctx, error):
    """명령어 에러 핸들링"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("존재하지 않는 명령어입니다.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"필수 인자가 누락되었습니다: {error.param}")
    else:
        logger.error(f"명령어 에러: {error}")
        await ctx.send(f"오류가 발생했습니다: {str(error)}")


@bot.event
async def on_guild_remove(guild):
    """봇이 서버에서 추방되거나 서버가 삭제될 때"""
    logger.info(f"서버에서 제거됨: {guild.name} (ID: {guild.id})")


async def load_extensions():
    """Cog 확장 로드"""
    extensions = [
        'cogs.roulette',  # 러시안 룰렛 게임
        'cogs.blackjack',  # 블랙잭 게임
        'cogs.slot_machine', #슬롯머신 게임
        'cogs.admin',  # 관리자 명령어
    ]
    
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            logger.info(f'✓ 로드 완료: {ext}')
        except Exception as e:
            logger.error(f'✗ 로드 실패 {ext}: {e}')


async def main():
    """메인 실행 함수"""
    # 설정 검증
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"설정 오류: {e}")
        logger.error("'.env' 파일을 확인하세요.")
        return
    
    # 데이터베이스 초기화
    try:
        db_manager = DatabaseManager()
        await db_manager.init_database()
        logger.info("데이터베이스 초기화 완료")
    except Exception as e:
        logger.error(f"데이터베이스 초기화 실패: {e}")

    
    # Cog 로드 및 봇 실행
    async with bot:
        await load_extensions()
        await bot.start(Config.BOT_TOKEN)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("봇 종료 중...")
    except Exception as e:
        logger.error(f"봇 실행 오류: {e}")