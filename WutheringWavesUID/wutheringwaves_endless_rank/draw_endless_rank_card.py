import json
import time
import asyncio
from pathlib import Path
from typing import List, Union, Optional
import aiofiles
from gsuid_core.bot import Bot
from pydantic import BaseModel
from gsuid_core.models import Event
from gsuid_core.logger import logger
from PIL import Image, ImageDraw, ImageFont
from gsuid_core.utils.image.convert import convert_img
from gsuid_core.utils.image.image_tools import crop_center_img
from ..utils.util import hide_uid
from ..utils.waves_api import waves_api
from ..utils.api.model import SlashDetail
from ..utils.database.models import WavesBind
from ..utils.resource.RESOURCE_PATH import PLAYER_PATH
from ..wutheringwaves_config import PREFIX, WutheringWavesConfig
from ..wutheringwaves_abyss.draw_slash_card import get_slash_data
from ..utils.image import (
    GREY, SPECIAL_GOLD, add_footer, get_waves_bg, get_qq_avatar, get_square_avatar,
)
from ..utils.fonts.waves_fonts import (
    waves_font_14, waves_font_16, waves_font_18, waves_font_20, waves_font_24,
    waves_font_30, waves_font_34, waves_font_40, waves_font_44,
)

rank_length = 20  # 排行长度
TEXT_PATH = Path(__file__).parent / "texture2d"
bar = Image.open(TEXT_PATH / "bar.png")
bar_width = bar.width
logo_img = Image.open(TEXT_PATH / "logo_small_2.png")
avatar_mask = Image.open(TEXT_PATH / "avatar_mask.png")


class EndlessRankInfo(BaseModel):
    qid: str  # qq id
    uid: str  # uid
    name: str  # 游戏昵称
    endless_score: int  # 无尽分数
    rank_level: str  # 等级 (S/A/B/C/D)
    half_list: List[dict] = []  # 半场信息
    account_level: int = 0  # 账号等级（保留以备将来使用）


async def get_local_slash_record(uid: str) -> Optional[dict]:
    """从本地JSON文件读取冥海记录（保留作为备用）"""
    try:
        path = PLAYER_PATH / uid / "slashData.json"
        if not path.exists(): return None
        async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
            data = json.loads(await f.read())
        # 查找第12层的数据
        for record in data:
            if record.get("challengeId") == 12: return record
        return None
    except Exception as e:
        logger.exception(f"[本地排行] 读取用户 {uid} 的本地记录失败: {e}")
        return None


async def get_db_slash_record(uid: str) -> Optional[dict]:
    """从数据库读取冥海记录"""
    try:
        from .models import SlashRecord, SlashRoleRecord
        # 获取最新的冥海记录
        slash_record = await SlashRecord.get_latest_slash_record_by_uid_and_level(uid, 12)
        if not slash_record: return None
        # 获取角色记录
        role_records = await SlashRoleRecord.get_slash_role_records(slash_record.id)
        # 构建队伍信息
        half_list = build_team_info(role_records, slash_record.slash_score)
        
        # 如果没有队伍信息，创建一个默认队伍
        if not half_list and role_records:
            all_roles = []
            for role in role_records:
                role_info = {
                    "roleId": role.char_id,
                    "iconUrl": "",
                    "chain": role.char_chain_count,
                    "chainName": f"{role.char_chain_count}链" if role.char_chain_count > 0 else "零链"
                }
                all_roles.append(role_info)
            half_list = [{
                "buffIcon": "", "buffName": "", "buffQuality": 1,
                "roleList": all_roles, "score": slash_record.slash_score,
                "charIds": [role.char_id for role in role_records]
            }]
        
        # 获取评级
        rank_level = ""
        if hasattr(slash_record, 'rank') and slash_record.rank:
            rank_level = slash_record.rank.lower()
        
        return {
            "score": slash_record.slash_score,
            "rank": rank_level,
            "halfList": half_list,
            "name": slash_record.nickname or hide_uid(uid)
        }
    except Exception as e:
        logger.exception(f"[数据库排行] 读取用户 {uid} 的数据库记录失败: {e}")
        return None


