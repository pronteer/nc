"""
블랙잭 게임 로직
"""
import random
import json
from typing import Optional, List, Dict, Tuple
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import BlackjackGame, BlackjackPlayer, User


class Card:
    """카드 클래스"""
    SUITS = ['♠️', '♥️', '♦️', '♣️']
    RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    
    def __init__(self, suit: str, rank: str):
        self.suit = suit
        self.rank = rank
    
    def __str__(self):
        return f"{self.rank}{self.suit}"
    
    def __repr__(self):
        return str(self)
    
    def to_dict(self):
        return {'suit': self.suit, 'rank': self.rank}
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(data['suit'], data['rank'])
    
    def value(self, current_total: int = 0) -> int:
        """카드 값 계산 (A는 1 또는 11)"""
        if self.rank in ['J', 'Q', 'K']:
            return 10
        elif self.rank == 'A':
            # A는 11로 계산했을 때 21 넘으면 1로
            return 11 if current_total + 11 <= 21 else 1
        else:
            return int(self.rank)


class Deck:
    """덱 클래스"""
    
    def __init__(self):
        self.cards = []
        self.reset()
    
    def reset(self):
        """새 덱 생성 및 셔플"""
        self.cards = [
            Card(suit, rank) 
            for suit in Card.SUITS 
            for rank in Card.RANKS
        ]
        random.shuffle(self.cards)
    
    def draw(self) -> Card:
        """카드 한 장 뽑기"""
        if not self.cards:
            self.reset()
        return self.cards.pop()
    
    def to_json(self) -> str:
        """JSON으로 변환"""
        return json.dumps([card.to_dict() for card in self.cards])
    
    @classmethod
    def from_json(cls, json_str: str):
        """JSON에서 로드"""
        deck = cls()
        if json_str:
            deck.cards = [Card.from_dict(d) for d in json.loads(json_str)]
        else:
            deck.reset()
        return deck


class Hand:
    """핸드 클래스"""
    
    def __init__(self, cards: List[Card] = None):
        self.cards = cards or []
    
    def add_card(self, card: Card):
        """카드 추가"""
        self.cards.append(card)
    
    def value(self) -> int:
        """핸드 총 값 계산"""
        total = 0
        aces = 0
        
        for card in self.cards:
            if card.rank == 'A':
                aces += 1
                total += 11
            elif card.rank in ['J', 'Q', 'K']:
                total += 10
            else:
                total += int(card.rank)
        
        # A를 11에서 1로 변경
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        
        return total
    
    def is_blackjack(self) -> bool:
        """블랙잭 여부 (처음 2장으로 21)"""
        return len(self.cards) == 2 and self.value() == 21
    
    def is_bust(self) -> bool:
        """버스트 여부 (21 초과)"""
        return self.value() > 21
    
    def is_soft(self) -> bool:
        """소프트 핸드 여부 (A를 11로 계산 중)"""
        total = sum(10 if c.rank in ['J','Q','K'] else int(c.rank) if c.rank != 'A' else 0 for c in self.cards)
        aces = sum(1 for c in self.cards if c.rank == 'A')
        return aces > 0 and total + 11 <= 21
    
    def can_split(self) -> bool:
        """스플릿 가능 여부"""
        if len(self.cards) != 2:
            return False
        # 같은 숫자거나 둘 다 10점 카드
        if self.cards[0].rank == self.cards[1].rank:
            return True
        val1 = 10 if self.cards[0].rank in ['J','Q','K','10'] else 0
        val2 = 10 if self.cards[1].rank in ['J','Q','K','10'] else 0
        return val1 == val2 == 10
    
    def to_json(self) -> str:
        """JSON으로 변환"""
        return json.dumps([card.to_dict() for card in self.cards])
    
    @classmethod
    def from_json(cls, json_str: str):
        """JSON에서 로드"""
        if not json_str:
            return cls()
        cards = [Card.from_dict(d) for d in json.loads(json_str)]
        return cls(cards)
    
    def __str__(self):
        return ' '.join(str(card) for card in self.cards)


