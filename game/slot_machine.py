"""
슬롯머신 게임 로직
"""
import random
from typing import Dict, Tuple
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import SlotPlay, User


class SlotMachine:
    """슬롯머신 클래스"""
    
    # 심볼 정의
    SYMBOLS = {
        '🍒': {'name': '체리', 'weight': 30, 'payout_3': 5, 'payout_2': 0.5},
        '🍋': {'name': '레몬', 'weight': 25, 'payout_3': 8, 'payout_2': 1},
        '🍊': {'name': '오렌지', 'weight': 20, 'payout_3': 15, 'payout_2': 1},
        '🍇': {'name': '포도', 'weight': 15, 'payout_3': 30, 'payout_2': 1},
        '🔔': {'name': '벨', 'weight': 7, 'payout_3': 50, 'payout_2': 2},
        '💎': {'name': '다이아몬드', 'weight': 2, 'payout_3': 200, 'payout_2': 5},
        '7️⃣': {'name': '세븐', 'weight': 1, 'payout_3': 777, 'payout_2': 10},
    }
    
    MIN_BET = 10
    
    def __init__(self):
        # 가중치 기반 심볼 풀 생성
        self.symbol_pool = []
        for symbol, data in self.SYMBOLS.items():
            # 가중치를 정수로 변환 (0.5 → 1, 2.5 → 5)
            count = int(data['weight'] * 2)
            self.symbol_pool.extend([symbol] * count)
    
    def spin(self) -> Tuple[str, str, str]:
        """릴 스핀 - 3개 심볼 반환"""
        reel1 = random.choice(self.symbol_pool)
        reel2 = random.choice(self.symbol_pool)
        reel3 = random.choice(self.symbol_pool)
        return reel1, reel2, reel3
    
    def check_win(self, reel1: str, reel2: str, reel3: str) -> Dict:
        """승리 여부 및 배당 확인"""
        # 3개 모두 일치
        if reel1 == reel2 == reel3:
            symbol_data = self.SYMBOLS[reel1]
            return {
                'win': True,
                'symbol': reel1,
                'name': symbol_data['name'],
                'multiplier': symbol_data['payout_3'],
                'type': 'jackpot' if reel1 == '7️⃣' else 'triple',
                'match_count': 3
            }
        
        # 2개 일치 체크
        if reel1 == reel2 or reel2 == reel3 or reel1 == reel3:
            # 어떤 심볼이 2개 일치했는지 찾기
            if reel1 == reel2:
                matched_symbol = reel1
            elif reel2 == reel3:
                matched_symbol = reel2
            else:  # reel1 == reel3
                matched_symbol = reel1
            
            symbol_data = self.SYMBOLS[matched_symbol]
            return {
                'win': True,
                'symbol': matched_symbol,
                'name': symbol_data['name'],
                'multiplier': symbol_data['payout_2'],
                'type': 'double',
                'match_count': 2
            }
        
        # 불일치
        return {
            'win': False,
            'symbol': None,
            'name': None,
            'multiplier': 0,
            'type': 'lose',
            'match_count': 0
        }


class SlotMachineManager:
    """슬롯머신 게임 관리 클래스"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.slot = SlotMachine()
    
    async def play(
        self,
        player_id: int,
        player_name: str,
        bet_amount: int
    ) -> Dict:
        """슬롯머신 플레이"""
        # 최소 배팅 확인
        if bet_amount < SlotMachine.MIN_BET:
            raise ValueError(f"최소 배팅 금액은 {SlotMachine.MIN_BET} 코인입니다.")
        
        # 유저 확인/생성
        user = await self._get_or_create_user(player_id, player_name)
        
        # 코인 확인
        if user.coins < bet_amount:
            raise ValueError(f"코인이 부족합니다. (보유: {user.coins}, 필요: {bet_amount})")
        
        # 배팅 차감
        user.coins -= bet_amount
        
        # 스핀!
        reel1, reel2, reel3 = self.slot.spin()
        
        # 결과 확인
        result = self.slot.check_win(reel1, reel2, reel3)
        
        # 지급액 계산
        payout = 0
        if result['win']:
            payout = bet_amount * result['multiplier']
            user.coins += payout
            user.games_won += 1
        else:
            user.games_lost += 1
        
        user.games_played += 1
        
        # 플레이 기록 저장
        play_record = SlotPlay(
            discord_id=str(player_id),
            username=player_name,
            bet_amount=bet_amount,
            reel1=reel1,
            reel2=reel2,
            reel3=reel3,
            is_win=result['win'],
            payout=payout,
            multiplier=result['multiplier']
        )
        self.session.add(play_record)
        
        await self.session.commit()
        
        return {
            'reel1': reel1,
            'reel2': reel2,
            'reel3': reel3,
            'win': result['win'],
            'symbol': result['symbol'],
            'name': result['name'],
            'multiplier': result['multiplier'],
            'type': result['type'],
            'bet': bet_amount,
            'payout': payout,
            'profit': payout - bet_amount,
            'balance': user.coins
        }
    
    async def _get_or_create_user(self, discord_id: int, username: str) -> User:
        """유저 가져오기 또는 생성"""
        stmt = select(User).where(User.discord_id == str(discord_id))
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                discord_id=str(discord_id),
                username=username,
                coins=1000
            )
            self.session.add(user)
            await self.session.flush()
        
        return user
    
    async def get_stats(self, player_id: int) -> Dict:
        """플레이어 슬롯머신 통계"""
        stmt = select(SlotPlay).where(
            SlotPlay.discord_id == str(player_id)
        )
        result = await self.session.execute(stmt)
        plays = result.scalars().all()
        
        if not plays:
            return None
        
        total_plays = len(plays)
        total_wins = sum(1 for p in plays if p.is_win)
        total_bet = sum(p.bet_amount for p in plays)
        total_payout = sum(p.payout for p in plays)
        
        # 최고 배당
        best_play = max(plays, key=lambda p: p.multiplier)
        
        return {
            'total_plays': total_plays,
            'total_wins': total_wins,
            'win_rate': (total_wins / total_plays * 100) if total_plays > 0 else 0,
            'total_bet': total_bet,
            'total_payout': total_payout,
            'net_profit': total_payout - total_bet,
            'best_multiplier': best_play.multiplier,
            'best_symbol': best_play.reel1 if best_play.is_win else None
        }