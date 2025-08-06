import re
from typing import Any, List

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event

from ..utils.at_help import ruser_id
from ..utils.hint import error_reply
from ..utils.button import WavesButton
from ..utils.database.models import WavesBind
from .models import SlashRecord, SlashRoleRecord
from ..utils.error_reply import WAVES_CODE_103
from .draw_slash_query_card import draw_slash_query_img
from .draw_endless_rank_card import draw_endless_rank_img

sv_waves_endless_rank = SV("ww无尽排行")
sv_waves_slash_query = SV("ww冥海查询")


@sv_waves_endless_rank.on_regex("^无尽(?:排行|排名)$", block=True)
async def send_endless_rank_card(bot: Bot, ev: Event):
    if not ev.group_id:
        return await bot.send("请在群聊中使用")

    im = await draw_endless_rank_img(bot, ev)

    if isinstance(im, str):
        at_sender = True if ev.group_id else False
        await bot.send(im, at_sender)
    if isinstance(im, bytes):
        await bot.send(im)


@sv_waves_slash_query.on_command(
    (
        "冥海",
        "mh",
        "海墟",
        "冥歌海墟",
        "查询冥海",
        "查询无尽",
        "查询海墟",
        "无尽",
        "无尽深渊",
        "禁忌",
        "禁忌海域",
        "再生海域",
    ),
    block=True,
)
async def send_waves_slash_query_info(bot: Bot, ev: Event):
    user_id = ruser_id(ev)
    uid = await WavesBind.get_uid_by_game(user_id, ev.bot_id)
    if not uid:
        return await bot.send(error_reply(WAVES_CODE_103))

    im = await draw_slash_query_img(ev, uid, user_id)
    if isinstance(im, str):
        at_sender = True if ev.group_id else False
        return await bot.send(im, at_sender)
    else:
        buttons: List[Any] = [
            WavesButton("冥歌海墟", "冥海"),
            WavesButton("冥海前6层", "禁忌"),
            WavesButton("冥海11层", "冥海11"),
            WavesButton("冥海12层", "无尽"),
        ]
        return await bot.send_option(im, buttons)
