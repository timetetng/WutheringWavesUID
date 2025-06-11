# 统一将所有 import 放在文件顶部
import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any

from gsuid_core.aps import scheduler
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.subscribe import gs_subscribe
from gsuid_core.segment import MessageSegment # 将此 import 移至顶部
from ..wutheringwaves_config import WutheringWavesConfig
from gsuid_core.gss import gss
from .calendar_model import VersionActivity
from ..utils.waves_api import waves_api

task_name = "鸣潮活动提醒"
threshold = WutheringWavesConfig.get_config("ReminderThresholdHours").data
last_reminder_time = {}

async def check_events():
    # ... 此函数保持不变 ...
    if not WutheringWavesConfig.get_config("CalendarReminderOpen").data:
        return
    
    wiki_home = await waves_api.get_wiki_home()
    if wiki_home["code"] != 200:
        logger.warning(f"[{task_name}] 获取维基数据失败: {wiki_home}")
        return

    now = datetime.now()
    all_api_events: List[Dict[str, Any]] = []
    side_modules = wiki_home.get("data", {}).get("contentJson", {}).get("sideModules", [])
    
    for side_module in side_modules:
        title = side_module.get("title")
        if title == "版本活动":
            content_items = side_module.get("content", [])
            all_api_events.extend(content_items)
        elif title in ["角色活动唤取", "武器活动唤取"]:
            tabs = side_module.get("content", {}).get("tabs", [])
            for tab in tabs:
                if "countDown" in tab and "dateRange" in tab["countDown"]:
                    event_data = {"title": f'{title}: {tab.get("name", "未知")}', "countDown": {"dateRange": tab["countDown"]["dateRange"]}}
                    all_api_events.append(event_data)
    await process_events(all_api_events, now)


def get_periodic_events(now: datetime) -> List[Dict[str, Any]]:
    # ... 此函数保持不变 ...
    events = []
    tower_start_time = datetime(2025, 2, 3, 3, 59)
    tower_date_range = timedelta(days=28)
    if now >= tower_start_time:
        tower_elapsed_time = now - tower_start_time
        tower_period_index = tower_elapsed_time // tower_date_range
        tower_current_start = tower_start_time + tower_period_index * tower_date_range
        tower_current_end = tower_current_start + tower_date_range
        events.append({"title": "逆境深塔", "countDown": {"dateRange": [tower_current_start.strftime("%Y-%m-%d %H:%M"), tower_current_end.strftime("%Y-%m-%d %H:%M")]}})
    
    shenhai_start_time = datetime(2025, 3, 17, 3, 59)
    shenhai_date_range = timedelta(days=28)
    if now >= shenhai_start_time:
        shenhai_elapsed_time = now - shenhai_start_time
        shenhai_period_index = shenhai_elapsed_time // shenhai_date_range
        shenhai_current_start = shenhai_start_time + shenhai_period_index * shenhai_date_range
        shenhai_current_end = shenhai_current_start + shenhai_date_range
        events.append({"title": "冥歌海墟", "countDown": {"dateRange": [shenhai_current_start.strftime("%Y-%m-%d %H:%M"), shenhai_current_end.strftime("%Y-%m-%d %H:%M")]}})

    today = now.replace(hour=3, minute=59, second=0, microsecond=0)
    weekly_reset_time = today - timedelta(days=today.weekday())
    if now.weekday() == 0 and now.hour < 3:
        weekly_reset_time -= timedelta(days=7)
    weekly_start_time = weekly_reset_time
    weekly_end_time = weekly_reset_time + timedelta(days=7)
    weekly_format = {"countDown": {"dateRange": [weekly_start_time.strftime("%Y-%m-%d %H:%M"), weekly_end_time.strftime("%Y-%m-%d %H:%M")]}}
    events.append({"title": "【周常】千道门扉的异想", **weekly_format})
    events.append({"title": "【周本】战歌重奏", **weekly_format})
    return events


async def process_events(events: List, now: datetime):
    # ... 此函数保持不变 ...
    sent_events = set()
    events_to_notify = {}
    periodic_events = get_periodic_events(now)
    all_events = events + periodic_events
    logger.debug(f"共获取到 {len(all_events)} 个活动")
    
    for idx, event in enumerate(all_events):
        is_dict = isinstance(event, dict)
        count_down_data = event.get('countDown') if is_dict else getattr(event, 'countDown', None)
        if not isinstance(count_down_data, dict) and count_down_data:
             count_down_data = count_down_data.model_dump()
        if not count_down_data: continue
        date_range = count_down_data.get('dateRange')
        if not date_range or len(date_range) < 2: continue
        title = event.get('title') if is_dict else getattr(event, 'title', '未知活动')
        end_time = datetime.strptime(date_range[1], "%Y-%m-%d %H:%M")
        time_left = end_time - now
        if time_left <= timedelta(0): continue
        if time_left <= timedelta(hours=threshold):
            interval_hours = WutheringWavesConfig.get_config("FinalReminderInterval").data
            event_key = f"{title}_{end_time}"
            if (event_key not in last_reminder_time or (now - last_reminder_time.get(event_key, now)) >= timedelta(hours=interval_hours)):
                if event_key not in sent_events:
                    logger.debug(f"[活动调试] 符合推送条件: {title}")
                    if end_time not in events_to_notify:
                        events_to_notify[end_time] = []
                    events_to_notify[end_time].append(title)
                    last_reminder_time[event_key] = now
                    sent_events.add(event_key)

    for end_time, event_titles in events_to_notify.items():
        await send_event_notification(event_titles, end_time)
        logger.info(f"[活动提醒] 已发送{len(event_titles)}个活动结束前提醒")

# 【全新修改的函数】
async def send_event_notification(events: List[str], end_time: datetime):
    """向订阅用户发送结构化的活动即将结束通知"""
    time_left = end_time - datetime.now()
    if time_left <= timedelta(0):
        logger.warning(f"尝试发送已结束活动提醒: {events}")
        return
            
    if time_left <= timedelta(hours=24):
        hours = time_left.seconds // 3600
        minutes = (time_left.seconds % 3600) // 60
        time_str = f"{hours}小时{minutes}分钟"
    else:
        days = time_left.days
        hours = time_left.seconds // 3600
        time_str = f"{days}天{hours}小时"
    
    event_list_str = "\n- ".join(events)
    
    formatted_message = f"""【鸣潮活动提醒】

以下活动将在约 {time_str} 后结束，请漂泊者注意及时完成：

- {event_list_str}

祝您游戏愉快！
"""

    subscribes = await gs_subscribe.get_subscribe(task_name)
    if not subscribes:
        logger.info(f"[{task_name}] 暂无订阅用户")
        return

    message_node_list = [formatted_message]

    for subscribe in subscribes:
        try:
            await subscribe.send(MessageSegment.node(message_node_list))
            await asyncio.sleep(random.uniform(1, 3))
        except Exception as e:
            logger.exception(f"[{task_name}] 推送失败: {e}")

# daily_check 和 start_notifier 保持不变
# ...
@scheduler.scheduled_job(
    "interval", 
    minutes=WutheringWavesConfig.get_config("CalendarReminderCheckInterval").data
)
async def daily_check():
    """定时活动检查任务"""
    if not WutheringWavesConfig.get_config("CalendarReminderOpen").data:
        return
        
    logger.info("[活动提醒] 开始检查活动结束时间...")
    await check_events()
    logger.info("[活动提醒] 检查完成")

def start_notifier():
    """启动活动通知服务"""
    if WutheringWavesConfig.get_config("CalendarReminderOpen").data:
        logger.info("[活动提醒] 活动提醒服务已启动")
