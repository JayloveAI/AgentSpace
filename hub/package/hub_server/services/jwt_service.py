"""
JWT Service - 门票签发与验证
============================
负责签发防伪门票和验证门票有效性
"""
import jwt
from datetime import datetime, timedelta
from typing import Optional
from ..config import HUB_JWT_SECRET, JWT_EXPIRATION_MINUTES


class JWTService:
    """JWT 门票服务"""
    
    def __init__(self, secret: str = HUB_JWT_SECRET):
        self.secret = secret
        self.algorithm = "HS256"  # 对称加密
    
    def issue_match_token(
        self,
        seeker_id: str,
        provider_id: str,
        seeker_endpoint: str
    ) -> str:
        """
        签发撮合门票
        
        Args:
            seeker_id: 需求方 Agent ID
            provider_id: 服务方 Agent ID
            seeker_endpoint: 需求方回调地址
        
        Returns:
            JWT 编码的门票字符串
        """
        payload = {
            "seeker": seeker_id,
            "provider": provider_id,
            "reply_to": seeker_endpoint,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES),
            "type": "match_ticket"
        }
        
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)
    
    def verify_match_token(self, token: str) -> dict:
        """
        验证门票有效性
        
        Args:
            token: JWT 门票字符串
        
        Returns:
            解码后的 payload
            
        Raises:
            jwt.ExpiredSignatureError: 门票已过期
            jwt.InvalidTokenError: 门票无效
        """
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                options={
                    "require": ["seeker", "provider", "reply_to", "type"]
                }
            )
            
            # 验证门票类型
            if payload.get("type") != "match_ticket":
                raise jwt.InvalidTokenError("Invalid ticket type")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise jwt.ExpiredSignatureError("Match ticket has expired")
        except jwt.InvalidTokenError as e:
            raise jwt.InvalidTokenError(f"Invalid match ticket: {str(e)}")
    
    def decode_without_verification(self, token: str) -> dict:
        """
        仅解码不验证（用于获取 issuer 等信息）
        警告：不要用于身份验证！
        """
        return jwt.decode(token, options={"verify_signature": False})
    
    def get_token_hash(self, token: str) -> str:
        """
        获取门票哈希值（用于防重）
        """
        import hashlib
        return hashlib.sha256(token.encode()).hexdigest()


# 全局单例
jwt_service = JWTService()
