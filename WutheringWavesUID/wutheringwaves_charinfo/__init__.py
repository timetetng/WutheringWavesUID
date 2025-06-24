import re

from PIL import Image

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV
from gsuid_core.utils.image.convert import convert_img

from ..utils.at_help import is_valid_at, ruser_id
from ..utils.database.models import WavesBind
from ..utils.error_reply import WAVES_CODE_103
from ..utils.hint import error_reply
from ..utils.name_convert import char_name_to_char_id
from ..utils.resource.constant import SPECIAL_CHAR
from .draw_char_card import draw_char_detail_img, draw_char_score_img
from .upload_card import (
    compress_all_custom_card,
    delete_all_custom_card,
    delete_custom_card,
    get_custom_card_list,
    upload_custom_card,
)

from .upload_mr_card import (
    delete_all_custom_mr_card,
    delete_custom_mr_card,
    get_custom_mr_card_list,
    upload_custom_mr_card,
)
import json 
from ..utils.resource.RESOURCE_PATH import CUSTOM_CHAR_ALIAS_PATH

waves_new_get_char_info = SV("waves新获取面板", priority=3)
waves_new_get_one_char_info = SV("waves新获取单个角色面板", priority=3)
waves_new_char_detail = SV("waves新角色面板", priority=4)
waves_char_detail = SV("waves角色面板", priority=5)
waves_upload_char = SV("waves上传面板图", priority=5, pm=1)
waves_char_card_list = SV("waves面板图列表", priority=5, pm=1)
waves_delete_char_card = SV("waves删除面板图", priority=5, pm=1)
waves_delete_all_card = SV("waves删除全部面板图", priority=5, pm=1)
waves_compress_card = SV("waves面板图压缩", priority=5, pm=1)

waves_upload_mr_char = SV("waves上传体力背景图", priority=5, pm=1)
waves_mr_char_card_list = SV("waves体力背景图列表", priority=5, pm=1)
waves_delete_mr_char_card = SV("waves删除体力背景图", priority=5, pm=1)
waves_delete_all_mr_card = SV("waves删除全部体力背景图", priority=5, pm=1)
waves_char_alias = SV("waves角色别名", priority=5, pm=5)




# 插件命令触发器
@waves_char_alias.on_keyword(("别名",))
async def get_char_aliases(bot: Bot, ev: Event):
    """
    响应包含 "别名" 关键词的消息，查询角色别名并返回。
    """
    # 提取消息中的角色名
    text = ev.raw_text  # 直接从 ev.raw_text 获取消息内容
    parts = text.split("别名")
    if len(parts) != 2:
        await bot.send(ev, "呜呜呜，消息格式好像不太对劲呢！")  # 消息格式不正确，直接返回
        return
    char_name = parts[0].strip()  # 提取角色名并去除首尾空格
    # 如果角色名以 `ww` 或 `mc` 开头，就去掉
    if char_name and char_name.startswith(("ww","kt")):
        char_name = char_name[2:]
    aliases = get_aliases(char_name, str(CUSTOM_CHAR_ALIAS_PATH))  # 调用别名查询函数
    if aliases:
        reply_message = f"\"{char_name}\"的别名有：{', '.join(aliases)}"
        await bot.send(reply_message)
    else:
        await bot.send(f"哎呀，找不到 {char_name} 的别名呢！请输入正确的角色名")
def get_aliases(character_name, alias_file):
    """
    提取某个角色的所有别名。
    Args:
        character_name (str): 角色名或别名。
        alias_file (str): 别名文件的路径。
    Returns:
        list: 包含所有别名的列表，如果找不到角色，则返回 None。
    """
    try:
        with open(alias_file, 'r', encoding='utf-8') as f:
            alias_data = json.load(f)
    except FileNotFoundError:
        print(f"呜呜呜，找不到文件：{alias_file} 呢！")
        return None
    except json.JSONDecodeError:
        print(f"文件 {alias_file} 的格式好像不太对劲，菲比看不懂呢！")
        return None
    for char, aliases in alias_data.items():
        if character_name in aliases:
            return aliases
    # 如果没找到，也可能是角色名本身就是键
    if character_name in alias_data:
        return alias_data[character_name]
    print(f"哎呀，找不到 {character_name} 的别名呢！")
    return None


