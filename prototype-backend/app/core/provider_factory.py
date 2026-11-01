"""
LLM Provider工厂，根据数据库配置或环境变量选择provider
"""
import os
from sqlalchemy.orm import Session
from app.core.llm_provider import LLMProvider, MockLLMProvider
from app.core.providers.openai_provider import OpenAIProvider
from app.core.providers.ollama_provider import OllamaProvider
from app.core.providers.gemini_provider import GeminiProvider
from app.core.providers.claude_provider import ClaudeProvider
from app.core.providers.minimax_provider import MiniMaxProvider
from app.core.providers.doubao_provider import DoubaoProvider
from app.db import SessionLocal
from app.schemas.ai_config import validate_base_url


def get_llm_provider(db: Session = None) -> LLMProvider:
    """
    根据数据库配置或环境变量获取LLM Provider实例
    
    优先从数据库读取激活的配置，如果没有则从环境变量读取
    
    环境变量 LLM_PROVIDER 可选值：
    - "openai": 使用OpenAI API
    - "ollama": 使用Ollama本地模型
    - 其他或未设置: 使用Mock实现
    """
    # 尝试从数据库读取配置
    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False
    
    try:
        from app.models.ai_config import AIConfig
        active_config = db.query(AIConfig).filter(AIConfig.is_active == True).first()
        
        if active_config:
            # 从数据库配置创建provider
            provider = _create_provider_from_config(active_config)
            if provider:
                return provider
    except Exception as e:
        raise RuntimeError("Unable to load the configured model provider") from e
    finally:
        if should_close:
            db.close()
    
    # 回退到环境变量
    provider_name = os.getenv("LLM_PROVIDER", "mock").lower()
    
    if provider_name == "openai":
        return OpenAIProvider()
    if provider_name == "ollama":
        return OllamaProvider()
    if provider_name == "mock":
        return MockLLMProvider()
    raise ValueError("Unknown model provider")


def _create_provider_from_config(config) -> LLMProvider:
    """根据数据库配置创建provider实例"""
    try:
        validate_base_url(config.base_url)
        provider_name = config.provider.lower()
        
        if provider_name == "openai":
            return OpenAIProvider(
                api_key=config.api_key or '',
                base_url=config.base_url,
                model=config.model
            )
        elif provider_name == "ollama":
            return OllamaProvider(
                base_url=config.base_url,
                model=config.model
            )
        elif provider_name == "gemini":
            return GeminiProvider(
                api_key=config.api_key or '',
                base_url=config.base_url,
                model=config.model
            )
        elif provider_name == "claude":
            return ClaudeProvider(
                api_key=config.api_key or '',
                base_url=config.base_url,
                model=config.model
            )
        elif provider_name == "minimax":
            return MiniMaxProvider(
                api_key=config.api_key or '',
                base_url=config.base_url,
                model=config.model
            )
        elif provider_name == "doubao":
            return DoubaoProvider(
                api_key=config.api_key or '',
                base_url=config.base_url,
                model=config.model
            )
        elif provider_name in ["deepseek", "qwen", "moonshot", "zhipu", "baidu"]:
            # 这些提供商使用OpenAI兼容的API
            return OpenAIProvider(
                api_key=config.api_key or '',
                base_url=config.base_url,
                model=config.model
            )
        else:
            raise ValueError("Unknown configured model provider")
    except Exception as e:
        raise RuntimeError("Unable to initialize the configured model provider") from e

