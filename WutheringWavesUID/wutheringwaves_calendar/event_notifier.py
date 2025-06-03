import asyncio
import random
from datetime import datetime, timedelta
from typing import List

from gsuid_core.aps import scheduler
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.subscribe import gs_subscribe
from ..wutheringwaves_config import WutheringWavesConfig
from gsuid_core.gss import gss
from .calendar_model import VersionActivity
from ..utils.api.requests import Wiki

wiki = Wiki()
task_name = "鸣潮活动提醒"
threshold = WutheringWavesConfig.get_config("ReminderThresholdHours").data
async def check_events():
    """检查所有活动并发送即将结束的活动通知"""
    if not WutheringWavesConfig.get_config("CalendarReminderOpen").data:
        return
        
    wiki_home = await wiki.get_wiki_home()
    if wiki_home["code"] != 200:
        return

    now = datetime.now()
    side_modules = wiki_home.get("data", {}).get("contentJson", {}).get("sideModules", [])
    
    for side_module in side_modules:
        if side_module["title"] == "版本活动":
            content = VersionActivity(**side_module)
            await process_events(content.content, now)

# 记录最后提醒时间的字典
last_reminder_time = {}

def get_periodic_events(now: datetime):
    """获取周期性活动信息"""
    # 逆境深塔 (28天周期)
    tower_start = datetime(2025, 2, 3, 4, 0)
    tower_cycle = tower_start + timedelta(days=28 * ((now - tower_start).days // 28))
    tower_end = tower_cycle + timedelta(days=28)
    
    # 冥歌海墟 (28天周期，与逆境深塔错开2周)
    shenhai_start = datetime(2025, 4, 14, 4, 0)
    shenhai_cycle = shenhai_start + timedelta(days=28 * ((now - shenhai_start).days // 28))
    shenhai_end = shenhai_cycle + timedelta(days=28)
    
    # 千道门扉的异想 (每周一4:00)
    qianmen_start = datetime(2025, 4, 7, 4, 0)  # 假设4月7日是第一个周一
    qianmen_cycle = qianmen_start + timedelta(days=7 * ((now - qianmen_start).days // 7))
    qianmen_end = qianmen_cycle + timedelta(days=7)
    
    
    return [
        {
            "title": "逆境深塔",
            "countDown": {
                "dateRange": [
                    tower_cycle.strftime("%Y-%m-%d %H:%M"),
                    tower_end.strftime("%Y-%m-%d %H:%M")
                ]
            }
        },
        {
            "title": "冥歌海墟", 
            "countDown": {
                "dateRange": [
                    shenhai_cycle.strftime("%Y-%m-%d %H:%M"),
                    shenhai_end.strftime("%Y-%m-%d %H:%M")
                ]
            }
        },
        {
            "title": "【周常】千道门扉的异想",
            "countDown": {
                "dateRange": [
                    (qianmen_end - timedelta(days=7)).strftime("%Y-%m-%d %H:%M"),
                    qianmen_end.strftime("%Y-%m-%d %H:%M")
                ]
            }
        },
        {
            "title": "【周本】战歌重奏",
            "countDown": {
                "dateRange": [
                    (qianmen_end - timedelta(days=7)).strftime("%Y-%m-%d %H:%M"),
                    qianmen_end.strftime("%Y-%m-%d %H:%M")
                ]
            }
        }
    ]

async def process_events(events: List, now: datetime):
    """处理活动列表，对剩余1天结束的活动发送通知"""
    sent_events = set()  # 记录已发送提醒的活动
    events_to_notify = {}  # 按结束时间分组的活动
    
    # 合并API获取的活动和周期性活动
    periodic_events = get_periodic_events(now)
    all_events = events + periodic_events
    
    logger.debug(f"共获取到 {len(all_events)} 个活动")
    
    # 先收集所有需要提醒的活动
    for idx, event in enumerate(all_events):
        # 处理字典和VersionActivity两种类型
        count_down = event.get('countDown') if isinstance(event, dict) else getattr(event, 'countDown', None)
        if not count_down:
            title = event.get('title') if isinstance(event, dict) else getattr(event, 'title', '未知活动')
            logger.debug(f"[活动调试] 活动 {idx+1}: {title} 无倒计时信息")
            continue
            
        date_range = count_down.get('dateRange') if isinstance(count_down, dict) else getattr(count_down, 'dateRange', None)
        end_time = datetime.strptime(date_range[1], "%Y-%m-%d %H:%M")
        time_left = end_time - now
        
        title = event.get('title') if isinstance(event, dict) else getattr(event, 'title', '未知活动')
        logger.debug(
            f"[活动调试] 活动 {idx+1}: {title}\n"
            f"结束时间: {end_time}\n"
            f"剩余时间: {time_left}\n"
            f"是否小于阈值: {time_left <= timedelta(hours=threshold)}"
        )
        
        # 检查活动是否已结束
        if time_left <= timedelta(0):
            logger.debug(f"[活动调试] 活动 {title} 已结束")
            continue
            
        # 如果活动剩余时间小于配置的阈值且未结束
        if time_left <= timedelta(hours=threshold):
            interval_hours = WutheringWavesConfig.get_config("FinalReminderInterval").data
            event_key = f"{title}_{end_time}"
            
            # 检查是否需要发送提醒
            if (event_key not in last_reminder_time or 
                (now - last_reminder_time[event_key]) >= timedelta(hours=interval_hours)):
                
                # 确保不重复发送相同活动的提醒
                if event_key not in sent_events:
                    logger.debug(f"[活动调试] 符合推送条件: {title}")
                    # 按结束时间分组活动
                    if end_time not in events_to_notify:
                        events_to_notify[end_time] = []
                    events_to_notify[end_time].append(title)
                    last_reminder_time[event_key] = now
                    sent_events.add(event_key)

    # 发送合并后的活动提醒
    for end_time, events in events_to_notify.items():
        await send_event_notification(events, end_time)
        logger.info(f"[活动提醒] 已发送{len(events)}个活动结束前提醒")

async def send_event_notification(events: List[str], end_time: datetime):
    """向订阅用户发送活动即将结束通知"""
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
        hours = (time_left.seconds // 3600) % 24
        time_str = f"{days}天{hours}小时"
    
    event_list = "\n".join(events)
    message = f"以下活动即将在{time_str}后结束：\n{event_list}\n请及时完成活动内容！"
    subscribes = await gs_subscribe.get_subscribe(task_name)
    
    if not subscribes:
        logger.info("[活动提醒] 暂无订阅用户")
        return

    use_forward = WutheringWavesConfig.get_config("CalendarReminderForward").data
    for subscribe in subscribes:
        try:
            if use_forward:
                from gsuid_core.segment import MessageSegment
                
                # 构建纯文本转发消息
                im = ["【活动提醒】"]
                if time_left <= timedelta(hours=24):
                    hours = time_left.seconds // 3600
                    minutes = (time_left.seconds % 3600) // 60
                    time_str = f"{hours}小时{minutes}分钟"
                else:
                    days = time_left.days
                    hours = (time_left.seconds // 3600) % 24
                    time_str = f"{days}天{hours}小时"
                
                im.append(f"以下活动将在{time_str}后结束：")
                im.extend(f"\n\n{events}")  # 直接添加活动名称列表
                im.append("\n\n请及时完成活动内容！")
                
                await subscribe.send(MessageSegment.node(im))
            else:
                await subscribe.send(message)
            await asyncio.sleep(random.uniform(1, 3))
        except Exception as e:
            logger.exception(f"[活动提醒] 推送失败: {e}")

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