@waves_new_get_char_info.on_fullmatch(
    (
        "刷新面板",
        "刷新面包",
        "更新面板",
        "更新面包",
        "强制刷新",
        "面板刷新",
        "面包刷新",
        "面板更新",
        "面板",
        "面包",
    ),
    block=True,
)
async def send_card_info(bot: Bot, ev: Event):
    user_id = ruser_id(ev)

    uid = await WavesBind.get_uid_by_game(user_id, ev.bot_id)
    if not uid:
        return await bot.send(error_reply(WAVES_CODE_103))

    from .draw_refresh_char_card import draw_refresh_char_detail_img

    buttons = []
    msg = await draw_refresh_char_detail_img(bot, ev, user_id, uid, buttons)
    if isinstance(msg, str) or isinstance(msg, bytes):
        return await bot.send_option(msg, buttons)


@waves_new_get_one_char_info.on_regex(
    r"^(刷新|更新)[\u4e00-\u9fa5]+(面板|面包)$",
    block=True,
)
async def send_one_char_detail_msg(bot: Bot, ev: Event):
    logger.debug(f"[鸣潮] [角色面板] RAW_TEXT: {ev.raw_text}")
    match = re.search(
        r"(?P<is_refresh>刷新|更新)(?P<char>[\u4e00-\u9fa5]+)(?P<query_type>面板|面包)",
        ev.raw_text,
    )
    logger.debug(f"[鸣潮] [角色面板] MATCH: {match}")
    if not match:
        return
    ev.regex_dict = match.groupdict()
    char = ev.regex_dict.get("char")
    if not char:
        return
    char_id = char_name_to_char_id(char)
    if not char_id:
        return (
            f"[鸣潮] 角色名【{char}】无法找到, 可能暂未适配, 请先检查输入是否正确！\n"
        )
    refresh_type = [char_id]
    if char_id in SPECIAL_CHAR:
        refresh_type = SPECIAL_CHAR.copy()[char_id]

    user_id = ruser_id(ev)

    uid = await WavesBind.get_uid_by_game(user_id, ev.bot_id)
    if not uid:
        return await bot.send(error_reply(WAVES_CODE_103))

    from .draw_refresh_char_card import draw_refresh_char_detail_img

    buttons = []
    msg = await draw_refresh_char_detail_img(
        bot, ev, user_id, uid, buttons, refresh_type
    )
    if isinstance(msg, str) or isinstance(msg, bytes):
        return await bot.send_option(msg, buttons)


@waves_char_detail.on_prefix(("角色面板", "查询"))
async def send_char_detail_msg(bot: Bot, ev: Event):
    char = ev.text.strip(" ")
    logger.debug(f"[鸣潮] [角色面板] CHAR: {char}")
    user_id = ruser_id(ev)
    uid = await WavesBind.get_uid_by_game(user_id, ev.bot_id)
    if not uid:
        return await bot.send(error_reply(WAVES_CODE_103))
    logger.debug(f"[鸣潮] [角色面板] UID: {uid}")
    if not char:
        return

    im = await draw_char_detail_img(ev, uid, char, user_id)
    if isinstance(im, str) or isinstance(im, bytes):
        return await bot.send(im)


@waves_new_char_detail.on_regex(
    r"^(\d+)?[a-zA-Z\u4e00-\u9fa5🥔]+(面板|面包|mb|🍞|伤害(\d+)?)(pk|对比|PK|比|比较)?(?:\s*)((换[^换]*)*)?$",
    block=True,
)
async def send_char_detail_msg2(bot: Bot, ev: Event):
    match = re.search(
        r"(?P<waves_id>\d+)?(?P<char>[a-zA-Z\u4e00-\u9fa5🥔]+)(?P<query_type>面板|面包|mb|🍞|伤害(?P<damage>(\d+)?))(?P<is_pk>pk|对比|PK|比|比较)?(\s*)?(?P<change_list>((换[^换]*)*)?)",
        ev.raw_text,
    )
    if not match:
        return
    ev.regex_dict = match.groupdict()
    waves_id = ev.regex_dict.get("waves_id")
    char = ev.regex_dict.get("char")
    damage = ev.regex_dict.get("damage")
    query_type = ev.regex_dict.get("query_type")
    is_pk = ev.regex_dict.get("is_pk") is not None
    change_list_regex = ev.regex_dict.get("change_list")