async def get_endless_rank_info_for_user(user: WavesBind, tokenLimitFlag: bool, wavesTokenUsersMap: dict) -> List[EndlessRankInfo]:
    """获取单个用户的无尽排行信息"""
    rank_info_list = []
    if not user.uid: return rank_info_list
    # 处理多个UID的情况
    uid_list = user.uid.split("_")
    for uid in uid_list:
        try:
            # 检查权限
            if tokenLimitFlag and (user.user_id, uid) not in wavesTokenUsersMap: continue
            # 优先使用数据库数据，如果没有则使用本地JSON数据
            db_record = await get_db_slash_record(uid)
            if db_record:
                endless_score = db_record.get("score", 0)
                rank_level = db_record.get("rank", "").lower()
                half_list = db_record.get("halfList", [])
            else:
                local_record = await get_local_slash_record(uid)
                if local_record:
                    endless_score = local_record.get("score", 0)
                    rank_level = local_record.get("rank", "").lower()
                    half_list = local_record.get("halfList", [])
                else: continue
            if endless_score == 0: continue
            
            # 使用与单个查询相同的评级逻辑，即使没有评级也显示
            # rank_level 可能为空字符串，这是正常的
            # 获取账号信息
            account_level = 0
            player_name = hide_uid(uid)  # 默认名字
            try:
                is_self_ck, ck = await waves_api.get_ck_result(uid, user.user_id, user.bot_id)
                if ck:
                    succ, account_info = await waves_api.get_base_info(uid, ck)
                    if succ and isinstance(account_info, dict):
                        account_level = account_info.get("level", 0)
                        player_name = account_info.get("name", player_name)
            except: pass
            # 处理角色信息
            processed_half_list = []
            for half in half_list:
                processed_half = half.copy()
                processed_role_list = []
                for role in half.get("roleList", []):
                    # 确保链数信息存在
                    if "chainName" not in role: role["chainName"] = "零链"
                    if "chain" not in role: role["chain"] = 0
                    processed_role_list.append(role)
                processed_half["roleList"] = processed_role_list
                processed_half_list.append(processed_half)
            # 创建排行信息
            rank_info = EndlessRankInfo(
                qid=user.user_id, uid=uid, name=player_name, endless_score=endless_score,
                rank_level=rank_level, half_list=processed_half_list, account_level=account_level,
            )
            rank_info_list.append(rank_info)
        except Exception as e:
            logger.exception(f"处理用户 {uid} 的无尽排行信息时出错: {e}")
            continue
    return rank_info_list