class BlackjackGameManager:
    """블랙잭 게임 관리 클래스"""
    
    MIN_BET = 10
    MAX_PLAYERS = 6
    BLACKJACK_PAYOUT = 1.5
    WIN_PAYOUT = 1.0
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_game(
        self,
        guild_id: int,
        channel_id: int,
        host_id: int,
        host_name: str
    ) -> Optional[BlackjackGame]:
        """새 게임 생성"""
        # 진행 중인 게임 확인
        stmt = select(BlackjackGame).where(
            and_(
                BlackjackGame.channel_id == str(channel_id),
                BlackjackGame.status.in_(['waiting', 'playing', 'dealer_turn'])
            )
        )
        result = await self.session.execute(stmt)
        existing_game = result.scalar_one_or_none()
        
        if existing_game:
            return None
        
        # 호스트 유저 확인/생성
        await self._get_or_create_user(host_id, host_name)
        
        # 새 덱 생성
        deck = Deck()
        
        # 게임 생성
        game = BlackjackGame(
            guild_id=str(guild_id),
            channel_id=str(channel_id),
            host_id=str(host_id),
            deck=deck.to_json(),
            status='waiting'
        )
        self.session.add(game)
        await self.session.commit()
        
        return game
    
    async def join_game(
        self,
        channel_id: int,
        player_id: int,
        player_name: str,
        bet_amount: int
    ) -> Optional[BlackjackPlayer]:
        """게임 참가"""
        # 대기 중인 게임 찾기
        stmt = select(BlackjackGame).where(
            and_(
                BlackjackGame.channel_id == str(channel_id),
                BlackjackGame.status == 'waiting'
            )
        )
        result = await self.session.execute(stmt)
        game = result.scalar_one_or_none()
        
        if not game:
            return None
        
        # 최소 배팅 확인
        if bet_amount < self.MIN_BET:
            raise ValueError(f"최소 배팅 금액은 {self.MIN_BET} 코인입니다.")
        
        # 이미 참가했는지 확인
        stmt = select(BlackjackPlayer).where(
            and_(
                BlackjackPlayer.game_id == game.id,
                BlackjackPlayer.discord_id == str(player_id)
            )
        )
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError("이미 게임에 참가했습니다.")
        
        # 인원 확인
        stmt = select(BlackjackPlayer).where(BlackjackPlayer.game_id == game.id)
        result = await self.session.execute(stmt)
        current_players = result.scalars().all()
        
        if len(current_players) >= self.MAX_PLAYERS:
            raise ValueError(f"게임이 가득 찼습니다. (최대 {self.MAX_PLAYERS}명)")
        
        # 유저 확인/생성
        await self._get_or_create_user(player_id, player_name)
        
        # 코인 확인
        user = await self._get_user(player_id)
        if user.coins < bet_amount:
            raise ValueError(f"코인이 부족합니다. (보유: {user.coins}, 필요: {bet_amount})")
        
        # 참가
        player = BlackjackPlayer(
            game_id=game.id,
            discord_id=str(player_id),
            username=player_name,
            join_order=len(current_players) + 1,
            bet_amount=bet_amount
        )
        self.session.add(player)
        
        # 코인 차감
        user.coins -= bet_amount
        
        await self.session.commit()
        
        return player
    
    async def start_game(self, channel_id: int, starter_id: int) -> Optional[Dict]:
        """게임 시작 - 카드 배분"""
        # 대기 중인 게임 찾기
        stmt = select(BlackjackGame).where(
            and_(
                BlackjackGame.channel_id == str(channel_id),
                BlackjackGame.status == 'waiting'
            )
        )
        result = await self.session.execute(stmt)
        game = result.scalar_one_or_none()
        
        if not game:
            return None
        
        # 호스트 확인
        if str(starter_id) != game.host_id:
            raise ValueError("게임 호스트만 시작할 수 있습니다.")
        
        # 플레이어 확인
        stmt = select(BlackjackPlayer).where(
            BlackjackPlayer.game_id == game.id
        ).order_by(BlackjackPlayer.join_order)
        result = await self.session.execute(stmt)
        players = result.scalars().all()
        
        if len(players) < 1:
            raise ValueError("최소 1명 이상의 플레이어가 필요합니다.")
        
        # 덱 로드
        deck = Deck.from_json(game.deck)
        
        # 각 플레이어에게 카드 2장씩 배분
        for player in players:
            hand = Hand()
            hand.add_card(deck.draw())
            hand.add_card(deck.draw())
            player.cards = hand.to_json()
            
            # 블랙잭 체크
            if hand.is_blackjack():
                player.status = 'blackjack'
        
        # 딜러 카드 2장
        dealer_hand = Hand()
        dealer_hand.add_card(deck.draw())
        dealer_hand.add_card(deck.draw())
        game.dealer_cards = dealer_hand.to_json()
        
        # 게임 상태 업데이트
        game.deck = deck.to_json()
        game.status = 'playing'
        game.started_at = datetime.utcnow()
        
        await self.session.commit()
        
        return {
            'game': game,
            'players': players,
            'dealer_hand': dealer_hand
        }
    
    # 헬퍼 메서드들
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
    
    async def _get_user(self, discord_id: int) -> User:
        """유저 가져오기"""
        stmt = select(User).where(User.discord_id == str(discord_id))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_current_game(self, channel_id: int) -> Optional[BlackjackGame]:
        """현재 게임 가져오기"""
        stmt = select(BlackjackGame).where(
            and_(
                BlackjackGame.channel_id == str(channel_id),
                BlackjackGame.status.in_(['waiting', 'playing', 'dealer_turn'])
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_players(self, game_id: int) -> List[BlackjackPlayer]:
        """게임 플레이어 목록"""
        stmt = select(BlackjackPlayer).where(
            BlackjackPlayer.game_id == game_id
        ).order_by(BlackjackPlayer.join_order)
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_current_turn_player(self, game_id: int) -> Optional[BlackjackPlayer]:
        """현재 턴 플레이어"""
        stmt = select(BlackjackGame).where(BlackjackGame.id == game_id)
        result = await self.session.execute(stmt)
        game = result.scalar_one_or_none()
        
        if not game:
            return None
        
        stmt = select(BlackjackPlayer).where(
            and_(
                BlackjackPlayer.game_id == game_id,
                BlackjackPlayer.join_order == game.current_turn
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def hit(self, channel_id: int, player_id: int) -> Dict:
        """히트 - 카드 한 장 더 받기"""
        game = await self.get_current_game(channel_id)
        if not game or game.status != 'playing':
            raise ValueError("진행 중인 게임이 없습니다.")
        
        # 현재 턴 플레이어 확인
        current_player = await self.get_current_turn_player(game.id)
        if not current_player or str(player_id) != current_player.discord_id:
            if current_player:
                raise ValueError(f"당신의 차례가 아닙니다! 현재 **{current_player.username}**님의 차례입니다.")
            raise ValueError("잘못된 요청입니다.")
        
        # 스플릿 여부 확인
        if current_player.is_split:
            # 현재 플레이 중인 핸드
            if current_player.current_hand == 1:
                if current_player.status in ['stand', 'bust', 'blackjack']:
                    raise ValueError("첫 번째 핸드가 이미 종료되었습니다.")
                
                # 첫 번째 핸드에 카드 추가
                deck = Deck.from_json(game.deck)
                hand = Hand.from_json(current_player.cards)
                new_card = deck.draw()
                hand.add_card(new_card)
                
                current_player.cards = hand.to_json()
                game.deck = deck.to_json()
                
                # 버스트 체크
                if hand.is_bust():
                    current_player.status = 'bust'
                    # 두 번째 핸드로 자동 전환
                    current_player.current_hand = 2
                    if not current_player.split_cards:
                        # 두 번째 핸드도 없으면 턴 종료
                        await self._advance_turn(game)
                
                await self.session.commit()
                
                return {
                    'card': new_card,
                    'hand': hand,
                    'bust': hand.is_bust(),
                    'player': current_player,
                    'hand_number': 1,
                    'auto_switch': hand.is_bust()
                }
            
            else:  # current_hand == 2
                if current_player.split_status in ['stand', 'bust', 'blackjack']:
                    raise ValueError("두 번째 핸드가 이미 종료되었습니다.")
                
                # 두 번째 핸드에 카드 추가
                deck = Deck.from_json(game.deck)
                hand2 = Hand.from_json(current_player.split_cards)
                new_card = deck.draw()
                hand2.add_card(new_card)
                
                current_player.split_cards = hand2.to_json()
                game.deck = deck.to_json()
                
                # 버스트 체크
                if hand2.is_bust():
                    current_player.split_status = 'bust'
                    # 다음 플레이어로
                    await self._advance_turn(game)
                
                await self.session.commit()
                
                return {
                    'card': new_card,
                    'hand': hand2,
                    'bust': hand2.is_bust(),
                    'player': current_player,
                    'hand_number': 2,
                    'auto_switch': False
                }
        
        else:
            # 일반 핸드
            if current_player.status in ['stand', 'bust', 'blackjack']:
                raise ValueError("이미 턴이 종료되었습니다.")
            
            # 카드 뽑기
            deck = Deck.from_json(game.deck)
            hand = Hand.from_json(current_player.cards)
            new_card = deck.draw()
            hand.add_card(new_card)
            
            # 업데이트
            current_player.cards = hand.to_json()
            game.deck = deck.to_json()
            
            # 버스트 체크
            if hand.is_bust():
                current_player.status = 'bust'
                await self._advance_turn(game)
            
            await self.session.commit()
            
            return {
                'card': new_card,
                'hand': hand,
                'bust': hand.is_bust(),
                'player': current_player,
                'hand_number': 1,
                'auto_switch': False
            }
    
    async def stand(self, channel_id: int, player_id: int) -> Dict:
        """스탠드 - 카드 받기 중단"""
        game = await self.get_current_game(channel_id)
        if not game or game.status != 'playing':
            raise ValueError("진행 중인 게임이 없습니다.")
        
        current_player = await self.get_current_turn_player(game.id)
        if not current_player or str(player_id) != current_player.discord_id:
            if current_player:
                raise ValueError(f"당신의 차례가 아닙니다! 현재 **{current_player.username}**님의 차례입니다.")
            raise ValueError("잘못된 요청입니다.")
        
        # 스플릿 여부 확인
        if current_player.is_split:
            if current_player.current_hand == 1:
                # 첫 번째 핸드 스탠드
                current_player.status = 'stand'
                hand = Hand.from_json(current_player.cards)
                
                # 두 번째 핸드로 전환
                current_player.current_hand = 2
                
                await self.session.commit()
                
                return {
                    'hand': hand,
                    'player': current_player,
                    'hand_number': 1,
                    'switch_to_hand2': True
                }
            
            else:  # current_hand == 2
                # 두 번째 핸드 스탠드
                current_player.split_status = 'stand'
                hand2 = Hand.from_json(current_player.split_cards)
                
                # 다음 플레이어로
                await self._advance_turn(game)
                await self.session.commit()
                
                return {
                    'hand': hand2,
                    'player': current_player,
                    'hand_number': 2,
                    'switch_to_hand2': False
                }
        
        else:
            # 일반 핸드
            current_player.status = 'stand'
            hand = Hand.from_json(current_player.cards)
            
            # 다음 턴으로
            await self._advance_turn(game)
            await self.session.commit()
            
            return {
                'hand': hand,
                'player': current_player,
                'hand_number': 1,
                'switch_to_hand2': False
            }
    
    async def double_down(self, channel_id: int, player_id: int) -> Dict:
        """더블다운 - 배팅 2배, 카드 1장만 더 받고 스탠드"""
        game = await self.get_current_game(channel_id)
        if not game or game.status != 'playing':
            raise ValueError("진행 중인 게임이 없습니다.")
        
        current_player = await self.get_current_turn_player(game.id)
        if not current_player or str(player_id) != current_player.discord_id:
            if current_player:
                raise ValueError(f"당신의 차례가 아닙니다!")
            raise ValueError("잘못된 요청입니다.")
        
        # 처음 2장일 때만 가능
        hand = Hand.from_json(current_player.cards)
        if len(hand.cards) != 2:
            raise ValueError("더블다운은 처음 2장일 때만 가능합니다.")
        
        # 코인 확인
        user = await self._get_user(player_id)
        if user.coins < current_player.bet_amount:
            raise ValueError(f"코인이 부족합니다. (필요: {current_player.bet_amount})")
        
        # 배팅 2배
        user.coins -= current_player.bet_amount
        current_player.bet_amount *= 2
        current_player.is_doubled = True
        
        # 카드 1장 뽑기
        deck = Deck.from_json(game.deck)
        new_card = deck.draw()
        hand.add_card(new_card)
        
        current_player.cards = hand.to_json()
        game.deck = deck.to_json()
        
        # 자동 스탠드 (또는 버스트)
        if hand.is_bust():
            current_player.status = 'bust'
        else:
            current_player.status = 'stand'
        
        await self._advance_turn(game)
        await self.session.commit()
        
        return {
            'card': new_card,
            'hand': hand,
            'bust': hand.is_bust(),
            'player': current_player
        }
    
    async def insurance(self, channel_id: int, player_id: int) -> Dict:
        """인슈어런스 - 딜러가 블랙잭일 경우 보험"""
        game = await self.get_current_game(channel_id)
        if not game or game.status != 'playing':
            raise ValueError("진행 중인 게임이 없습니다.")
        
        # 딜러의 오픈 카드 확인
        dealer_hand = Hand.from_json(game.dealer_cards)
        if dealer_hand.cards[0].rank != 'A':
            raise ValueError("인슈어런스는 딜러의 오픈 카드가 A일 때만 가능합니다.")
        
        # 플레이어 확인
        stmt = select(BlackjackPlayer).where(
            and_(
                BlackjackPlayer.game_id == game.id,
                BlackjackPlayer.discord_id == str(player_id)
            )
        )
        result = await self.session.execute(stmt)
        player = result.scalar_one_or_none()
        
        if not player:
            raise ValueError("게임에 참가하지 않았습니다.")
        
        if player.has_insurance:
            raise ValueError("이미 인슈어런스를 신청했습니다.")
        
        # 처음 2장일 때만 가능
        hand = Hand.from_json(player.cards)
        if len(hand.cards) != 2:
            raise ValueError("인슈어런스는 처음 카드를 받았을 때만 가능합니다.")
        
        # 보험금 = 원래 배팅의 절반
        insurance_cost = player.bet_amount // 2
        
        # 코인 확인
        user = await self._get_user(player_id)
        if user.coins < insurance_cost:
            raise ValueError(f"코인이 부족합니다. (필요: {insurance_cost})")
        
        # 보험 구매
        user.coins -= insurance_cost
        player.has_insurance = True
        player.insurance_amount = insurance_cost
        
        await self.session.commit()
        
        # 딜러 블랙잭 확인
        dealer_blackjack = dealer_hand.is_blackjack()
        
        return {
            'insurance_cost': insurance_cost,
            'dealer_blackjack': dealer_blackjack,
            'player': player
        }
    
    async def split(self, channel_id: int, player_id: int) -> Dict:
        """스플릿 - 같은 숫자 2장을 분리해서 2개 핸드로"""
        game = await self.get_current_game(channel_id)
        if not game or game.status != 'playing':
            raise ValueError("진행 중인 게임이 없습니다.")
        
        current_player = await self.get_current_turn_player(game.id)
        if not current_player or str(player_id) != current_player.discord_id:
            if current_player:
                raise ValueError(f"당신의 차례가 아닙니다!")
            raise ValueError("잘못된 요청입니다.")
        
        if current_player.is_split:
            raise ValueError("이미 스플릿했습니다.")
        
        # 스플릿 가능 확인
        hand = Hand.from_json(current_player.cards)
        if not hand.can_split():
            raise ValueError("스플릿할 수 없는 핸드입니다. (같은 숫자 2장 필요)")
        
        # 추가 배팅 필요
        user = await self._get_user(player_id)
        if user.coins < current_player.bet_amount:
            raise ValueError(f"코인이 부족합니다. (필요: {current_player.bet_amount})")
        
        # 배팅 차감 및 2배로
        user.coins -= current_player.bet_amount
        original_bet = current_player.bet_amount
        current_player.bet_amount *= 2
        
        # 카드 분리
        card1 = hand.cards[0]
        card2 = hand.cards[1]
        
        deck = Deck.from_json(game.deck)
        
        # 첫 번째 핸드 (기존)
        hand1 = Hand([card1])
        hand1.add_card(deck.draw())
        
        # 두 번째 핸드 (새로 생성)
        hand2 = Hand([card2])
        hand2.add_card(deck.draw())
        
        current_player.cards = hand1.to_json()
        current_player.split_cards = hand2.to_json()
        current_player.is_split = True
        current_player.current_hand = 1  # 첫 번째 핸드부터 시작
        current_player.split_status = 'playing'  # 두 번째 핸드 상태 초기화
        game.deck = deck.to_json()
        
        await self.session.commit()
        
        return {
            'hand1': hand1,
            'hand2': hand2,
            'player': current_player,
            'bet_per_hand': original_bet
        }

    
    async def _advance_turn(self, game: BlackjackGame) -> Optional[BlackjackPlayer]:
        """다음 턴으로 진행"""
        players = await self.get_players(game.id)
        
        # 모든 플레이어가 종료되었는지 확인
        active_players = [p for p in players if p.status == 'playing']
        
        if not active_players:
            # 딜러 턴으로
            game.status = 'dealer_turn'
            return None
        
        # 다음 active 플레이어 찾기
        for player in players:
            if player.join_order > game.current_turn and player.status == 'playing':
                game.current_turn = player.join_order
                return player
        
        # 다시 처음부터 찾기
        for player in players:
            if player.status == 'playing':
                game.current_turn = player.join_order
                return player
        
        # 모두 종료
        game.status = 'dealer_turn'
        return None
    
    async def play_dealer(self, game_id: int) -> Dict:
        """딜러 턴 진행"""
        stmt = select(BlackjackGame).where(BlackjackGame.id == game_id)
        result = await self.session.execute(stmt)
        game = result.scalar_one_or_none()
        
        if not game or game.status != 'dealer_turn':
            raise ValueError("딜러 턴이 아닙니다.")
        
        deck = Deck.from_json(game.deck)
        dealer_hand = Hand.from_json(game.dealer_cards)
        
        drawn_cards = []
        
        # 딜러 규칙: 16 이하 히트, 17 이상 스탠드
        while dealer_hand.value() < 17:
            card = deck.draw()
            dealer_hand.add_card(card)
            drawn_cards.append(card)
        
        game.dealer_cards = dealer_hand.to_json()
        game.deck = deck.to_json()
        game.status = 'finished'
        game.finished_at = datetime.utcnow()
        
        # 결과 계산
        await self._calculate_results(game, dealer_hand)
        
        await self.session.commit()
        
        return {
            'dealer_hand': dealer_hand,
            'drawn_cards': drawn_cards,
            'dealer_value': dealer_hand.value(),
            'dealer_bust': dealer_hand.is_bust()
        }
    
    async def _calculate_results(self, game: BlackjackGame, dealer_hand: Hand):
        """결과 계산 및 지급"""
        players = await self.get_players(game.id)
        dealer_value = dealer_hand.value()
        dealer_blackjack = dealer_hand.is_blackjack()
        dealer_bust = dealer_hand.is_bust()
        
        for player in players:
            hand = Hand.from_json(player.cards)
            player_value = hand.value()
            player_blackjack = hand.is_blackjack()
            player_bust = hand.is_bust()
            
            user = await self._get_user(int(player.discord_id))
            
            # 인슈어런스 처리
            if player.has_insurance:
                if dealer_blackjack:
                    # 딜러 블랙잭 - 보험금 2:1 지급
                    insurance_payout = player.insurance_amount * 2
                    user.coins += insurance_payout
                # 딜러 블랙잭 아니면 보험금은 이미 차감됨
            
            total_payout = 0
            
            # 스플릿 처리 - 두 핸드 모두 계산
            if player.is_split and player.split_cards:
                # 첫 번째 핸드 계산
                payout1 = self._calculate_hand_result(
                    hand, player_blackjack, player_bust,
                    dealer_value, dealer_blackjack, dealer_bust,
                    player.bet_amount // 2  # 스플릿이면 배팅이 2배니까 절반씩
                )
                
                # 두 번째 핸드 계산
                hand2 = Hand.from_json(player.split_cards)
                hand2_value = hand2.value()
                hand2_blackjack = hand2.is_blackjack()
                hand2_bust = hand2.is_bust()
                
                payout2 = self._calculate_hand_result(
                    hand2, hand2_blackjack, hand2_bust,
                    dealer_value, dealer_blackjack, dealer_bust,
                    player.bet_amount // 2
                )
                
                total_payout = payout1 + payout2
                
                # 결과 판정 (둘 중 하나라도 이기면 win)
                if payout1 > player.bet_amount // 2 or payout2 > player.bet_amount // 2:
                    player.result = 'win'
                    user.games_won += 1
                elif payout1 == 0 and payout2 == 0:
                    player.result = 'lose'
                else:
                    player.result = 'push'
                
            else:
                # 일반 핸드 계산
                total_payout = self._calculate_hand_result(
                    hand, player_blackjack, player_bust,
                    dealer_value, dealer_blackjack, dealer_bust,
                    player.bet_amount
                )
                
                # 결과 판정
                if player_bust:
                    player.result = 'lose'
                elif player_blackjack and not dealer_blackjack:
                    player.result = 'blackjack'
                    user.games_won += 1
                elif total_payout > player.bet_amount:
                    player.result = 'win'
                    user.games_won += 1
                elif total_payout == player.bet_amount:
                    player.result = 'push'
                else:
                    player.result = 'lose'
            
            player.payout = total_payout
            user.coins += total_payout
            
            user.games_played += 1
            if player.result == 'lose':
                user.games_lost += 1
    
    def _calculate_hand_result(
        self,
        hand: Hand,
        is_blackjack: bool,
        is_bust: bool,
        dealer_value: int,
        dealer_blackjack: bool,
        dealer_bust: bool,
        bet_amount: int
    ) -> int:
        """단일 핸드 결과 계산 (지급액 반환)"""
        player_value = hand.value()
        
        # 버스트
        if is_bust:
            return 0
        
        # 블랙잭
        if is_blackjack:
            if dealer_blackjack:
                return bet_amount  # 푸시
            else:
                return int(bet_amount * (1 + self.BLACKJACK_PAYOUT))  # 1.5배
        
        # 딜러 버스트
        if dealer_bust:
            return bet_amount * 2  # 1배 수익
        
        # 값 비교
        if player_value > dealer_value:
            return bet_amount * 2  # 1배 수익
        elif player_value == dealer_value:
            return bet_amount  # 푸시
        else:
            return 0  # 패배