# 如果角色名以 `ww` 开头，并且长度大于2时才去掉
    if char and len(char) > 2 and char.startswith(("ww","mc")):
        char = char[2:]

    if waves_id and len(waves_id) != 9:
        return

    if waves_id and len(waves_id) != 9:
        return

    if isinstance(query_type, str) and "伤害" in query_type and not damage:
        damage = "1"

    is_limit_query = False
    if isinstance(char, str) and "极限" in char:
        is_limit_query = True
        char = char.replace("极限", "")

    if damage:
        char = f"{char}{damage}"
    if not char:
        return
    logger.debug(f"[鸣潮] [角色面板] CHAR: {char} {ev.regex_dict}")

    if is_limit_query:
        im = await draw_char_detail_img(
            ev, "1", char, ev.user_id, is_limit_query=is_limit_query
        )
        if isinstance(im, str) or isinstance(im, bytes):
            return await bot.send(im)
        else:
            return

    at_sender = True if ev.group_id else False
    if is_pk:
        if not waves_id and not is_valid_at(ev):
            return await bot.send(
                f"[鸣潮] [角色面板] 角色【{char}】PK需要指定目标玩家!\n", at_sender
            )

        uid = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
        if not uid:
            return await bot.send(error_reply(WAVES_CODE_103))

        im1 = await draw_char_detail_img(
            ev,
            uid,
            char,
            ev.user_id,
            waves_id=None,
            need_convert_img=False,
            is_force_avatar=True,
            change_list_regex=change_list_regex,
        )
        if isinstance(im1, str):
            return await bot.send(im1, at_sender)

        if not isinstance(im1, Image.Image):
            return

        user_id = ruser_id(ev)
        uid = await WavesBind.get_uid_by_game(user_id, ev.bot_id)
        if not uid:
            return await bot.send(error_reply(WAVES_CODE_103))
        im2 = await draw_char_detail_img(
            ev, uid, char, user_id, waves_id, need_convert_img=False
        )
        if isinstance(im2, str):
            return await bot.send(im2, at_sender)

        if not isinstance(im2, Image.Image):
            return

        # 创建一个新的图片对象
        new_im = Image.new(
            "RGBA", (im1.size[0] + im2.size[0], max(im1.size[1], im2.size[1]))
        )

        # 将两张图片粘贴到新图片对象上
        new_im.paste(im1, (0, 0))
        new_im.paste(im2, (im1.size[0], 0))
        new_im = await convert_img(new_im)
        return await bot.send(new_im)
    else:
        user_id = ruser_id(ev)
        uid = await WavesBind.get_uid_by_game(user_id, ev.bot_id)
        if not uid:
            return await bot.send(error_reply(WAVES_CODE_103))
        im = await draw_char_detail_img(
            ev, uid, char, user_id, waves_id, change_list_regex=change_list_regex
        )
        at_sender = False
        if isinstance(im, str) or isinstance(im, bytes):
            return await bot.send(im, at_sender)


@waves_new_char_detail.on_regex(r"^(\d+)?[\u4e00-\u9fa5]+(?:权重)$", block=True)
async def send_char_detail_msg2_weight(bot: Bot, ev: Event):
    match = re.search(
        r"(?P<waves_id>\d+)?(?P<char>[\u4e00-\u9fa5]+)(?:权重)", ev.raw_text
    )
    if not match:
        return
    ev.regex_dict = match.groupdict()
    waves_id = ev.regex_dict.get("waves_id")
    char = ev.regex_dict.get("char")

    if waves_id and len(waves_id) != 9:
        return

    user_id = ruser_id(ev)
    uid = await WavesBind.get_uid_by_game(user_id, ev.bot_id)
    if not uid:
        return await bot.send(error_reply(WAVES_CODE_103))
    if not char:
        return

    im = await draw_char_score_img(ev, uid, char, user_id, waves_id)  # type: ignore
    at_sender = False
    if isinstance(im, str) and ev.group_id:
        at_sender = True
    if isinstance(im, str) or isinstance(im, bytes):
        return await bot.send(im, at_sender)


@waves_upload_char.on_regex(r"^上传[a-zA-Z\u4e00-\u9fa5🥔]+(色图|涩图|🐍图|面板图|🍞图|面包图)$", block=True)
async def upload_char_img(bot: Bot, ev: Event):
    match = re.search(r"上传(?P<char>[a-zA-Z\u4e00-\u9fa5🥔]+)(色图|涩图|🐍图|面板图|🍞图|面包图)", ev.raw_text)
    if not match:
        return
    ev.regex_dict = match.groupdict()
    char = ev.regex_dict.get("char")
    
    if char and len(char) > 2 and char.startswith(("ww","mc")):
        char = char[2:]
    
    if not char:
        return
    await upload_custom_card(bot, ev, char)


