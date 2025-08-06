from sqlmodel import SQLModel, Field, select
from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from gsuid_core.utils.database.base_models import with_session
from gsuid_core.utils.database.startup import exec_list
import json
import logging

logger = logging.getLogger(__name__)

class SlashRoleRecord(SQLModel, table=True):
    """冥海记录中的角色信息"""
    __tablename__ = "slash_role_records"
    id: Optional[int] = Field(default=None, primary_key=True)
    slash_record_id: int = Field(foreign_key="slash_records.id")
    char_id: str = Field(index=True)
    char_name: str
    char_level: int
    char_ascension: int
    char_weapon_id: str
    char_weapon_name: str
    char_weapon_level: int
    char_weapon_ascension: int
    char_echo_id: str
    char_echo_name: str
    char_echo_level: int
    char_echo_ascension: int
    char_chain_count: int
    team_index: int = Field(default=0)  # 队伍索引：0=队伍一，1=队伍二
    team_score: int = Field(default=0)  # 该队伍的分数
    user_id: str = Field(index=True)
    bot_id: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.now)
    
    @classmethod
    async def _save_slash_role_record_internal(cls, session: AsyncSession, slash_record_id: int, char_data: dict, user_id: str, bot_id: str):
        """内部方法：在现有session中保存角色记录"""
        role_record = cls(
            slash_record_id=slash_record_id,
            char_id=char_data.get("char_id", ""),
            char_name=char_data.get("char_name", ""),
            char_level=char_data.get("char_level", 0),
            char_ascension=char_data.get("char_ascension", 0),
            char_weapon_id=char_data.get("char_weapon_id", ""),
            char_weapon_name=char_data.get("char_weapon_name", ""),
            char_weapon_level=char_data.get("char_weapon_level", 0),
            char_weapon_ascension=char_data.get("char_weapon_ascension", 0),
            char_echo_id=char_data.get("char_echo_id", ""),
            char_echo_name=char_data.get("char_echo_name", ""),
            char_echo_level=char_data.get("char_echo_level", 0),
            char_echo_ascension=char_data.get("char_echo_ascension", 0),
            char_chain_count=char_data.get("char_chain_count", 0),
            team_index=char_data.get("team_index", 0),
            team_score=char_data.get("team_score", 0),
            user_id=user_id,
            bot_id=bot_id
        )
        session.add(role_record)
        await session.flush()
        return role_record

    @classmethod
    @with_session
    async def save_slash_role_record(cls, session: AsyncSession, slash_record_id: int, char_data: dict, user_id: str, bot_id: str):
        """保存角色记录"""
        return await cls._save_slash_role_record_internal(session, slash_record_id, char_data, user_id, bot_id)
    
    @classmethod
    @with_session
    async def get_slash_role_records(cls, session: AsyncSession, slash_record_id: int) -> List["SlashRoleRecord"]:
        """获取指定冥海记录的所有角色记录"""
        statement = select(cls).where(cls.slash_record_id == slash_record_id)
        result = await session.execute(statement)
        return result.scalars().all()
    
    @classmethod
    async def _delete_role_records_by_slash_record_id_internal(cls, session: AsyncSession, slash_record_id: int):
        """内部方法：在现有session中删除指定冥海记录的所有角色记录"""
        from sqlalchemy import delete
        statement = delete(cls).where(cls.slash_record_id == slash_record_id)
        await session.execute(statement)

    @classmethod
    @with_session
    async def delete_role_records_by_slash_record_id(cls, session: AsyncSession, slash_record_id: int):
        """删除指定冥海记录的所有角色记录"""
        await cls._delete_role_records_by_slash_record_id_internal(session, slash_record_id)


