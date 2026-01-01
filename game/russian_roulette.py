"""
러시안 룰렛 게임 로직
"""
import random
from typing import Optional, List, Dict
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import RouletteGame, RoulettePlayer, User


class RussianRouletteGame:
    """러시안 룰렛 게임 관리 클래스"""
    
    BULLET_PROBABILITY = 1/6  # 총알 확률 (고정)
    TIMEOUT_DURATION = 60  # 패배 시 타임아웃 시간 (초)
    WIN_REWARD = 5000  # 승리 시 보상 코인
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    def pull_trigger(self) -> bool:
        """
        방아쇠를 당김 (항상 1/6 확률)
        
        Returns:
            True: 총알 발사 (패배)
            False: 빈 탄창 (생존)
        """
        return random.random() < self.BULLET_PROBABILITY
    
    async def create_game(
        self, 
        guild_id: int, 
        channel_id: int, 
        host_id: int,
        host_name: str,
        max_players: int = 6
    ) -> Optional[RouletteGame]:
        """
        새 게임 생성
        
        Args:
            guild_id: 서버 ID
            channel_id: 채널 ID
            host_id: 호스트 Discord ID
            host_name: 호스트 이름
            max_players: 최대 플레이어 수
        
        Returns:
            생성된 게임 객체 또는 None
        """
        # 해당 채널에 진행 중인 게임이 있는지 확인
        stmt = select(RouletteGame).where(
            and_(
                RouletteGame.channel_id == str(channel_id),
                RouletteGame.status.in_(['waiting', 'playing'])
            )
        )
        result = await self.session.execute(stmt)
        existing_game = result.scalar_one_or_none()
        
        if existing_game:
            return None
        
        # 호스트 유저 확인/생성
        await self._get_or_create_user(host_id, host_name)
        
        # 새 게임 생성
        game = RouletteGame(
            guild_id=str(guild_id),
            channel_id=str(channel_id),
            host_id=str(host_id),
            bet_amount=0,  # 판돈 없음
            max_players=max_players,
            status='waiting'
        )
        self.session.add(game)
        await self.session.flush()
        
        # 호스트를 첫 번째 플레이어로 추가
        player = RoulettePlayer(
            game_id=game.id,
            discord_id=str(host_id),
            username=host_name,
            join_order=1
        )
        self.session.add(player)
        
        await self.session.commit()
        
        return game
    
    async def join_game(
        self,
        channel_id: int,
        player_id: int,
        player_name: str
    ) -> Optional[RoulettePlayer]:
        """
        게임에 참가
        
        Args:
            channel_id: 채널 ID
            player_id: 플레이어 Discord ID
            player_name: 플레이어 이름
        
        Returns:
            참가한 플레이어 객체 또는 None
        """
        # 대기 중인 게임 찾기
        stmt = select(RouletteGame).where(
            and_(
                RouletteGame.channel_id == str(channel_id),
                RouletteGame.status == 'waiting'
            )
        )
        result = await self.session.execute(stmt)
        game = result.scalar_one_or_none()
        
        if not game:
            return None
        
        # 이미 참가했는지 확인
        stmt = select(RoulettePlayer).where(
            and_(
                RoulettePlayer.game_id == game.id,
                RoulettePlayer.discord_id == str(player_id)
            )
        )
        result = await self.session.execute(stmt)
        existing_player = result.scalar_one_or_none()
        
        if existing_player:
            raise ValueError("이미 게임에 참가했습니다.")
        
        # 현재 플레이어 수 확인
        stmt = select(RoulettePlayer).where(RoulettePlayer.game_id == game.id)
        result = await self.session.execute(stmt)
        current_players = result.scalars().all()
        
        if len(current_players) >= game.max_players:
            raise ValueError("게임이 가득 찼습니다.")
        
        # 플레이어 유저 확인/생성
        await self._get_or_create_user(player_id, player_name)
        
        # 플레이어 추가
        player = RoulettePlayer(
            game_id=game.id,
            discord_id=str(player_id),
            username=player_name,
            join_order=len(current_players) + 1
        )
        self.session.add(player)
        
        await self.session.commit()
        
        return player
    
    async def start_game(self, channel_id: int, starter_id: int) -> Optional[RouletteGame]:
        """
        게임 시작
        
        Args:
            channel_id: 채널 ID
            starter_id: 시작 명령을 내린 사용자 ID
        
        Returns:
            시작된 게임 객체 또는 None
        """
        # 대기 중인 게임 찾기
        stmt = select(RouletteGame).where(
            and_(
                RouletteGame.channel_id == str(channel_id),
                RouletteGame.status == 'waiting'
            )
        )
        result = await self.session.execute(stmt)
        game = result.scalar_one_or_none()
        
        if not game:
            return None
        
        # 호스트만 시작 가능
        if str(starter_id) != game.host_id:
            raise ValueError("게임 호스트만 시작할 수 있습니다.")
        
        # 최소 2명 이상 필요
        stmt = select(RoulettePlayer).where(RoulettePlayer.game_id == game.id)
        result = await self.session.execute(stmt)
        players = result.scalars().all()
        
        if len(players) < 2:
            raise ValueError("최소 2명 이상의 플레이어가 필요합니다.")
        
        # 게임 상태 변경
        game.status = 'playing'
        game.started_at = datetime.utcnow()
        
        await self.session.commit()
        
        return game
    
    async def shoot(
        self,
        channel_id: int,
        shooter_id: int
    ) -> Dict:
        """
        방아쇠 당기기
        
        Args:
            channel_id: 채널 ID
            shooter_id: 쏘는 플레이어 ID
        
        Returns:
            결과 딕셔너리 {
                'hit': bool,  # 총알 맞았는지
                'game_over': bool,  # 게임 종료 여부
                'winners': List[RoulettePlayer],  # 승자들 (생존자)
                'loser': RoulettePlayer,  # 패자 (총알 맞은 사람)
                'reward': int,  # 승자 1인당 보상
                'next_player': Optional[RoulettePlayer]  # 다음 차례 플레이어
            }
        """
        # 진행 중인 게임 찾기
        stmt = select(RouletteGame).where(
            and_(
                RouletteGame.channel_id == str(channel_id),
                RouletteGame.status == 'playing'
            )
        )
        result = await self.session.execute(stmt)
        game = result.scalar_one_or_none()
        
        if not game:
            raise ValueError("진행 중인 게임이 없습니다.")
        
        # 플레이어 확인
        stmt = select(RoulettePlayer).where(
            and_(
                RoulettePlayer.game_id == game.id,
                RoulettePlayer.discord_id == str(shooter_id),
                RoulettePlayer.is_alive == True
            )
        )
        result = await self.session.execute(stmt)
        shooter = result.scalar_one_or_none()
        
        if not shooter:
            raise ValueError("당신은 이미 탈락했거나 게임에 참가하지 않았습니다.")
        
        # 턴 체크
        if shooter.join_order != game.current_turn:
            # 현재 턴인 플레이어 찾기
            stmt = select(RoulettePlayer).where(
                and_(
                    RoulettePlayer.game_id == game.id,
                    RoulettePlayer.join_order == game.current_turn,
                    RoulettePlayer.is_alive == True
                )
            )
            result = await self.session.execute(stmt)
            current_turn_player = result.scalar_one_or_none()
            
            if current_turn_player:
                raise ValueError(f"당신의 차례가 아닙니다! 현재 **{current_turn_player.username}**님의 차례입니다.")
            else:
                # 현재 턴 플레이어가 탈락했으면 다음 생존자 턴으로
                await self._advance_turn(game)
                raise ValueError("차례가 업데이트되었습니다. 다시 시도해주세요.")
        
        # 방아쇠 당기기 (항상 1/6 확률)
        hit = self.pull_trigger()
        
        result_data = {
            'hit': hit,
            'game_over': False,
            'winners': [],
            'loser': None,
            'reward': 0,
            'next_player': None
        }
        
        if hit:
            # 총알 맞음 - 게임 즉시 종료!
            shooter.is_alive = False
            result_data['loser'] = shooter
            result_data['game_over'] = True
            
            # 패자 통계 업데이트
            loser_user = await self._get_user(shooter_id)
            loser_user.games_played += 1
            loser_user.games_lost += 1
            
            # 모든 생존자를 승자로 설정
            stmt = select(RoulettePlayer).where(
                and_(
                    RoulettePlayer.game_id == game.id,
                    RoulettePlayer.is_alive == True
                )
            )
            result = await self.session.execute(stmt)
            survivors = result.scalars().all()
            
            # 생존자들에게 보상 지급
            for survivor in survivors:
                survivor.is_winner = True
                
                winner_user = await self._get_user(int(survivor.discord_id))
                winner_user.coins += self.WIN_REWARD
                winner_user.games_played += 1
                winner_user.games_won += 1
            
            result_data['winners'] = survivors
            result_data['reward'] = self.WIN_REWARD
            
            # 게임 종료
            game.status = 'finished'
            game.finished_at = datetime.utcnow()
        else:
            # 생존 - 다음 턴으로
            next_player = await self._advance_turn(game)
            result_data['next_player'] = next_player
        
        await self.session.commit()
        
        return result_data
    
    async def get_current_game(self, channel_id: int) -> Optional[RouletteGame]:
        """현재 채널의 활성 게임 가져오기"""
        stmt = select(RouletteGame).where(
            and_(
                RouletteGame.channel_id == str(channel_id),
                RouletteGame.status.in_(['waiting', 'playing'])
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_players(self, game_id: int) -> List[RoulettePlayer]:
        """게임의 모든 플레이어 가져오기"""
        stmt = select(RoulettePlayer).where(
            RoulettePlayer.game_id == game_id
        ).order_by(RoulettePlayer.join_order)
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def get_alive_players(self, game_id: int) -> List[RoulettePlayer]:
        """게임의 생존 플레이어 가져오기"""
        stmt = select(RoulettePlayer).where(
            and_(
                RoulettePlayer.game_id == game_id,
                RoulettePlayer.is_alive == True
            )
        ).order_by(RoulettePlayer.join_order)
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def cancel_game(self, channel_id: int, canceller_id: int) -> bool:
        """
        게임 취소
        
        Args:
            channel_id: 채널 ID
            canceller_id: 취소 명령을 내린 사용자 ID
        
        Returns:
            취소 성공 여부
        """
        # 대기 중인 게임 찾기
        stmt = select(RouletteGame).where(
            and_(
                RouletteGame.channel_id == str(channel_id),
                RouletteGame.status == 'waiting'
            )
        )
        result = await self.session.execute(stmt)
        game = result.scalar_one_or_none()
        
        if not game:
            return False
        
        # 호스트만 취소 가능
        if str(canceller_id) != game.host_id:
            raise ValueError("게임 호스트만 취소할 수 있습니다.")
        
        # 게임 취소
        game.status = 'cancelled'
        
        await self.session.commit()
        
        return True
    
    # === 헬퍼 메서드 ===
    
    async def _get_or_create_user(self, discord_id: int, username: str) -> User:
        """유저 가져오기 또는 생성"""
        from database.models import User
        
        stmt = select(User).where(User.discord_id == str(discord_id))
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                discord_id=str(discord_id),
                username=username,
                coins=5000  # 신규 유저 기본 코인
            )
            self.session.add(user)
            await self.session.flush()
        
        return user
    
    async def _get_user(self, discord_id: int) -> User:
        """유저 가져오기"""
        from database.models import User
        
        stmt = select(User).where(User.discord_id == str(discord_id))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def _get_player_count(self, game_id: int) -> int:
        """게임의 총 플레이어 수"""
        stmt = select(RoulettePlayer).where(RoulettePlayer.game_id == game_id)
        result = await self.session.execute(stmt)
        players = result.scalars().all()
        return len(players)
    
    async def _advance_turn(self, game: RouletteGame) -> Optional[RoulettePlayer]:
        """
        다음 턴으로 진행
        
        Returns:
            다음 차례 플레이어 (없으면 None)
        """
        # 모든 생존자 가져오기 (순서대로)
        stmt = select(RoulettePlayer).where(
            and_(
                RoulettePlayer.game_id == game.id,
                RoulettePlayer.is_alive == True
            )
        ).order_by(RoulettePlayer.join_order)
        result = await self.session.execute(stmt)
        alive_players = result.scalars().all()
        
        if not alive_players:
            return None
        
        # 현재 턴보다 큰 join_order 중 가장 작은 것 찾기
        next_player = None
        for player in alive_players:
            if player.join_order > game.current_turn:
                next_player = player
                break
        
        # 없으면 첫 번째 생존자로 (순환)
        if not next_player:
            next_player = alive_players[0]
        
        # 턴 업데이트
        game.current_turn = next_player.join_order
        
        return next_player
    
    async def get_current_turn_player(self, game_id: int) -> Optional[RoulettePlayer]:
        """현재 턴인 플레이어 가져오기"""
        # 게임 정보 가져오기
        stmt = select(RouletteGame).where(RouletteGame.id == game_id)
        result = await self.session.execute(stmt)
        game = result.scalar_one_or_none()
        
        if not game:
            return None
        
        # 현재 턴 플레이어 찾기
        stmt = select(RoulettePlayer).where(
            and_(
                RoulettePlayer.game_id == game_id,
                RoulettePlayer.join_order == game.current_turn,
                RoulettePlayer.is_alive == True
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()