@waves_char_card_list.on_regex(r"^[a-zA-Z\u4e00-\u9fa5🥔]+(色图列表|涩图列表|🐍图列表|面板图列表|面包图列表)$", block=True)
async def get_char_card_list(bot: Bot, ev: Event):
    match = re.search(r"(?P<char>[a-zA-Z\u4e00-\u9fa5🥔]+)(色图列表|涩图列表|🐍图列表|面板图列表|面包图列表)", ev.raw_text)
    if not match:
        return
    ev.regex_dict = match.groupdict()
    char = ev.regex_dict.get("char")

    if char and len(char) > 2 and char.startswith(("ww","mc")):
        char = char[2:]

    if not char:
        return
    await get_custom_card_list(bot, ev, char)


@waves_delete_char_card.on_regex(
    r"^删除[a-zA-Z\u4e00-\u9fa5🥔]+(色图|涩图|🐍图|面板图|面包图)[a-zA-Z0-9]+$", block=True
)
async def delete_char_card(bot: Bot, ev: Event):
    match = re.search(
        r"删除(?P<char>[a-zA-Z\u4e00-\u9fa5🥔]+)(色图|涩图|🐍图|面板图|面包图)(?P<hash_id>[a-zA-Z0-9]+)",
        ev.raw_text,
    )
    if not match:
        return
    ev.regex_dict = match.groupdict()
    char = ev.regex_dict.get("char")

    if char and len(char) > 2 and char.startswith(("ww","mc")):
        char = char[2:]

    hash_id = ev.regex_dict.get("hash_id")
    if not char or not hash_id:
        return
    await delete_custom_card(bot, ev, char, hash_id)


@waves_delete_all_card.on_regex(r"^删除全部[a-zA-Z\u4e00-\u9fa5🥔]+(色图|涩图|🐍图|面板图|面包图)$", block=True)
async def delete_all_char_card(bot: Bot, ev: Event):
    match = re.search(r"删除全部(?P<char>[a-zA-Z\u4e00-\u9fa5🥔]+)(色图|涩图|🐍图|面板图|面包图)", ev.raw_text)
    if not match:
        return
    ev.regex_dict = match.groupdict()
    char = ev.regex_dict.get("char")

    if char and len(char) > 2 and char.startswith(("ww","mc")):
        char = char[2:]

    if not char:
        return
    await delete_all_custom_card(bot, ev, char)

@waves_compress_card.on_fullmatch("压缩面板图", block=True)
async def compress_char_card(bot: Bot, ev: Event):
    await compress_all_custom_card(bot, ev)

@waves_upload_mr_char.on_regex(r"^上传[\u4e00-\u9fa5]+(体力背景图|mr背景图)$", block=True)
async def upload_mr_char_img(bot: Bot, ev: Event):
    match = re.search(r"上传(?P<char>[\u4e00-\u9fa5]+)(体力背景图|mr背景图)", ev.raw_text)
    if not match:
        return
    ev.regex_dict = match.groupdict()
    char = ev.regex_dict.get("char")
    if not char:
        return
    await upload_custom_mr_card(bot, ev, char)


@waves_mr_char_card_list.on_regex(r"^[\u4e00-\u9fa5]+(体力背景图列表|mr背景图列表)$", block=True)
async def get_mr_char_card_list(bot: Bot, ev: Event):
    match = re.search(r"(?P<char>[\u4e00-\u9fa5]+)(体力背景图列表|mr背景图列表)", ev.raw_text)
    if not match:
        return
    ev.regex_dict = match.groupdict()
    char = ev.regex_dict.get("char")
    if not char:
        return
    await get_custom_mr_card_list(bot, ev, char)


@waves_delete_mr_char_card.on_regex(
    r"^删除[\u4e00-\u9fa5]+(体力背景图|mr背景图)[a-zA-Z0-9]+$", block=True
)
async def delete_mr_char_card(bot: Bot, ev: Event):
    match = re.search(
        r"删除(?P<char>[\u4e00-\u9fa5]+)(体力背景图|mr背景图)(?P<hash_id>[a-zA-Z0-9]+)",
        ev.raw_text,
    )
    if not match:
        return
    ev.regex_dict = match.groupdict()
    char = ev.regex_dict.get("char")
    hash_id = ev.regex_dict.get("hash_id")
    if not char or not hash_id:
        return
    await delete_custom_mr_card(bot, ev, char, hash_id)


@waves_delete_all_mr_card.on_regex(r"^删除全部[\u4e00-\u9fa5]+(体力背景图|mr背景图)$", block=True)
async def delete_all_mr_char_card(bot: Bot, ev: Event):
    match = re.search(r"删除全部(?P<char>[\u4e00-\u9fa5]+)(体力背景图|mr背景图)", ev.raw_text)
    if not match:
        return
    ev.regex_dict = match.groupdict()
    char = ev.regex_dict.get("char")
    if not char:
        return
    await delete_all_custom_mr_card(bot, ev, char)