class SlashRecord(SQLModel, table=True):
    """冥海记录主表"""
    __tablename__ = "slash_records"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    bot_id: str = Field(index=True)
    uid: str = Field(index=True)
    nickname: str
    level: int  # 账号等级
    world_level: int
    slash_level: int
    slash_score: int
    slash_time: int
    slash_date: str
    rank: str = Field(default="")  # 游戏API返回的评级
    # 关系字段，不直接存储在数据库中，通过外键关联
    created_at: datetime = Field(default_factory=datetime.now)
    
    @classmethod
    @with_session
    async def save_slash_record(cls, session: AsyncSession, slash_data: dict, user_id: str, bot_id: str) -> "SlashRecord":
        """保存冥海记录（如果已存在则更新）"""
        uid = slash_data.get("uid", "")
        slash_level = slash_data.get("slash_level", 0)
        # 检查是否已存在相同UID和层数的记录
        existing_record = await cls.get_latest_slash_record_by_uid_and_level(uid, slash_level)
        if existing_record:
            # 删除旧的角色记录
            await SlashRoleRecord._delete_role_records_by_slash_record_id_internal(session, existing_record.id)
            # 更新主记录 - 使用最新数据覆盖所有字段
            existing_record.nickname = slash_data.get("nickname", "")
            existing_record.level = slash_data.get("level", 0)
            existing_record.world_level = slash_data.get("world_level", 0)
            existing_record.slash_score = slash_data.get("slash_score", 0)
            existing_record.slash_time = slash_data.get("slash_time", 0)
            existing_record.slash_date = slash_data.get("slash_date", "")
            existing_record.rank = slash_data.get("rank", "")
            existing_record.created_at = datetime.now()
            await session.flush()
            # 保存新的角色记录
            roles_data = slash_data.get("roles", [])
            for role_data in roles_data:
                await SlashRoleRecord._save_slash_role_record_internal(session, existing_record.id, role_data, user_id, bot_id)
            return existing_record
        else:
            # 不存在记录，创建新记录
            slash_record = cls(
                user_id=user_id, bot_id=bot_id, uid=uid, nickname=slash_data.get("nickname", ""),
                level=slash_data.get("level", 0), world_level=slash_data.get("world_level", 0), slash_level=slash_level,
                slash_score=slash_data.get("slash_score", 0), slash_time=slash_data.get("slash_time", 0),
                slash_date=slash_data.get("slash_date", ""), rank=slash_data.get("rank", "")  # 保存评级
            )
            session.add(slash_record)
            await session.flush()
            # 保存角色记录
            roles_data = slash_data.get("roles", [])
            for role_data in roles_data:
                await SlashRoleRecord._save_slash_role_record_internal(session, slash_record.id, role_data, user_id, bot_id)
            return slash_record
    
    @classmethod
    @with_session
    async def get_slash_records(cls, session: AsyncSession, user_id: str, bot_id: str, limit: int = 10) -> List["SlashRecord"]:
        """获取用户的冥海记录"""
        statement = (select(cls).where(cls.user_id == user_id, cls.bot_id == bot_id)
                    .order_by(cls.created_at.desc()).limit(limit))
        result = await session.execute(statement)
        return result.scalars().all()
    
    @classmethod
    @with_session
    async def get_all_slash_records_for_ranking(cls, session: AsyncSession, limit: int = 100) -> List["SlashRecord"]:
        """获取所有用户的冥海记录用于排行"""
        statement = (select(cls).where(cls.slash_level == 12)  # 只获取第12层（无尽层）的记录
                    .order_by(cls.slash_score.desc(), cls.created_at.desc()).limit(limit))
        result = await session.execute(statement)
        return result.scalars().all()
    
    @classmethod
    @with_session
    async def get_latest_slash_record_by_uid(cls, session: AsyncSession, uid: str) -> Optional["SlashRecord"]:
        """根据UID获取最新的冥海记录"""
        statement = (select(cls).where(cls.uid == uid, cls.slash_level == 12)
                    .order_by(cls.created_at.desc()).limit(1))
        result = await session.execute(statement)
        return result.scalars().first()
    
    @classmethod
    @with_session
    async def get_latest_slash_record_by_uid_and_level(cls, session: AsyncSession, uid: str, slash_level: int) -> Optional["SlashRecord"]:
        """根据UID和层数获取最新的冥海记录"""
        statement = (select(cls).where(cls.uid == uid, cls.slash_level == slash_level)
                    .order_by(cls.created_at.desc()).limit(1))
        result = await session.execute(statement)
        return result.scalars().first()
    
    @classmethod
    @with_session
    async def get_slash_records_by_uids_and_level(cls, session: AsyncSession, uids: List[str], slash_level: int) -> List["SlashRecord"]:
        """批量获取多个UID的指定层数最新冥海记录"""
        if not uids: return []
        # 使用窗口函数获取每个UID的最新记录
        from sqlalchemy import func, text
        # 构建子查询，为每个UID的每个层数记录按时间排序并标记行号
        subquery = (select(
            cls.id, cls.user_id, cls.bot_id, cls.uid, cls.nickname, cls.level, cls.world_level,
            cls.slash_level, cls.slash_score, cls.slash_time, cls.slash_date, cls.rank, cls.created_at,
            func.row_number().over(partition_by=[cls.uid, cls.slash_level], order_by=cls.created_at.desc()).label('rn')
        ).where(cls.uid.in_(uids), cls.slash_level == slash_level).subquery())
        # 主查询，只获取每个UID每个层数的最新记录（rn=1）
        statement = (select(cls).join(subquery, cls.id == subquery.c.id).where(subquery.c.rn == 1))
        result = await session.execute(statement)
        return result.scalars().all()