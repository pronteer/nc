"""
관리자 명령어 Cog
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from sqlalchemy import select
from database.db_manager import DatabaseManager
from database.models import User

logger = logging.getLogger(__name__)


class AdminCommands(commands.Cog):
    """관리자 전용 명령어"""
    
    EMOJI_ADMIN = "👑"
    EMOJI_MONEY = "💰"
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
    
    async def is_bot_owner(self, interaction: discord.Interaction) -> bool:
        """봇 소유자인지 확인"""
        app_info = await self.bot.application_info()
        return interaction.user.id == app_info.owner.id
    
    @app_commands.command(name="코인지급", description="[관리자 전용] 유저에게 코인을 지급합니다")
    @app_commands.describe(
        유저="코인을 지급할 유저",
        금액="지급할 코인 양"
    )
    async def give_coins(
        self,
        interaction: discord.Interaction,
        유저: discord.Member,
        금액: int
    ):
        """코인 지급"""
        await interaction.response.defer()
        
        # 권한 확인
        if not await self.is_bot_owner(interaction):
            await interaction.followup.send("❌ 봇 소유자만 사용할 수 있는 명령어입니다!")
            return
        
        if 금액 <= 0:
            await interaction.followup.send("❌ 양수만 입력 가능합니다!")
            return
        
        try:
            async with self.db_manager.session() as session:
                # 유저 조회 또는 생성
                stmt = select(User).where(User.discord_id == str(유저.id))
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                
                if not user:
                    user = User(
                        discord_id=str(유저.id),
                        username=유저.display_name,
                        coins=1000
                    )
                    session.add(user)
                    await session.flush()
                
                before_coins = user.coins
                user.coins += 금액
                after_coins = user.coins
                
                await session.commit()
                
                embed = discord.Embed(
                    title=f"{self.EMOJI_ADMIN} 코인 지급",
                    description=f"{유저.mention}님에게 코인을 지급했습니다!",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="지급 금액",
                    value=f"{self.EMOJI_MONEY} **+{금액:,}** 코인",
                    inline=True
                )
                
                embed.add_field(
                    name="지급 전",
                    value=f"{before_coins:,} 코인",
                    inline=True
                )
                
                embed.add_field(
                    name="지급 후",
                    value=f"{after_coins:,} 코인",
                    inline=True
                )
                
                await interaction.followup.send(embed=embed)
                
        except Exception as e:
            logger.error(f"코인 지급 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 코인 지급 중 오류가 발생했습니다.")
    
    @app_commands.command(name="코인차감", description="[관리자 전용] 유저의 코인을 차감합니다")
    @app_commands.describe(
        유저="코인을 차감할 유저",
        금액="차감할 코인 양"
    )
    async def take_coins(
        self,
        interaction: discord.Interaction,
        유저: discord.Member,
        금액: int
    ):
        """코인 차감"""
        await interaction.response.defer()
        
        # 권한 확인
        if not await self.is_bot_owner(interaction):
            await interaction.followup.send("❌ 봇 소유자만 사용할 수 있는 명령어입니다!")
            return
        
        if 금액 <= 0:
            await interaction.followup.send("❌ 양수만 입력 가능합니다!")
            return
        
        try:
            async with self.db_manager.session() as session:
                # 유저 조회
                stmt = select(User).where(User.discord_id == str(유저.id))
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                
                if not user:
                    await interaction.followup.send("❌ 해당 유저의 기록이 없습니다!")
                    return
                
                before_coins = user.coins
                user.coins = max(0, user.coins - 금액)  # 음수 방지
                after_coins = user.coins
                actual_taken = before_coins - after_coins
                
                await session.commit()
                
                embed = discord.Embed(
                    title=f"{self.EMOJI_ADMIN} 코인 차감",
                    description=f"{유저.mention}님의 코인을 차감했습니다!",
                    color=discord.Color.red()
                )
                
                embed.add_field(
                    name="차감 금액",
                    value=f"💸 **-{actual_taken:,}** 코인",
                    inline=True
                )
                
                embed.add_field(
                    name="차감 전",
                    value=f"{before_coins:,} 코인",
                    inline=True
                )
                
                embed.add_field(
                    name="차감 후",
                    value=f"{after_coins:,} 코인",
                    inline=True
                )
                
                if actual_taken < 금액:
                    embed.add_field(
                        name="⚠️ 알림",
                        value=f"보유 코인이 부족하여 {actual_taken:,} 코인만 차감되었습니다.",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                
        except Exception as e:
            logger.error(f"코인 차감 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 코인 차감 중 오류가 발생했습니다.")
    
    @app_commands.command(name="코인설정", description="[관리자 전용] 유저의 코인을 특정 값으로 설정합니다")
    @app_commands.describe(
        유저="코인을 설정할 유저",
        금액="설정할 코인 양"
    )
    async def set_coins(
        self,
        interaction: discord.Interaction,
        유저: discord.Member,
        금액: int
    ):
        """코인 설정"""
        await interaction.response.defer()
        
        # 권한 확인
        if not await self.is_bot_owner(interaction):
            await interaction.followup.send("❌ 봇 소유자만 사용할 수 있는 명령어입니다!")
            return
        
        if 금액 < 0:
            await interaction.followup.send("❌ 음수는 설정할 수 없습니다!")
            return
        
        try:
            async with self.db_manager.session() as session:
                # 유저 조회 또는 생성
                stmt = select(User).where(User.discord_id == str(유저.id))
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                
                if not user:
                    user = User(
                        discord_id=str(유저.id),
                        username=유저.display_name,
                        coins=금액
                    )
                    session.add(user)
                    before_coins = 0
                else:
                    before_coins = user.coins
                    user.coins = 금액
                
                await session.commit()
                
                embed = discord.Embed(
                    title=f"{self.EMOJI_ADMIN} 코인 설정",
                    description=f"{유저.mention}님의 코인을 설정했습니다!",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="설정 전",
                    value=f"{before_coins:,} 코인",
                    inline=True
                )
                
                embed.add_field(
                    name="설정 후",
                    value=f"{금액:,} 코인",
                    inline=True
                )
                
                diff = 금액 - before_coins
                diff_text = f"+{diff:,}" if diff > 0 else f"{diff:,}"
                embed.add_field(
                    name="변동",
                    value=f"{diff_text} 코인",
                    inline=True
                )
                
                await interaction.followup.send(embed=embed)
                
        except Exception as e:
            logger.error(f"코인 설정 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 코인 설정 중 오류가 발생했습니다.")
    
    @app_commands.command(name="유저정보", description="[관리자 전용] 유저의 상세 정보를 확인합니다")
    @app_commands.describe(유저="정보를 확인할 유저")
    async def user_info(self, interaction: discord.Interaction, 유저: discord.Member):
        """유저 정보 조회"""
        await interaction.response.defer()
        
        # 권한 확인
        if not await self.is_bot_owner(interaction):
            await interaction.followup.send("❌ 봇 소유자만 사용할 수 있는 명령어입니다!")
            return
        
        try:
            async with self.db_manager.session() as session:
                stmt = select(User).where(User.discord_id == str(유저.id))
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                
                if not user:
                    await interaction.followup.send("❌ 해당 유저의 기록이 없습니다!")
                    return
                
                embed = discord.Embed(
                    title=f"{self.EMOJI_ADMIN} 유저 정보",
                    description=f"{유저.mention}님의 상세 정보",
                    color=discord.Color.purple()
                )
                
                embed.set_thumbnail(url=유저.display_avatar.url)
                
                embed.add_field(
                    name="보유 코인",
                    value=f"{self.EMOJI_MONEY} {user.coins:,} 코인",
                    inline=False
                )
                
                embed.add_field(
                    name="총 게임 수",
                    value=f"{user.games_played:,}회",
                    inline=True
                )
                
                embed.add_field(
                    name="승리",
                    value=f"🏆 {user.games_won:,}회",
                    inline=True
                )
                
                embed.add_field(
                    name="패배",
                    value=f"💔 {user.games_lost:,}회",
                    inline=True
                )
                
                if user.games_played > 0:
                    win_rate = (user.games_won / user.games_played) * 100
                    embed.add_field(
                        name="승률",
                        value=f"{win_rate:.2f}%",
                        inline=True
                    )
                
                embed.add_field(
                    name="가입일",
                    value=f"{user.created_at.strftime('%Y-%m-%d %H:%M')}",
                    inline=True
                )
                
                await interaction.followup.send(embed=embed)
                
        except Exception as e:
            logger.error(f"유저 정보 조회 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 유저 정보 조회 중 오류가 발생했습니다.")


async def setup(bot: commands.Bot):
    """Cog 설정"""
    await bot.add_cog(AdminCommands(bot))