async def get_all_endless_rank_info_from_db(group_users: List[WavesBind], tokenLimitFlag: bool = False, wavesTokenUsersMap: dict = None) -> List[EndlessRankInfo]:
    """从数据库获取群内用户的无尽排行信息"""
    try:
        from .models import SlashRecord, SlashRoleRecord
        # 获取群内用户的UID列表，处理多UID情况
        group_uids = []
        for user in group_users:
            if user.uid:
                # 处理多个UID的情况（用下划线分隔）
                uids = user.uid.split("_")
                for uid in uids:
                    if uid and uid not in group_uids:
                        group_uids.append(uid)
        
        if not group_uids: 
            return []
            
        # 批量获取群内用户的第12层记录
        slash_records = await SlashRecord.get_slash_records_by_uids_and_level(group_uids, 12)
        
        # 按分数排序
        slash_records.sort(key=lambda x: x.slash_score, reverse=True)
        rank_info_list = []
        
        for record in slash_records:
            try:
                # 检查权限
                if tokenLimitFlag and (record.user_id, record.uid) not in wavesTokenUsersMap:
                    continue
                
                # 获取角色记录
                role_records = await SlashRoleRecord.get_slash_role_records(record.id)
                
                # 构建队伍信息
                half_list = build_team_info(role_records, record.slash_score)
                
                # 如果没有队伍信息，创建一个默认队伍
                if not half_list and role_records:
                    all_roles = []
                    for role in role_records:
                        role_info = {
                            "roleId": role.char_id,
                            "iconUrl": "",
                            "chain": role.char_chain_count,
                            "chainName": f"{role.char_chain_count}链" if role.char_chain_count > 0 else "零链"
                        }
                        all_roles.append(role_info)
                    half_list = [{
                        "buffIcon": "", "buffName": "", "buffQuality": 1,
                        "roleList": all_roles, "score": record.slash_score,
                        "charIds": [role.char_id for role in role_records]
                    }]
                
                # 获取评级
                rank_level = ""
                if hasattr(record, 'rank') and record.rank:
                    rank_level = record.rank.lower()
                
                # 创建排行信息
                rank_info = EndlessRankInfo(
                    qid=record.user_id, uid=record.uid, name=record.nickname or hide_uid(record.uid),
                    endless_score=record.slash_score, rank_level=rank_level, half_list=half_list, account_level=0,
                )
                rank_info_list.append(rank_info)
            except Exception as e:
                logger.exception(f"处理数据库记录 {record.id} 时出错: {e}")
                continue
        return rank_info_list
    except Exception as e:
        logger.exception(f"从数据库获取排行信息失败: {e}")
        logger.error(f"group_uids: {group_uids}")
        return []


async def get_all_endless_rank_info(users: List[WavesBind], tokenLimitFlag: bool, wavesTokenUsersMap: dict) -> List[EndlessRankInfo]:
    """获取群内用户的无尽排行信息"""
    # 从数据库获取群内用户数据
    db_rank_info = await get_all_endless_rank_info_from_db(users, tokenLimitFlag, wavesTokenUsersMap)
    if db_rank_info:
        return db_rank_info
    return []


async def get_waves_token_condition(ev):
    """获取群排行权限设置"""
    wavesTokenUsersMap = {}
    flag = False
    # 群组 不限制token
    WavesRankNoLimitGroup = WutheringWavesConfig.get_config("WavesRankNoLimitGroup").data
    if WavesRankNoLimitGroup and ev.group_id in WavesRankNoLimitGroup:
        return flag, wavesTokenUsersMap
    # 群组 自定义的
    WavesRankUseTokenGroup = WutheringWavesConfig.get_config("WavesRankUseTokenGroup").data
    # 全局 主人定义的
    RankUseToken = WutheringWavesConfig.get_config("RankUseToken").data
    if (WavesRankUseTokenGroup and ev.group_id in WavesRankUseTokenGroup) or RankUseToken:
        from ..utils.database.models import WavesUser
        wavesTokenUsers = await WavesUser.get_waves_all_user()
        wavesTokenUsersMap = {(w.user_id, w.uid): w.cookie for w in wavesTokenUsers}
        flag = True
    return flag, wavesTokenUsersMap


