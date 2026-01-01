"""
블랙잭 게임 Cog
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
from database.db_manager import DatabaseManager
from game.blackjack import BlackjackGameManager, Hand

logger = logging.getLogger(__name__)


class BlackjackCommands(commands.Cog):
    """블랙잭 게임 명령어"""
    
    EMOJI_SPADE = "♠️"
    EMOJI_HEART = "♥️"
    EMOJI_DIAMOND = "♦️"
    EMOJI_CLUB = "♣️"
    EMOJI_MONEY = "💰"
    EMOJI_CARDS = "🃏"
    EMOJI_TROPHY = "🏆"
    EMOJI_BOOM = "💥"
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
    
    @app_commands.command(name="블랙잭시작", description="블랙잭 게임을 생성합니다")
    async def create_blackjack(self, interaction: discord.Interaction):
        """블랙잭 게임 생성"""
        await interaction.response.defer()
        
        try:
            async with self.db_manager.session() as session:
                game_manager = BlackjackGameManager(session)
                
                game = await game_manager.create_game(
                    guild_id=interaction.guild_id,
                    channel_id=interaction.channel_id,
                    host_id=interaction.user.id,
                    host_name=interaction.user.display_name
                )
                
                if not game:
                    await interaction.followup.send("❌ 이미 진행 중인 게임이 있습니다!")
                    return
                
                embed = discord.Embed(
                    title=f"{self.EMOJI_CARDS} 블랙잭 게임 생성!",
                    description=(
                        f"**딜러:** {interaction.user.mention}\n"
                        f"**최소 배팅:** {BlackjackGameManager.MIN_BET} 코인\n"
                        f"**최대 인원:** {BlackjackGameManager.MAX_PLAYERS}명\n\n"
                        f"참가하려면 `/블랙잭참가` 명령어를 사용하세요!\n"
                        f"모두 참가했으면 `/딜카드` 명령어로 시작하세요!"
                    ),
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="📋 배당률",
                    value=(
                        f"블랙잭: **{BlackjackGameManager.BLACKJACK_PAYOUT}배** (1.5배)\n"
                        f"일반 승리: **{BlackjackGameManager.WIN_PAYOUT}배** (1배)\n"
                        f"무승부: 배팅 반환"
                    ),
                    inline=False
                )
                
                await interaction.followup.send(embed=embed)
                
        except Exception as e:
            logger.error(f"블랙잭 생성 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 게임 생성 중 오류가 발생했습니다.")
    
    @app_commands.command(name="블랙잭참가", description="블랙잭 게임에 참가합니다")
    @app_commands.describe(배팅="배팅할 코인 (최소 10)")
    async def join_blackjack(self, interaction: discord.Interaction, 배팅: int):
        """블랙잭 게임 참가"""
        await interaction.response.defer()
        
        try:
            async with self.db_manager.session() as session:
                game_manager = BlackjackGameManager(session)
                
                player = await game_manager.join_game(
                    channel_id=interaction.channel_id,
                    player_id=interaction.user.id,
                    player_name=interaction.user.display_name,
                    bet_amount=배팅
                )
                
                if not player:
                    await interaction.followup.send("❌ 참가할 수 있는 게임이 없습니다!")
                    return
                
                game = await game_manager.get_current_game(interaction.channel_id)
                all_players = await game_manager.get_players(game.id)
                
                embed = discord.Embed(
                    title=f"{self.EMOJI_CARDS} 게임 참가 완료!",
                    description=f"{interaction.user.mention}님이 **{배팅:,}** 코인으로 참가했습니다!",
                    color=discord.Color.blue()
                )
                
                players_text = "\n".join([
                    f"{self._get_number_emoji(p.join_order)} **{p.username}** - {p.bet_amount:,} 코인"
                    for p in all_players
                ])
                
                embed.add_field(
                    name=f"📋 참가자 ({len(all_players)}/{BlackjackGameManager.MAX_PLAYERS}명)",
                    value=players_text,
                    inline=False
                )
                
                if len(all_players) >= 1:
                    embed.add_field(
                        name="✅ 게임 시작 가능",
                        value="딜러가 `/딜카드` 명령어로 게임을 시작할 수 있습니다!",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"블랙잭 참가 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 게임 참가 중 오류가 발생했습니다.")
    
    @app_commands.command(name="딜카드", description="카드를 배분하고 게임을 시작합니다 (호스트 전용)")
    async def deal_cards(self, interaction: discord.Interaction):
        """카드 배분"""
        await interaction.response.defer()
        
        try:
            async with self.db_manager.session() as session:
                game_manager = BlackjackGameManager(session)
                
                result = await game_manager.start_game(
                    channel_id=interaction.channel_id,
                    starter_id=interaction.user.id
                )
                
                if not result:
                    await interaction.followup.send("❌ 시작할 수 있는 게임이 없습니다!")
                    return
                
                game = result['game']
                players = result['players']
                dealer_hand = result['dealer_hand']
                
                embed = discord.Embed(
                    title=f"{self.EMOJI_CARDS} 블랙잭 게임 시작!",
                    description="카드가 배분되었습니다!",
                    color=discord.Color.gold()
                )
                
                # 딜러 카드 (1장만 공개)
                dealer_cards_str = f"{dealer_hand.cards[0]} 🎴"
                embed.add_field(
                    name="🎩 딜러",
                    value=dealer_cards_str,
                    inline=False
                )
                
                # 플레이어들 카드
                for player in players:
                    hand = Hand.from_json(player.cards)
                    hand_str = str(hand)
                    value = hand.value()
                    status = ""
                    
                    if hand.is_blackjack():
                        status = " 🎊 **블랙잭!**"
                    
                    embed.add_field(
                        name=f"👤 {player.username}",
                        value=f"{hand_str} (합: {value}){status}",
                        inline=True
                    )
                
                # 첫 번째 플레이어 턴
                first_player = players[0]
                if first_player.status != 'blackjack':
                    first_member = interaction.guild.get_member(int(first_player.discord_id))
                    first_mention = first_member.mention if first_member else f"**{first_player.username}**"
                    
                    embed.add_field(
                        name="🎯 첫 번째 차례",
                        value=f"{first_mention}님의 차례입니다!",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
                
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"카드 배분 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 카드 배분 중 오류가 발생했습니다.")
    
    def _get_number_emoji(self, number: int) -> str:
        """숫자 이모지"""
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        return emojis[number - 1] if 1 <= number <= 10 else str(number)
    
    @app_commands.command(name="히트", description="카드를 한 장 더 받습니다")
    async def hit(self, interaction: discord.Interaction):
        """히트"""
        await interaction.response.defer()
        
        try:
            async with self.db_manager.session() as session:
                game_manager = BlackjackGameManager(session)
                
                result = await game_manager.hit(
                    channel_id=interaction.channel_id,
                    player_id=interaction.user.id
                )
                
                card = result['card']
                hand = result['hand']
                bust = result['bust']
                hand_number = result.get('hand_number', 1)
                auto_switch = result.get('auto_switch', False)
                
                hand_text = f"핸드 {hand_number}" if result['player'].is_split else "핸드"
                
                embed = discord.Embed(
                    title=f"{self.EMOJI_CARDS} 히트!",
                    description=f"**{interaction.user.display_name}**님이 카드를 받았습니다",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name=f"받은 카드 ({hand_text})",
                    value=str(card),
                    inline=True
                )
                
                embed.add_field(
                    name="현재 핸드",
                    value=f"{hand} (합: {hand.value()})",
                    inline=True
                )
                
                if bust:
                    embed.add_field(
                        name=f"{self.EMOJI_BOOM} 버스트!",
                        value=f"{hand_text}가 21을 초과했습니다! (합: {hand.value()})",
                        inline=False
                    )
                    embed.color = discord.Color.red()
                    
                    if auto_switch:
                        embed.add_field(
                            name="➡️ 핸드 전환",
                            value="두 번째 핸드로 자동 전환됩니다!",
                            inline=False
                        )
                    else:
                        # 다음 플레이어
                        game = await game_manager.get_current_game(interaction.channel_id)
                        if game.status == 'playing':
                            next_player = await game_manager.get_current_turn_player(game.id)
                            if next_player:
                                next_member = interaction.guild.get_member(int(next_player.discord_id))
                                next_mention = next_member.mention if next_member else f"**{next_player.username}**"
                                embed.add_field(
                                    name="🎯 다음 차례",
                                    value=f"{next_mention}님의 차례입니다!",
                                    inline=False
                                )
                        elif game.status == 'dealer_turn':
                            embed.add_field(
                                name="🎩 딜러 턴",
                                value="모든 플레이어가 종료했습니다. 딜러가 카드를 공개합니다...",
                                inline=False
                            )
                            # 딜러 자동 진행
                            await self._play_dealer_and_show_results(interaction, game_manager, game.id)
                            return
                
                await interaction.followup.send(embed=embed)
                
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"히트 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 오류가 발생했습니다.")
    
    @app_commands.command(name="스탠드", description="더 이상 카드를 받지 않습니다")
    async def stand(self, interaction: discord.Interaction):
        """스탠드"""
        await interaction.response.defer()
        
        try:
            async with self.db_manager.session() as session:
                game_manager = BlackjackGameManager(session)
                
                result = await game_manager.stand(
                    channel_id=interaction.channel_id,
                    player_id=interaction.user.id
                )
                
                hand = result['hand']
                hand_number = result.get('hand_number', 1)
                switch_to_hand2 = result.get('switch_to_hand2', False)
                
                hand_text = f"핸드 {hand_number}" if result['player'].is_split else "핸드"
                
                embed = discord.Embed(
                    title=f"✋ 스탠드!",
                    description=f"**{interaction.user.display_name}**님이 {hand_text}를 스탠드했습니다",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="최종 핸드",
                    value=f"{hand} (합: {hand.value()})",
                    inline=False
                )
                
                if switch_to_hand2:
                    embed.add_field(
                        name="➡️ 핸드 전환",
                        value="이제 두 번째 핸드를 플레이하세요!",
                        inline=False
                    )
                else:
                    # 다음 플레이어 또는 딜러 턴
                    game = await game_manager.get_current_game(interaction.channel_id)
                    if game.status == 'playing':
                        next_player = await game_manager.get_current_turn_player(game.id)
                        if next_player:
                            next_member = interaction.guild.get_member(int(next_player.discord_id))
                            next_mention = next_member.mention if next_member else f"**{next_player.username}**"
                            embed.add_field(
                                name="🎯 다음 차례",
                                value=f"{next_mention}님의 차례입니다!",
                                inline=False
                            )
                    elif game.status == 'dealer_turn':
                        embed.add_field(
                            name="🎩 딜러 턴",
                            value="모든 플레이어가 종료했습니다. 딜러가 카드를 공개합니다...",
                            inline=False
                        )
                        await interaction.followup.send(embed=embed)
                        # 딜러 자동 진행
                        await self._play_dealer_and_show_results(interaction, game_manager, game.id)
                        return
                
                await interaction.followup.send(embed=embed)
                
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"스탠드 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 오류가 발생했습니다.")
    
    @app_commands.command(name="더블다운", description="배팅을 2배로 올리고 카드 1장만 더 받습니다")
    async def double_down(self, interaction: discord.Interaction):
        """더블다운"""
        await interaction.response.defer()
        
        try:
            async with self.db_manager.session() as session:
                game_manager = BlackjackGameManager(session)
                
                result = await game_manager.double_down(
                    channel_id=interaction.channel_id,
                    player_id=interaction.user.id
                )
                
                card = result['card']
                hand = result['hand']
                bust = result['bust']
                player = result['player']
                
                embed = discord.Embed(
                    title=f"{self.EMOJI_MONEY} 더블다운!",
                    description=f"**{interaction.user.display_name}**님이 배팅을 2배로 올렸습니다!",
                    color=discord.Color.purple()
                )
                
                embed.add_field(
                    name="배팅 금액",
                    value=f"{player.bet_amount:,} 코인",
                    inline=True
                )
                
                embed.add_field(
                    name="받은 카드",
                    value=str(card),
                    inline=True
                )
                
                embed.add_field(
                    name="최종 핸드",
                    value=f"{hand} (합: {hand.value()})",
                    inline=False
                )
                
                if bust:
                    embed.add_field(
                        name=f"{self.EMOJI_BOOM} 버스트!",
                        value=f"21을 초과했습니다!",
                        inline=False
                    )
                    embed.color = discord.Color.red()
                
                # 다음 플레이어 또는 딜러 턴
                game = await game_manager.get_current_game(interaction.channel_id)
                if game.status == 'playing':
                    next_player = await game_manager.get_current_turn_player(game.id)
                    if next_player:
                        next_member = interaction.guild.get_member(int(next_player.discord_id))
                        next_mention = next_member.mention if next_member else f"**{next_player.username}**"
                        embed.add_field(
                            name="🎯 다음 차례",
                            value=f"{next_mention}님의 차례입니다!",
                            inline=False
                        )
                elif game.status == 'dealer_turn':
                    embed.add_field(
                        name="🎩 딜러 턴",
                        value="모든 플레이어가 종료했습니다. 딜러가 카드를 공개합니다...",
                        inline=False
                    )
                    await interaction.followup.send(embed=embed)
                    # 딜러 자동 진행
                    await self._play_dealer_and_show_results(interaction, game_manager, game.id)
                    return
                
                await interaction.followup.send(embed=embed)
                
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"더블다운 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 오류가 발생했습니다.")
    
    async def _play_dealer_and_show_results(self, interaction: discord.Interaction, game_manager, game_id: int):
        """딜러 턴 진행 및 결과 표시"""
        try:
            # 딜러 플레이
            dealer_result = await game_manager.play_dealer(game_id)
            dealer_hand = dealer_result['dealer_hand']
            drawn_cards = dealer_result['drawn_cards']
            
            # 결과 임베드
            embed = discord.Embed(
                title=f"🎩 딜러 카드 공개!",
                description="게임이 종료되었습니다!",
                color=discord.Color.gold()
            )
            
            dealer_str = str(dealer_hand)
            if drawn_cards:
                dealer_str += f"\n(추가: {' '.join(str(c) for c in drawn_cards)})"
            
            dealer_status = ""
            if dealer_result['dealer_bust']:
                dealer_status = f" {self.EMOJI_BOOM} **버스트!**"
            elif dealer_hand.is_blackjack():
                dealer_status = " 🎊 **블랙잭!**"
            
            embed.add_field(
                name="🎩 딜러",
                value=f"{dealer_str}\n합: {dealer_hand.value()}{dealer_status}",
                inline=False
            )
            
            # 플레이어별 결과
            players = await game_manager.get_players(game_id)
            
            for player in players:
                hand = Hand.from_json(player.cards)
                result_emoji = {
                    'blackjack': '🎊',
                    'win': '🏆',
                    'lose': '💔',
                    'push': '🤝'
                }
                
                emoji = result_emoji.get(player.result, '❓')
                result_text = {
                    'blackjack': '블랙잭 승리!',
                    'win': '승리!',
                    'lose': '패배',
                    'push': '무승부'
                }
                
                status_text = f"{emoji} **{result_text.get(player.result, player.result)}**"
                
                # 스플릿 처리
                if player.is_split and player.split_cards:
                    hand2 = Hand.from_json(player.split_cards)
                    hand_display = (
                        f"핸드1: {hand} (합: {hand.value()})\n"
                        f"핸드2: {hand2} (합: {hand2.value()})"
                    )
                else:
                    hand_display = f"{hand} (합: {hand.value()})"
                
                payout_text = ""
                if player.payout > 0:
                    profit = player.payout - player.bet_amount
                    payout_text = f"\n💰 +{profit:,} 코인 (총 {player.payout:,})"
                elif player.result == 'lose':
                    payout_text = f"\n💸 -{player.bet_amount:,} 코인"
                else:
                    payout_text = "\n💰 ±0 코인"
                
                # 인슈어런스 표시
                insurance_text = ""
                if player.has_insurance:
                    if dealer_hand.is_blackjack():
                        insurance_payout = player.insurance_amount * 2
                        insurance_text = f"\n🛡️ 보험금: +{insurance_payout:,} 코인"
                    else:
                        insurance_text = f"\n🛡️ 보험금: -{player.insurance_amount:,} 코인"
                
                embed.add_field(
                    name=f"👤 {player.username}",
                    value=f"{hand_display}\n{status_text}{payout_text}{insurance_text}",
                    inline=True
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"딜러 턴 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 딜러 턴 진행 중 오류가 발생했습니다.")
    
    @app_commands.command(name="인슈어런스", description="딜러의 오픈 카드가 A일 때 보험을 구매합니다")
    async def insurance(self, interaction: discord.Interaction):
        """인슈어런스"""
        await interaction.response.defer()
        
        try:
            async with self.db_manager.session() as session:
                game_manager = BlackjackGameManager(session)
                
                result = await game_manager.insurance(
                    channel_id=interaction.channel_id,
                    player_id=interaction.user.id
                )
                
                insurance_cost = result['insurance_cost']
                dealer_blackjack = result['dealer_blackjack']
                
                embed = discord.Embed(
                    title=f"🛡️ 인슈어런스!",
                    description=f"**{interaction.user.display_name}**님이 보험을 구매했습니다",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="보험료",
                    value=f"{insurance_cost:,} 코인",
                    inline=True
                )
                
                embed.add_field(
                    name="보험 내용",
                    value="딜러가 블랙잭이면 2배 지급",
                    inline=True
                )
                
                if dealer_blackjack:
                    payout = insurance_cost * 2
                    embed.add_field(
                        name="🎊 딜러 블랙잭!",
                        value=f"보험금 {payout:,} 코인 지급!",
                        inline=False
                    )
                    embed.color = discord.Color.green()
                
                await interaction.followup.send(embed=embed)
                
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"인슈어런스 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 오류가 발생했습니다.")
    
    @app_commands.command(name="스플릿", description="같은 숫자 2장을 분리해서 2개의 핸드로 플레이합니다")
    async def split(self, interaction: discord.Interaction):
        """스플릿"""
        await interaction.response.defer()
        
        try:
            async with self.db_manager.session() as session:
                game_manager = BlackjackGameManager(session)
                
                result = await game_manager.split(
                    channel_id=interaction.channel_id,
                    player_id=interaction.user.id
                )
                
                hand1 = result['hand1']
                hand2 = result['hand2']
                player = result['player']
                
                embed = discord.Embed(
                    title=f"✂️ 스플릿!",
                    description=f"**{interaction.user.display_name}**님이 핸드를 분리했습니다",
                    color=discord.Color.purple()
                )
                
                embed.add_field(
                    name="💰 추가 배팅",
                    value=f"{player.bet_amount // 2:,} 코인",
                    inline=True
                )
                
                embed.add_field(
                    name="📋 총 배팅",
                    value=f"{player.bet_amount:,} 코인",
                    inline=True
                )
                
                embed.add_field(
                    name="🃏 첫 번째 핸드",
                    value=f"{hand1} (합: {hand1.value()})",
                    inline=False
                )
                
                embed.add_field(
                    name="🃏 두 번째 핸드",
                    value=f"{hand2} (합: {hand2.value()})",
                    inline=False
                )
                
                embed.add_field(
                    name="ℹ️ 안내",
                    value="첫 번째 핸드부터 플레이하세요!\n완료되면 자동으로 두 번째 핸드로 전환됩니다.",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed)
                
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"스플릿 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 오류가 발생했습니다.")


async def setup(bot: commands.Bot):
    """Cog 설정"""
    await bot.add_cog(BlackjackCommands(bot))