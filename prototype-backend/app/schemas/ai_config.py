"""
AI配置相关的Schema
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from datetime import datetime
from urllib.parse import urlsplit


def validate_base_url(value):
    if value:
        url = urlsplit(value)
        if (url.scheme not in ("http", "https") or not url.hostname or url.username or url.password
                or url.query or url.fragment):
            raise ValueError("服务地址须为不含账号、密钥参数或片段的 HTTP(S) 地址")
        url.port
    return value


class AIConfigBase(BaseModel):
    """AI配置基础模型"""
    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    extra_config: Optional[Dict[str, Any]] = None

    @field_validator("base_url")
    @classmethod
    def check_base_url(cls, value):
        return validate_base_url(value)


class AIConfigCreate(AIConfigBase):
    """创建AI配置"""
    pass


class AIConfigUpdate(BaseModel):
    """更新AI配置"""
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    extra_config: Optional[Dict[str, Any]] = None

    @field_validator("base_url")
    @classmethod
    def check_base_url(cls, value):
        return validate_base_url(value)
    is_active: Optional[bool] = None


class AIConfigResponse(AIConfigBase):
    """AI配置响应模型"""
    api_key: Optional[str] = Field(default=None, exclude=True)
    has_key: bool = False
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("extra_config")
    @classmethod
    def hide_extra_credentials(cls, value):
        def clean(item):
            if isinstance(item, dict):
                return {key: clean(val) for key, val in item.items()
                        if not any(word in key.lower() for word in ("key", "token", "secret", "password", "authorization", "credential", "headers"))}
            if isinstance(item, list):
                return [clean(child) for child in item]
            return item
        return clean(value)

    class Config:
        from_attributes = True


class AIConfigListResponse(BaseModel):
    """AI配置列表响应"""
    configs: list[AIConfigResponse]
    active_provider: Optional[str] = None