async def get_avatar(qid: str) -> Image.Image:
    """获取圆形用户头像"""
    try:
        # 获取QQ头像
        pic = await get_qq_avatar(qid, size=100)
        # 确保头像是正方形
        size = min(pic.size)
        pic = crop_center_img(pic, size, size)
        # 创建圆形遮罩
        mask = Image.new('L', (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        # 应用遮罩
        output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        output.paste(pic, (0, 0), mask)
        return output
    except Exception as e:
        logger.warning(f"获取用户头像失败: {e}")
        # 如果失败，返回默认方形头像
        return await get_square_avatar(1203)


async def _draw_team_info(bar_bg: Image.Image, roles: List[dict], score: int, start_x: int, center_y: int, team_name: str):
    """在排行条上绘制单个队伍的信息 (头像, 链数, 队伍名, 分数)"""
    bar_draw = ImageDraw.Draw(bar_bg)
    avatar_size = 48  # 放大头像
    avatar_gap = 4
    text_block_width = 60  # 左侧文字区域宽度
    # 绘制左侧的队伍名和分数
    bar_draw.text((start_x, center_y - 10), team_name, (255,255,255,200), waves_font_16, "lm")
    bar_draw.text((start_x, center_y + 12), str(score), "white", waves_font_18, "lm")
    # 异步获取所有角色头像
    avatar_tasks = [get_square_avatar(role["roleId"]) for role in roles[:3]]
    avatars = await asyncio.gather(*avatar_tasks)
    avatar_start_x = start_x + text_block_width
    for i, (role, char_avatar) in enumerate(zip(roles[:3], avatars)):
        try:
            char_avatar = char_avatar.resize((avatar_size, avatar_size), Image.LANCZOS)
            cx = avatar_start_x + i * (avatar_size + avatar_gap)
            cy = center_y - avatar_size // 2
            bar_bg.paste(char_avatar, (cx, cy), char_avatar)
            # 绘制链数
            chain_name = role.get("chainName", "零链")
            chain_num_str = chain_name.replace("零", "0").replace("一", "1").replace("二", "2").replace("三", "3").replace("四", "4").replace("五", "5").replace("六", "6").replace("链", "")
            chain_block_size = (18, 18)  # 缩小链数背景
            chain_block = Image.new("RGBA", chain_block_size, (0, 0, 0, 180))
            chain_block_draw = ImageDraw.Draw(chain_block)
            chain_block_draw.text((chain_block_size[0] // 2, chain_block_size[1] // 2 + 1), chain_num_str, "white", waves_font_14, "mm")
            # 粘贴到右下角
            paste_x = cx + avatar_size - chain_block_size[0]
            paste_y = cy + avatar_size - chain_block_size[1]
            bar_bg.alpha_composite(chain_block, (paste_x, paste_y))
        except Exception as e:
            logger.error(f"绘制角色信息时出错: {e}")


async def draw_endless_rank_img(bot: Bot, ev: Event) -> Union[str, bytes]:
    """绘制群无尽分数排行图片"""
    # 并行获取群用户数据和权限设置
    users_task = WavesBind.get_group_all_uid(ev.group_id)
    token_task = get_waves_token_condition(ev)
    
    users_result, token_result = await asyncio.gather(users_task, token_task, return_exceptions=True)
    
    # 处理群用户数据结果
    if isinstance(users_result, Exception):
        return f"获取群用户数据失败: {users_result}"
    users = users_result
    
    # 处理权限设置结果
    if isinstance(token_result, Exception):
        return f"获取权限设置失败: {token_result}"
    tokenLimitFlag, wavesTokenUsersMap = token_result
    
    if not users:
        msg = [f"[鸣潮] 群【{ev.group_id}】暂无用户数据", f"请使用【{PREFIX}刷新面板】并且【{PREFIX}无尽】后再使用此功能！"]
        if tokenLimitFlag: msg.append(f"当前排行开启了登录验证，请使用命令【{PREFIX}登录】登录后此功能！")
        return "\n".join(msg)
    
    rankInfoList = await get_all_endless_rank_info(list(users), tokenLimitFlag, wavesTokenUsersMap)
    if not rankInfoList:
        msg = [f"[鸣潮] 群【{ev.group_id}】暂无无尽挑战数据", f"请使用【{PREFIX}刷新面板】并且【{PREFIX}无尽】后再使用此功能！"]
        if tokenLimitFlag: msg.append(f"当前排行开启了登录验证，请使用命令【{PREFIX}登录】登录后此功能！")
        return "\n".join(msg)
    rankInfoList.sort(key=lambda i: i.endless_score, reverse=True)
    # 查找触发者的排名信息
    self_uid = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
    self_rank_info = None
    self_rank_index = -1
    
    if self_uid:
        for i, info in enumerate(rankInfoList):
            if info.uid == self_uid:
                self_rank_info = info
                self_rank_index = i
                break
    display_list = rankInfoList[:rank_length]
    has_extra_row = True
    total_rows = len(display_list) + 1
    img_width = 1050  # 图片宽度
    title_h = 200  # 标题区域高度
    header_h = 40  # 表头高度
    bar_h = 90  # 每一行条目的高度
    h = title_h + header_h + total_rows * bar_h + 80
    card_img = get_waves_bg(img_width, h, "bg3")
    card_img_draw = ImageDraw.Draw(card_img)
    # 绘制标题和统计信息
    logo_copy = logo_img.copy()
    logo_copy.thumbnail((150, 150), Image.LANCZOS)
    card_img.alpha_composite(logo_copy, dest=(50, 55))
    card_img_draw.text((img_width // 2, 80), "冥歌海墟无尽排行", "white", waves_font_40, "mm")
    card_img_draw.text((img_width // 2, 125), "数据来源: 当前群聊", SPECIAL_GOLD, waves_font_20, "mm")
    total_players = len(rankInfoList)
    avg_score = sum(i.endless_score for i in rankInfoList) // total_players if total_players > 0 else 0
    max_score_info = rankInfoList[0] if rankInfoList else None
    center_stat_y = 165
    stat_font = waves_font_18
    stat_color = (255,255,255,200)
    max_score_str = f"最高分: {max_score_info.endless_score} (by {max_score_info.name})" if max_score_info else "最高分: N/A"
    avg_score_str = f"平均分: {avg_score}"
    max_w = card_img_draw.textlength(max_score_str, stat_font)
    avg_w = card_img_draw.textlength(avg_score_str, stat_font)
    gap = 80
    total_w = max_w + avg_w + gap
    start_x_stats = (img_width - total_w) // 2
    card_img_draw.text((start_x_stats, center_stat_y), max_score_str, stat_color, stat_font, "lm")
    card_img_draw.text((start_x_stats + max_w + gap, center_stat_y), avg_score_str, stat_color, stat_font, "lm")
    # 绘制列表头
    header_y = title_h
    centered_x = (img_width - bar_width) // 2
    header_font = waves_font_16
    header_color = (255, 255, 255, 180)
    card_img_draw.text((centered_x + 45, header_y + header_h/2), "排名", header_color, header_font, "mm")
    card_img_draw.text((centered_x + 190, header_y + header_h/2), "玩家信息", header_color, header_font, "mm")
    card_img_draw.text((centered_x + 520, header_y + header_h/2), "队伍阵容", header_color, header_font, "mm")
    card_img_draw.text((centered_x + 830, header_y + header_h/2), "总评分", header_color, header_font, "mm")
    card_img_draw.text((centered_x + 930, header_y + header_h/2), "评级", header_color, header_font, "mm")
    # 并行获取榜单用户头像和触发者头像
    display_avatar_tasks = [get_avatar(rank.qid) for rank in display_list]
    
    # 只有当触发者有排行信息时才获取头像
    if self_rank_info and hasattr(self_rank_info, 'qid'):
        self_avatar_task = get_avatar(self_rank_info.qid)
        all_avatar_tasks = display_avatar_tasks + [self_avatar_task]
        all_avatars = await asyncio.gather(*all_avatar_tasks, return_exceptions=True)
        user_avatars = all_avatars[:len(display_list)]
        self_avatar = all_avatars[-1] if not isinstance(all_avatars[-1], Exception) else None
    else:
        user_avatars = await asyncio.gather(*display_avatar_tasks, return_exceptions=True)
        self_avatar = None
    
    # 处理头像获取失败的情况
    user_avatars = [avatar if not isinstance(avatar, Exception) else None for avatar in user_avatars]
    # 绘制榜单
    for index, (rank, user_avatar) in enumerate(zip(display_list, user_avatars)):
        bar_bg = bar.copy().resize((bar_width, bar_h))
        bar_draw = ImageDraw.Draw(bar_bg)
        y_pos = title_h + header_h + index * bar_h
        center_y = bar_h // 2
        # 绘制排名
        rank_color = (100, 100, 100, 180)
        if index == 0: rank_color = (255, 215, 0, 220)
        elif index == 1: rank_color = (192, 192, 192, 220)
        elif index == 2: rank_color = (205, 127, 50, 220)
        bar_draw.text((45, center_y), str(index + 1), rank_color, waves_font_30, "mm")
        # 绘制玩家信息
        player_info_x = 90
        avatar_size = 64
        if user_avatar:
            user_avatar = user_avatar.resize((avatar_size, avatar_size), Image.LANCZOS)
            bar_bg.paste(user_avatar, (player_info_x, center_y - avatar_size // 2), user_avatar)
        else:
            # 如果头像获取失败，绘制一个默认的圆形背景
            default_avatar = Image.new("RGBA", (avatar_size, avatar_size), (100, 100, 100, 180))
            mask = Image.new('L', (avatar_size, avatar_size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
            bar_bg.paste(default_avatar, (player_info_x, center_y - avatar_size // 2), mask)
        bar_draw.text((player_info_x + avatar_size + 10, center_y - 10), rank.name, "white", waves_font_20, "lm")
        bar_draw.text((player_info_x + avatar_size + 10, center_y + 15), f"UID:{hide_uid(rank.uid)}", (255,255,255,180), waves_font_16, "lm")
        # 绘制队伍信息
        if rank.half_list:
            team_block_width = 60 + 3 * 48 + 2 * 4
            team_gap = 20
            total_teams_width = 2 * team_block_width + team_gap
            column_width = 400  # 队伍阵容列的大致宽度
            teams_start_x = 340 + (column_width - total_teams_width) // 2
            team_tasks = []
            if len(rank.half_list) > 0:
                team_tasks.append(_draw_team_info(bar_bg, rank.half_list[0]["roleList"], rank.half_list[0]["score"], teams_start_x, center_y, "队伍一"))
            if len(rank.half_list) > 1:
                team_tasks.append(_draw_team_info(bar_bg, rank.half_list[1]["roleList"], rank.half_list[1]["score"], teams_start_x + team_block_width + team_gap, center_y, "队伍二"))
            if team_tasks: 
                await asyncio.gather(*team_tasks, return_exceptions=True)
        # 绘制总评分
        bar_draw.text((830, center_y), str(rank.endless_score), SPECIAL_GOLD, waves_font_34, "mm")
        # 绘制评级
        if rank.rank_level:  # 只有当有评级时才显示
            try:
                score_bar_img = Image.open(TEXT_PATH / f"score_{rank.rank_level}.png").resize((50, 50), Image.LANCZOS)
                bar_bg.alpha_composite(score_bar_img, (930 - 25, center_y - 25))
            except FileNotFoundError:
                bar_draw.text((930, center_y), rank.rank_level.upper(), SPECIAL_GOLD, waves_font_40, "mm")
        else:
            # 没有评级时显示 "-"
            bar_draw.text((930, center_y), "-", GREY, waves_font_40, "mm")
        card_img.paste(bar_bg, (centered_x, y_pos), bar_bg)
    # 绘制触发者自己的排名行
    if has_extra_row and self_rank_info and self_avatar:
        bar_bg = bar.copy().resize((bar_width, bar_h))
        bar_draw = ImageDraw.Draw(bar_bg)
        y_pos = title_h + header_h + len(display_list) * bar_h
        center_y = bar_h // 2
        # 绘制真实排名
        rank_str = str(self_rank_index + 1)
        if self_rank_index + 1 > 999: rank_str = "999+"
        bar_draw.text((45, center_y), rank_str, SPECIAL_GOLD, waves_font_30, "mm")
        # 绘制玩家信息
        player_info_x = 90
        avatar_size = 64
        if self_avatar:
            user_avatar = self_avatar.resize((avatar_size, avatar_size), Image.LANCZOS)
            bar_bg.paste(user_avatar, (player_info_x, center_y - avatar_size // 2), user_avatar)
        else:
            # 如果头像获取失败，绘制一个默认的圆形背景
            default_avatar = Image.new("RGBA", (avatar_size, avatar_size), (100, 100, 100, 180))
            mask = Image.new('L', (avatar_size, avatar_size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
            bar_bg.paste(default_avatar, (player_info_x, center_y - avatar_size // 2), mask)
        bar_draw.text((player_info_x + avatar_size + 10, center_y - 10), self_rank_info.name, "white", waves_font_20, "lm")
        bar_draw.text((player_info_x + avatar_size + 10, center_y + 15), f"UID:{hide_uid(self_rank_info.uid)}", (255,255,255,180), waves_font_16, "lm")
        # 绘制队伍信息
        if self_rank_info.half_list:
            team_block_width = 60 + 3 * 48 + 2 * 4
            team_gap = 20
            total_teams_width = 2 * team_block_width + team_gap
            column_width = 400
            teams_start_x = 340 + (column_width - total_teams_width) // 2
            team_tasks = []
            if len(self_rank_info.half_list) > 0:
                team_tasks.append(_draw_team_info(bar_bg, self_rank_info.half_list[0]["roleList"], self_rank_info.half_list[0]["score"], teams_start_x, center_y, "队伍一"))
            if len(self_rank_info.half_list) > 1:
                team_tasks.append(_draw_team_info(bar_bg, self_rank_info.half_list[1]["roleList"], self_rank_info.half_list[1]["score"], teams_start_x + team_block_width + team_gap, center_y, "队伍二"))
            if team_tasks: 
                await asyncio.gather(*team_tasks, return_exceptions=True)
        # 绘制总评分
        bar_draw.text((830, center_y), str(self_rank_info.endless_score), SPECIAL_GOLD, waves_font_34, "mm")
        # 绘制评级
        if self_rank_info.rank_level:  # 只有当有评级时才显示
            try:
                score_bar_img = Image.open(TEXT_PATH / f"score_{self_rank_info.rank_level}.png").resize((50, 50), Image.LANCZOS)
                bar_bg.alpha_composite(score_bar_img, (930 - 25, center_y - 25))
            except FileNotFoundError:
                bar_draw.text((930, center_y), self_rank_info.rank_level.upper(), SPECIAL_GOLD, waves_font_40, "mm")
        else:
            # 没有评级时显示 "-"
            bar_draw.text((930, center_y), "-", GREY, waves_font_40, "mm")
        card_img.paste(bar_bg, (centered_x, y_pos), bar_bg)
    # 添加页脚
    card_img = add_footer(card_img)
    return await convert_img(card_img)


def build_team_info(role_records, total_score):
    """构建队伍信息，返回包含真实队伍分数的半场信息"""
    team_0_roles = []
    team_1_roles = []
    team_0_score = 0
    team_1_score = 0
    
    for role in role_records:
        role_info = {
            "roleId": role.char_id,
            "iconUrl": "",
            "chain": role.char_chain_count,
            "chainName": f"{role.char_chain_count}链" if role.char_chain_count > 0 else "零链"
        }
        if role.team_index == 0:
            team_0_roles.append(role_info)
            if hasattr(role, 'team_score') and role.team_score > 0:
                team_0_score = role.team_score
        else:
            team_1_roles.append(role_info)
            if hasattr(role, 'team_score') and role.team_score > 0:
                team_1_score = role.team_score
    
    # 构建半场信息列表
    half_list = []
    if team_0_roles:
        score = team_0_score if team_0_score > 0 else total_score // 2
        half_list.append({
            "buffIcon": "", "buffName": "", "buffQuality": 1,
            "roleList": team_0_roles, "score": score,
            "charIds": [role['roleId'] for role in team_0_roles]
        })
    if team_1_roles:
        score = team_1_score if team_1_score > 0 else total_score // 2
        half_list.append({
            "buffIcon": "", "buffName": "", "buffQuality": 1,
            "roleList": team_1_roles, "score": score,
            "charIds": [role['roleId'] for role in team_1_roles]
        })
    
    return half_list
