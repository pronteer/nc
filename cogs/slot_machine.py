"""
슬롯머신 게임 Cog
"""
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import logging
from database.db_manager import DatabaseManager
from game.slot_machine import SlotMachineManager

logger = logging.getLogger(__name__)


class SlotMachineCommands(commands.Cog):
    """슬롯머신 게임 명령어"""
    
    EMOJI_SLOT = "🎰"
    EMOJI_MONEY = "💰"
    EMOJI_TROPHY = "🏆"
    EMOJI_FIRE = "🔥"
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
    
    @app_commands.command(name="슬롯", description="슬롯머신을 플레이합니다")
    @app_commands.describe(배팅="배팅할 코인 (최소 10)")
    async def slot(self, interaction: discord.Interaction, 배팅: int):
        """슬롯머신 플레이"""
        await interaction.response.defer()
        
        try:
            async with self.db_manager.session() as session:
                slot_manager = SlotMachineManager(session)
                
                result = await slot_manager.play(
                    player_id=interaction.user.id,
                    player_name=interaction.user.display_name,
                    bet_amount=배팅
                )
                
                # 릴 애니메이션 효과
                embed = discord.Embed(
                    title=f"{self.EMOJI_SLOT} 슬롯머신",
                    description=f"**{interaction.user.display_name}**님의 플레이",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="배팅",
                    value=f"{배팅:,} 코인",
                    inline=True
                )
                
                embed.add_field(
                    name="스핀 중...",
                    value="🎰 🎰 🎰",
                    inline=False
                )
                
                msg = await interaction.followup.send(embed=embed)
                
                # 짧은 딜레이
                await asyncio.sleep(1)
                
                # 결과 표시
                result_embed = discord.Embed(
                    title=f"{self.EMOJI_SLOT} 슬롯머신 결과",
                    description=f"**{interaction.user.display_name}**님의 플레이",
                    color=self._get_result_color(result)
                )
                
                # 릴 결과
                reel_display = f"┃ {result['reel1']} ┃ {result['reel2']} ┃ {result['reel3']} ┃"
                result_embed.add_field(
                    name="결과",
                    value=f"```\n{reel_display}\n```",
                    inline=False
                )
                
                # 승패 결과
                if result['win']:
                    if result['type'] == 'jackpot':
                        result_text = f"{self.EMOJI_FIRE} **잭팟!!!** {self.EMOJI_FIRE}\n"
                        result_text += f"**{result['name']}** 3개 일치!"
                    elif result['type'] == 'triple':
                        result_text = f"{self.EMOJI_TROPHY} **대박!**\n"
                        result_text += f"**{result['name']}** 3개 일치!"
                    else:  # double
                        result_text = f"✨ **당첨!**\n"
                        result_text += f"**{result['name']}** 2개 일치!"
                    
                    result_embed.add_field(
                        name="🎊 당첨!",
                        value=result_text,
                        inline=False
                    )
                    
                    result_embed.add_field(
                        name="배당",
                        value=f"**{result['multiplier']}배**",
                        inline=True
                    )
                    
                    result_embed.add_field(
                        name="지급액",
                        value=f"{self.EMOJI_MONEY} **+{result['profit']:,}** 코인\n(총 {result['payout']:,})",
                        inline=True
                    )
                else:
                    result_embed.add_field(
                        name="💔 꽝",
                        value=f"아쉽게도 불일치...\n다음 기회에!",
                        inline=False
                    )
                    
                    result_embed.add_field(
                        name="손실",
                        value=f"💸 **-{배팅:,}** 코인",
                        inline=True
                    )
                
                # 잔액
                result_embed.add_field(
                    name="현재 잔액",
                    value=f"{result['balance']:,} 코인",
                    inline=True
                )
                
                await msg.edit(embed=result_embed)
                
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"슬롯머신 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 슬롯머신 플레이 중 오류가 발생했습니다.")
    
    @app_commands.command(name="슬롯통계", description="나의 슬롯머신 플레이 통계를 확인합니다")
    async def slot_stats(self, interaction: discord.Interaction):
        """슬롯머신 통계"""
        await interaction.response.defer()
        
        try:
            async with self.db_manager.session() as session:
                slot_manager = SlotMachineManager(session)
                
                stats = await slot_manager.get_stats(interaction.user.id)
                
                if not stats:
                    await interaction.followup.send("❌ 슬롯머신 플레이 기록이 없습니다!")
                    return
                
                embed = discord.Embed(
                    title=f"{self.EMOJI_SLOT} 슬롯머신 통계",
                    description=f"**{interaction.user.display_name}**님의 플레이 기록",
                    color=discord.Color.gold()
                )
                
                embed.add_field(
                    name="총 플레이",
                    value=f"{stats['total_plays']:,}회",
                    inline=True
                )
                
                embed.add_field(
                    name="승리 횟수",
                    value=f"{stats['total_wins']:,}회",
                    inline=True
                )
                
                embed.add_field(
                    name="승률",
                    value=f"{stats['win_rate']:.2f}%",
                    inline=True
                )
                
                embed.add_field(
                    name="총 배팅액",
                    value=f"{stats['total_bet']:,} 코인",
                    inline=True
                )
                
                embed.add_field(
                    name="총 지급액",
                    value=f"{stats['total_payout']:,} 코인",
                    inline=True
                )
                
                profit_emoji = "📈" if stats['net_profit'] >= 0 else "📉"
                profit_sign = "+" if stats['net_profit'] >= 0 else ""
                embed.add_field(
                    name="순이익",
                    value=f"{profit_emoji} {profit_sign}{stats['net_profit']:,} 코인",
                    inline=True
                )
                
                if stats['best_symbol']:
                    embed.add_field(
                        name="최고 기록",
                        value=f"{stats['best_symbol']} × {stats['best_multiplier']}배",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                
        except Exception as e:
            logger.error(f"슬롯통계 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 통계 조회 중 오류가 발생했습니다.")
    
    def _get_result_color(self, result: dict) -> discord.Color:
        """결과에 따른 색상"""
        if not result['win']:
            return discord.Color.red()
        elif result['type'] == 'jackpot':
            return discord.Color.gold()
        elif result['type'] == 'triple':
            return discord.Color.green()
        else:  # double
            return discord.Color.blue()


async def setup(bot: commands.Bot):
    """Cog 설정"""
    await bot.add_cog(SlotMachineCommands(bot))