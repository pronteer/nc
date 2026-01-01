"""
러시안 룰렛 게임 Cog
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
from datetime import timedelta
from database.db_manager import DatabaseManager
from game.russian_roulette import RussianRouletteGame

logger = logging.getLogger(__name__)


class RouletteCommands(commands.Cog):
    """러시안 룰렛 게임 명령어"""
    
    EMOJI_GUN = "🔫"
    EMOJI_SKULL = "💀"
    EMOJI_MONEY = "💰"
    EMOJI_TROPHY = "🏆"
    EMOJI_DICE = "🎲"
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
    
    @app_commands.command(name="룰렛생성", description="러시안 룰렛 게임을 생성합니다")
    @app_commands.describe(
        최대인원="최대 플레이어 수 (기본: 6명)"
    )
    async def create_roulette(
        self, 
        interaction: discord.Interaction,
        최대인원: Optional[int] = 6
    ):
        """러시안 룰렛 게임 생성"""
        await interaction.response.defer()
        
        try:
            # 입력값 검증
            if 최대인원 < 2 or 최대인원 > 10:
                await interaction.followup.send("❌ 최대 인원은 2~10명 사이여야 합니다.")
                return
            
            async with self.db_manager.session() as session:
                game_manager = RussianRouletteGame(session)
                
                game = await game_manager.create_game(
                    guild_id=interaction.guild_id,
                    channel_id=interaction.channel_id,
                    host_id=interaction.user.id,
                    host_name=interaction.user.display_name,
                    max_players=최대인원
                )
                
                if not game:
                    await interaction.followup.send("❌ 이미 진행 중인 게임이 있습니다!")
                    return
                
                # 게임 생성 임베드
                embed = discord.Embed(
                    title=f"{self.EMOJI_GUN} 러시안 룰렛 게임 생성!",
                    description=(
                        f"**호스트:** {interaction.user.mention}\n"
                        f"**최대 인원:** {최대인원}명\n"
                        f"**승리 보상:** {RussianRouletteGame.WIN_REWARD} 코인 {self.EMOJI_MONEY}\n\n"
                        f"참가하려면 `/룰렛참가` 명령어를 사용하세요!\n"
                        f"게임을 시작하려면 `/룰렛시작` 명령어를 사용하세요!"
                    ),
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="📋 참가자 (1명)",
                    value=f"1️⃣ {interaction.user.mention}",
                    inline=False
                )
                embed.set_footer(text="⚠️ 게임 ID: " + str(game.id))
                
                await interaction.followup.send(embed=embed)
                
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"게임 생성 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 게임 생성 중 오류가 발생했습니다.")
    
    @app_commands.command(name="룰렛참가", description="러시안 룰렛 게임에 참가합니다")
    async def join_roulette(self, interaction: discord.Interaction):
        """러시안 룰렛 게임 참가"""
        await interaction.response.defer()
        
        try:
            async with self.db_manager.session() as session:
                game_manager = RussianRouletteGame(session)
                
                # 현재 게임 확인
                game = await game_manager.get_current_game(interaction.channel_id)
                if not game:
                    await interaction.followup.send("❌ 참가할 수 있는 게임이 없습니다!")
                    return
                
                if game.status != 'waiting':
                    await interaction.followup.send("❌ 이미 시작된 게임에는 참가할 수 없습니다!")
                    return
                
                # 게임 참가
                player = await game_manager.join_game(
                    channel_id=interaction.channel_id,
                    player_id=interaction.user.id,
                    player_name=interaction.user.display_name
                )
                
                # 참가자 목록
                all_players = await game_manager.get_players(game.id)
                
                # 참가 성공 임베드
                embed = discord.Embed(
                    title=f"{self.EMOJI_DICE} 게임 참가 완료!",
                    description=f"{interaction.user.mention}님이 게임에 참가했습니다!",
                    color=discord.Color.blue()
                )
                
                # 참가자 목록 표시
                players_text = "\n".join([
                    f"{self._get_number_emoji(p.join_order)} {self._get_user_mention(p.discord_id, p.username)}"
                    for p in all_players
                ])
                
                embed.add_field(
                    name=f"📋 참가자 ({len(all_players)}/{game.max_players}명)",
                    value=players_text,
                    inline=False
                )
                
                if len(all_players) >= 2:
                    embed.add_field(
                        name="✅ 게임 시작 가능",
                        value=f"호스트가 `/룰렛시작` 명령어로 게임을 시작할 수 있습니다!",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"게임 참가 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 게임 참가 중 오류가 발생했습니다.")
    
    @app_commands.command(name="룰렛시작", description="러시안 룰렛 게임을 시작합니다 (호스트 전용)")
    async def start_roulette(self, interaction: discord.Interaction):
        """러시안 룰렛 게임 시작"""
        await interaction.response.defer()
        
        try:
            async with self.db_manager.session() as session:
                game_manager = RussianRouletteGame(session)
                
                game = await game_manager.start_game(
                    channel_id=interaction.channel_id,
                    starter_id=interaction.user.id
                )
                
                if not game:
                    await interaction.followup.send("❌ 시작할 수 있는 게임이 없습니다!")
                    return
                
                # 참가자 목록
                players = await game_manager.get_players(game.id)
                
                # 게임 시작 임베드
                embed = discord.Embed(
                    title=f"{self.EMOJI_GUN} 러시안 룰렛 게임 시작!",
                    description=(
                        f"**승리 보상:** {RussianRouletteGame.WIN_REWARD} 코인 {self.EMOJI_MONEY}\n"
                        f"**플레이어:** {len(players)}명\n\n"
                        f"**{self.EMOJI_SKULL} 규칙:**\n"
                        f"• 각자 차례대로 `/당겨` 명령어를 사용하세요\n"
                        f"• 총알은 항상 1/6 확률로 발사됩니다\n"
                        f"• 총알에 맞으면 패배하고 1분간 채팅 금지됩니다\n"
                        f"• 나머지 생존자들이 승리하고 각각 {RussianRouletteGame.WIN_REWARD} 코인을 받습니다!"
                    ),
                    color=discord.Color.red()
                )
                
                # 플레이어 순서
                players_text = "\n".join([
                    f"{self._get_number_emoji(p.join_order)} {self._get_user_mention(p.discord_id, p.username)}"
                    for p in players
                ])
                
                embed.add_field(
                    name="👥 플레이어 순서",
                    value=players_text,
                    inline=False
                )
                
                embed.add_field(
                    name="🎯 첫 번째 차례",
                    value=f"{players[0].username}님, `/당겨` 명령어를 사용하세요!",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed)
                
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"게임 시작 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 게임 시작 중 오류가 발생했습니다.")
    
    @app_commands.command(name="당겨", description="방아쇠를 당깁니다")
    async def pull_trigger(self, interaction: discord.Interaction):
        """방아쇠 당기기"""
        await interaction.response.defer()
        
        try:
            async with self.db_manager.session() as session:
                game_manager = RussianRouletteGame(session)
                
                result = await game_manager.shoot(
                    channel_id=interaction.channel_id,
                    shooter_id=interaction.user.id
                )
                
                if result['hit']:
                    # 총알 맞음 - 게임 즉시 종료!
                    embed = discord.Embed(
                        title=f"{self.EMOJI_SKULL} 빵! 총알이 발사되었습니다!",
                        description=f"{interaction.user.mention}님이 총알에 맞았습니다...",
                        color=discord.Color.dark_red()
                    )
                    
                    # 타임아웃 적용
                    try:
                        await interaction.user.timeout(
                            timedelta(seconds=60),
                            reason="러시안 룰렛 패배"
                        )
                        embed.add_field(
                            name="⏱️ 타임아웃 1분",
                            value="조빱은 채팅을 칠 수 없습니다 ㅋ",
                            inline=False
                        )
                    except discord.Forbidden:
                        embed.add_field(
                            name="⚠️ 권한 없음",
                            value="타임아웃을 적용할 권한이 없습니다.",
                            inline=False
                        )
                    
                    # 게임 종료 - 승자들 표시
                    if result['game_over']:
                        winners_text = "\n".join([
                            f"{self._get_number_emoji(w.join_order)} {self._get_user_mention(w.discord_id, w.username)}"
                            for w in result['winners']
                        ])
                        
                        embed.add_field(
                            name=f"{self.EMOJI_TROPHY} 게임 종료!",
                            value=(
                                f"**승자들:** ({len(result['winners'])}명)\n"
                                f"{winners_text}\n\n"
                                f"**각자 보상:** {result['reward']} 코인 {self.EMOJI_MONEY}"
                            ),
                            inline=False
                        )
                        embed.color = discord.Color.gold()
                    
                    await interaction.followup.send(embed=embed)
                    
                else:
                    # 빈 탄창 - 다음 차례로
                    next_player = result.get('next_player')
                    
                    if next_player:
                        # 다음 차례 플레이어 멘션
                        next_user = self.bot.get_user(int(next_player.discord_id))
                        next_mention = next_user.mention if next_user else f"**{next_player.username}**"
                        
                        embed = discord.Embed(
                            title=f"{self.EMOJI_GUN} 찰칵... 빈 탄창!",
                            description=f"**{interaction.user.display_name}**님이 살아남았습니다!",
                            color=discord.Color.green()
                        )
                        
                        embed.add_field(
                            name="🎯 다음 차례",
                            value=f"{next_mention}님, `/당겨` 명령어를 사용하세요!",
                            inline=False
                        )
                    else:
                        embed = discord.Embed(
                            title=f"{self.EMOJI_GUN} 찰칵... 빈 탄창!",
                            description=f"**{interaction.user.display_name}**님이 살아남았습니다!",
                            color=discord.Color.green()
                        )
                    
                    # 현재 게임 정보
                    game = await game_manager.get_current_game(interaction.channel_id)
                    alive_players = await game_manager.get_alive_players(game.id)
                    
                    embed.add_field(
                        name="📊 현재 상황",
                        value=f"생존자: {len(alive_players)}명",
                        inline=False
                    )
                    
                    await interaction.followup.send(embed=embed)
                
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"방아쇠 당기기 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 오류가 발생했습니다.")
    
    @app_commands.command(name="룰렛취소", description="대기 중인 게임을 취소합니다 (호스트 전용)")
    async def cancel_roulette(self, interaction: discord.Interaction):
        """게임 취소"""
        await interaction.response.defer()
        
        try:
            async with self.db_manager.session() as session:
                game_manager = RussianRouletteGame(session)
                
                success = await game_manager.cancel_game(
                    channel_id=interaction.channel_id,
                    canceller_id=interaction.user.id
                )
                
                if success:
                    await interaction.followup.send(
                        f"게임이 취소되었습니다."
                    )
                else:
                    await interaction.followup.send("❌ 취소할 수 있는 게임이 없습니다!")
                    
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"게임 취소 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 게임 취소 중 오류가 발생했습니다.")
    
    @app_commands.command(name="룰렛정보", description="현재 게임 정보를 확인합니다")
    async def roulette_info(self, interaction: discord.Interaction):
        """게임 정보 확인"""
        await interaction.response.defer()
        
        try:
            async with self.db_manager.session() as session:
                game_manager = RussianRouletteGame(session)
                
                game = await game_manager.get_current_game(interaction.channel_id)
                
                if not game:
                    await interaction.followup.send("❌ 진행 중인 게임이 없습니다!")
                    return
                
                players = await game_manager.get_players(game.id)
                alive_players = await game_manager.get_alive_players(game.id)
                
                # 게임 정보 임베드
                embed = discord.Embed(
                    title=f"{self.EMOJI_GUN} 러시안 룰렛 게임 정보",
                    color=discord.Color.blue()
                )
                
                # 상태
                status_text = {
                    'waiting': '⏸️ 대기 중',
                    'playing': '▶️ 진행 중',
                    'finished': '✅ 종료됨'
                }
                
                embed.add_field(
                    name="📊 게임 상태",
                    value=status_text.get(game.status, game.status),
                    inline=True
                )
                
                embed.add_field(
                    name=f"{self.EMOJI_MONEY} 승리 보상",
                    value=f"{RussianRouletteGame.WIN_REWARD} 코인",
                    inline=True
                )
                
                embed.add_field(
                    name="👥 플레이어",
                    value=f"{len(players)}명",
                    inline=True
                )
                
                # 전체 플레이어 목록
                if game.status == 'waiting':
                    players_text = "\n".join([
                        f"{self._get_number_emoji(p.join_order)} {self._get_user_mention(p.discord_id, p.username)}"
                        for p in players
                    ])
                    embed.add_field(
                        name=f"📋 참가자 ({len(players)}/{game.max_players})",
                        value=players_text,
                        inline=False
                    )
                else:
                    # 진행 중 - 현재 턴 플레이어 표시
                    current_turn_player = await game_manager.get_current_turn_player(game.id)
                    
                    if current_turn_player:
                        embed.add_field(
                            name="🎯 현재 차례",
                            value=f"{self._get_user_mention(current_turn_player.discord_id, current_turn_player.username)}",
                            inline=False
                        )
                    
                    # 생존자와 탈락자 구분
                    alive_text = "\n".join([
                        f"{self._get_number_emoji(p.join_order)} {self._get_user_mention(p.discord_id, p.username)}"
                        for p in alive_players
                    ])
                    
                    dead_players = [p for p in players if not p.is_alive]
                    dead_text = "\n".join([
                        f"~~{self._get_number_emoji(p.join_order)} {self._get_user_mention(p.discord_id, p.username)}~~"
                        for p in dead_players
                    ]) if dead_players else "없음"
                    
                    embed.add_field(
                        name=f"✅ 생존자 ({len(alive_players)}명)",
                        value=alive_text,
                        inline=True
                    )
                    
                    embed.add_field(
                        name=f"{self.EMOJI_SKULL} 탈락자 ({len(dead_players)}명)",
                        value=dead_text,
                        inline=True
                    )
                
                embed.set_footer(text=f"게임 ID: {game.id}")
                
                await interaction.followup.send(embed=embed)
                
        except Exception as e:
            logger.error(f"게임 정보 조회 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 게임 정보 조회 중 오류가 발생했습니다.")
    
    @app_commands.command(name="내코인", description="보유 코인을 확인합니다")
    async def my_coins(self, interaction: discord.Interaction):
        """보유 코인 확인"""
        await interaction.response.defer()
        
        try:
            async with self.db_manager.session() as session:
                from sqlalchemy import select
                from database.models import User
                
                stmt = select(User).where(User.discord_id == str(interaction.user.id))
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                
                if not user:
                    await interaction.followup.send(
                        f"{self.EMOJI_MONEY} 아직 게임에 참여한 적이 없습니다. 기본 1,000 코인을 받으려면 게임에 참가하세요!"
                    )
                    return
                
                embed = discord.Embed(
                    title=f"{self.EMOJI_MONEY} 내 코인 정보",
                    color=discord.Color.gold()
                )
                
                embed.add_field(
                    name="보유 코인",
                    value=f"**{user.coins:,}** 코인",
                    inline=False
                )
                
                embed.add_field(
                    name="📊 게임 통계",
                    value=(
                        f"총 게임: {user.games_played}회\n"
                        f"승리: {user.games_won}회\n"
                        f"패배: {user.games_lost}회\n"
                        f"승률: {(user.games_won / user.games_played * 100) if user.games_played > 0 else 0:.1f}%"
                    ),
                    inline=False
                )
                
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                
                await interaction.followup.send(embed=embed)
                
        except Exception as e:
            logger.error(f"코인 조회 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 코인 조회 중 오류가 발생했습니다.")
    
    def _get_number_emoji(self, number: int) -> str:
        """숫자를 이모지로 변환"""
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        return emojis[number - 1] if 1 <= number <= 10 else str(number)
    
    def _get_user_mention(self, discord_id: str, username: str) -> str:
        """유저 멘션 또는 이름 반환 (안전)"""
        user = self.bot.get_user(int(discord_id))
        return user.mention if user else f"**{username}**"


async def setup(bot: commands.Bot):
    """Cog 설정"""
    await bot.add_cog(RouletteCommands(bot))