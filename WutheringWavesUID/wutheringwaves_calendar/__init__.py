from typing import Any, List

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..utils.button import WavesButton
from .draw_calendar_card import draw_calendar_img

from gsuid_core.logger import logger
from gsuid_core.subscribe import gs_subscribe
from ..wutheringwaves_config import WutheringWavesConfig
from .event_notifier import start_notifier, task_name

sv_waves_calendar = SV("waves日历")
sv_calendar_reminder = SV("订阅活动提醒", pm=3)

@sv_waves_calendar.on_fullmatch((f"个人日历", f"日历"), block=True)
async def send_waves_calendar_pic(bot: Bot, ev: Event):
    uid = ""
    im = await draw_calendar_img(ev, uid)
    if isinstance(im, str):
        return await bot.send(im)
    else:
        buttons: List[Any] = [
            WavesButton("深塔", "深塔"),
            WavesButton("冥海", "冥海"),
        ]
        return await bot.send_option(im, buttons)


@sv_calendar_reminder.on_fullmatch("订阅活动提醒")
async def sub_calendar_reminder(bot: Bot, ev: Event):
    """订阅活动提醒"""
    if not WutheringWavesConfig.get_config("CalendarReminderOpen").data:
        return await bot.send("活动提醒功能已关闭")
        
    if ev.group_id is None:
        return await bot.send("请在群聊中订阅")

    data = await gs_subscribe.get_subscribe(task_name)
    if data:
        for subscribe in data:
            if subscribe.group_id == ev.group_id:
                return await bot.send("已经订阅了活动提醒！")

    await gs_subscribe.add_subscribe(
        "session",
        task_name=task_name,
        event=ev,
        extra_message="",
    )
    await bot.send("成功订阅活动提醒!")

@sv_calendar_reminder.on_fullmatch(("取消活动提醒", "退订活动提醒"))
async def unsub_calendar_reminder(bot: Bot, ev: Event):
    """取消订阅活动提醒"""
    if ev.group_id is None:
        return await bot.send("请在群聊中取消订阅")

    data = await gs_subscribe.get_subscribe(task_name)
    if data:
        for subscribe in data:
            if subscribe.group_id == ev.group_id:
                await gs_subscribe.delete_subscribe("session", task_name, ev)
                return await bot.send("成功取消订阅活动提醒!")
    
    return await bot.send("未曾订阅活动提醒！")