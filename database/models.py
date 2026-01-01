"""
데이터베이스 모델 정의
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class User(Base):
    """사용자 정보 테이블"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    discord_id = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, nullable=False)
    coins = Column(Integer, default=5000)  # 기본 코인 5000개
    games_played = Column(Integer, default=0)
    games_won = Column(Integer, default=0)
    games_lost = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<User(discord_id={self.discord_id}, username={self.username}, coins={self.coins})>"


class RouletteGame(Base):
    """러시안 룰렛 게임 테이블"""
    __tablename__ = 'roulette_games'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(String, nullable=False, index=True)
    channel_id = Column(String, nullable=False)
    host_id = Column(String, nullable=False)  # 게임 생성자
    bet_amount = Column(Integer, default=100)  # 판돈
    max_players = Column(Integer, default=6)
    current_turn = Column(Integer, default=1)  # 현재 턴 (join_order 기준)
    status = Column(String, default='waiting')  # waiting, playing, finished
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<RouletteGame(id={self.id}, status={self.status}, players={self.max_players})>"


class RoulettePlayer(Base):
    """러시안 룰렛 게임 참가자 테이블"""
    __tablename__ = 'roulette_players'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('roulette_games.id'), nullable=False)
    discord_id = Column(String, nullable=False)
    username = Column(String, nullable=False)
    join_order = Column(Integer, nullable=False)  # 참가 순서
    is_alive = Column(Boolean, default=True)
    is_winner = Column(Boolean, default=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<RoulettePlayer(discord_id={self.discord_id}, game_id={self.game_id})>"


class BlackjackGame(Base):
    """블랙잭 게임 테이블"""
    __tablename__ = 'blackjack_games'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(String, nullable=False, index=True)
    channel_id = Column(String, nullable=False)
    host_id = Column(String, nullable=False)
    current_turn = Column(Integer, default=1)  # 현재 턴 (join_order 기준)
    dealer_cards = Column(String, default='')  # JSON 문자열로 저장
    deck = Column(String, default='')  # 남은 덱 (JSON)
    status = Column(String, default='waiting')  # waiting, playing, dealer_turn, finished
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<BlackjackGame(id={self.id}, status={self.status})>"


class BlackjackPlayer(Base):
    """블랙잭 게임 참가자 테이블"""
    __tablename__ = 'blackjack_players'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('blackjack_games.id'), nullable=False)
    discord_id = Column(String, nullable=False)
    username = Column(String, nullable=False)
    join_order = Column(Integer, nullable=False)
    bet_amount = Column(Integer, nullable=False)
    cards = Column(String, default='')  # JSON 문자열로 저장
    status = Column(String, default='playing')  # playing, stand, bust, blackjack
    result = Column(String, nullable=True)  # win, lose, push, blackjack
    payout = Column(Integer, default=0)
    has_insurance = Column(Boolean, default=False)
    insurance_amount = Column(Integer, default=0)
    is_doubled = Column(Boolean, default=False)
    is_split = Column(Boolean, default=False)
    split_cards = Column(String, nullable=True)  # 스플릿 시 두 번째 핸드
    split_status = Column(String, nullable=True)  # 두 번째 핸드 상태
    current_hand = Column(Integer, default=1)  # 현재 플레이 중인 핸드 (1 or 2)
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<BlackjackPlayer(discord_id={self.discord_id}, bet={self.bet_amount})>"


class SlotPlay(Base):
    """슬롯머신 플레이 기록"""
    __tablename__ = 'slot_plays'
    
    id = Column(Integer, primary_key=True)
    discord_id = Column(String, nullable=False, index=True)
    username = Column(String, nullable=False)
    bet_amount = Column(Integer, nullable=False)
    reel1 = Column(String, nullable=False)
    reel2 = Column(String, nullable=False)
    reel3 = Column(String, nullable=False)
    is_win = Column(Boolean, default=False)
    payout = Column(Integer, default=0)
    multiplier = Column(Integer, default=0)
    played_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<SlotPlay(discord_id={self.discord_id}, result={self.reel1}{self.reel2}{self.reel3})>"