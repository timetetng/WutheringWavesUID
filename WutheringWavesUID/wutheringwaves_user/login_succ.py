from typing import Any, List

from gsuid_core.bot import Bot
from gsuid_core.models import Event

from ..utils.button import WavesButton
from ..utils.database.models import WavesUser

login_succ = "[鸣潮] 特征码[{}]登录成功! "


async def login_success_msg(bot: Bot, ev: Event, waves_user: WavesUser):
    buttons: List[Any] = [
        WavesButton("体力", "mr"),
        WavesButton("刷新面板", "刷新面板"),
        WavesButton("深塔", "深塔"),
        WavesButton("冥歌海墟", "冥海"),
    ]
    from ..wutheringwaves_charinfo.draw_refresh_char_card import (
        draw_refresh_char_detail_img,
    )
    # 先发送登录成功消息
    await bot.send(login_succ.format(waves_user.uid))
    msg = await draw_refresh_char_detail_img(
        bot, ev, waves_user.user_id, waves_user.uid, buttons
    )
    if isinstance(msg, bytes):
        # 如果是图片，再发送图片消息和按钮
        return await bot.send_option(msg, buttons)
    else:
        # 如果是文本消息，则不发送额外的消息
        return msg
