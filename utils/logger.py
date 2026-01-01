"""
로깅 설정 모듈
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from config import Config


def setup_logger():
    """로거 설정"""
    # 로그 디렉토리 생성
    os.makedirs(Config.LOG_DIR, exist_ok=True)
    
    # 루트 로거 설정
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, Config.LOG_LEVEL))
    
    # 포맷터 설정
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 파일 핸들러 - 전체 로그
    file_handler = RotatingFileHandler(
        f'{Config.LOG_DIR}/bot.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 크롤러 로그
    crawler_handler = RotatingFileHandler(
        f'{Config.LOG_DIR}/crawler.log',
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    crawler_handler.setLevel(logging.DEBUG)
    crawler_handler.setFormatter(formatter)
    
    crawler_logger = logging.getLogger('crawlers')
    crawler_logger.addHandler(crawler_handler)
    
    # 에러 로그
    error_handler = RotatingFileHandler(
        f'{Config.LOG_DIR}/error.log',
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    # Discord.py 로거 설정
    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(logging.WARNING)
    
    return logger
