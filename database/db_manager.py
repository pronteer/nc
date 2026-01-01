"""
데이터베이스 관리자
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from config import Config
from database.models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """데이터베이스 연결 및 세션 관리"""
    
    def __init__(self):
        # SQLite URL 변환 (sqlite:/// → sqlite+aiosqlite:///)
        db_url = Config.DATABASE_URL
        if db_url.startswith('sqlite:///'):
            db_url = db_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
        
        self.engine = create_async_engine(
            db_url,
            echo=False,  # SQL 쿼리 로깅 (개발 시 True)
            poolclass=NullPool,  # SQLite는 연결 풀링 불필요
        )
        
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        logger.info(f"데이터베이스 연결 설정 완료: {db_url}")
    
    async def init_database(self):
        """데이터베이스 초기화 (테이블 생성)"""
        # 데이터베이스 디렉토리 생성
        db_path = Config.DATABASE_URL.replace('sqlite:///', '')
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        async with self.engine.begin() as conn:
            # 모든 테이블 생성
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("✓ 데이터베이스 테이블 생성 완료")
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        비동기 세션 컨텍스트 매니저
        
        사용 예시:
            async with db_manager.session() as session:
                # 데이터베이스 작업
                user = await session.get(User, user_id)
        """
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def close(self):
        """데이터베이스 연결 종료"""
        await self.engine.dispose()
        logger.info("데이터베이스 연결 종료")