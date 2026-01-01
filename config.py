import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


class Config:
    """봇 설정 관리 클래스"""
    
    # ===== .env에서 가져오는 보안 정보 =====
    BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    
    # ===== .env에서 가져오는 기본 설정 =====
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///data/bot.db')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_DIR = 'data/logs'
    
    @classmethod
    def validate(cls) -> bool:
        """필수 설정값 검증"""
        if not cls.BOT_TOKEN:
            raise ValueError("DISCORD_BOT_TOKEN이 필수입니다. .env 파일을 확인하세요.")
        return True
    
    @classmethod
    def print_config(cls):
        """현재 설정 출력 (디버깅용)"""
        print("=" * 60)
        print("🤖 봇 설정 정보")
        print("=" * 60)
        print(f"  봇 토큰: {'✅ 설정됨' if cls.BOT_TOKEN else '❌ 없음'}")
        print(f"  로그 레벨: {cls.LOG_LEVEL}")
        print(f"  데이터베이스: {cls.DATABASE_URL}")
        print("=" * 60)


if __name__ == "__main__":
    # 테스트
    try:
        Config.validate()
        Config.print_config()
    except Exception as e:
        print(f"❌ 설정 오류: {e}")