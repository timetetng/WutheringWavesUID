import asyncio
import hashlib
import shutil
import ssl
import time
from typing import List, Optional
import mimetypes 
import httpx

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.utils.download_resource.download_file import download
from gsuid_core.utils.image.convert import convert_img

from ..utils.name_convert import alias_to_char_name, char_name_to_char_id
from ..utils.resource.constant import SPECIAL_CHAR, SPECIAL_CHAR_ID
from ..utils.resource.RESOURCE_PATH import CUSTOM_MR_CARD_PATH


def get_hash_id(name):
    return hashlib.sha256(name.encode()).hexdigest()[:8]


def get_char_id_and_name(char: str) -> tuple[Optional[str], str, str]:
    char_id = None
    msg = f"[鸣潮] 角色名【{char}】无法找到, 可能暂未适配, 请先检查输入是否正确！"
    sex = ""
    if "男" in char:
        char = char.replace("男", "")
        sex = "男"
    elif "女" in char:
        char = char.replace("女", "")
        sex = "女"

    char = alias_to_char_name(char)
    if not char:
        return char_id, char, msg

    char_id = char_name_to_char_id(char)
    if not char_id:
        return char_id, char, msg

    if char_id in SPECIAL_CHAR:
        if not sex:
            msg1 = f"[鸣潮] 主角面板【{char}】需要指定性别！"
            return char_id, char, msg1
        char_id = SPECIAL_CHAR_ID[f"{char}·{sex}"]

    return char_id, char, ""


async def get_image(ev: Event) -> Optional[List[str]]:
    res = []
    for content in ev.content:
        if (
            content.type == "img"
            and content.data
            and isinstance(content.data, str)
            and content.data.startswith("http")
        ):
            res.append(content.data)
        elif (
            content.type == "image"
            and content.data
            and isinstance(content.data, str)
            and content.data.startswith("http")
        ):
            res.append(content.data)

    if not res and ev.image:
        res.append(ev.image)

    return res


async def upload_custom_mr_card(bot: Bot, ev: Event, char: str):
    at_sender = True if ev.group_id else False

    upload_images = await get_image(ev)
    if not upload_images:
        return await bot.send("[鸣潮] 上传角色体力背景图失败\n请同时发送图片及其命令", at_sender)

    char_id, char, msg = get_char_id_and_name(char)
    if msg:
        return await bot.send(msg, at_sender)

    temp_dir = CUSTOM_MR_CARD_PATH / f"{char_id}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    success = True
    for upload_image in upload_images:
        # 获取图片扩展名（如 .png, .jpg）
        ext = mimetypes.guess_extension(upload_image.split("?")[0]) or ".png"
        if ext != ".png":
            ext = ".png"  # 如果不是 PNG，则强制转为 PNG 格式

        name = f"{char}_{int(time.time() * 1000)}{ext}"
        temp_path = temp_dir / name

        if not temp_path.exists():
            try:
                if httpx.__version__ >= "0.28.0":
                    ssl_context = ssl.create_default_context()
                    ssl_context.set_ciphers("DEFAULT")
                    sess = httpx.AsyncClient(verify=ssl_context)
                else:
                    sess = httpx.AsyncClient()
            except Exception as e:
                logger.exception(f"{httpx.__version__} - {e}")
                sess = None
            
            code = await download(upload_image, temp_dir, name, tag="[鸣潮]", sess=sess)
            if not isinstance(code, int) or code != 200:
                success = False
                break

    if success:
        return await bot.send(f"[鸣潮]【{char}】上传角色体力背景图成功！", at_sender)
    else:
        return await bot.send(f"[鸣潮]【{char}】上传角色体力背景图失败！", at_sender)


async def get_custom_mr_card_list(bot: Bot, ev: Event, char: str):
    at_sender = True if ev.group_id else False
    char_id, char, msg = get_char_id_and_name(char)
    if msg:
        return await bot.send(msg, at_sender)

    temp_dir = CUSTOM_MR_CARD_PATH / f"{char_id}"
    if not temp_dir.exists():
        return await bot.send(f"[鸣潮] 角色【{char}】暂未上传过角色体力背景图！", at_sender)

    # 获取角色文件夹图片数量, 只要图片
    files = [
        f
        for f in temp_dir.iterdir()
        if f.is_file() and f.suffix in [".jpg", ".png", ".jpeg", ".webp"]
    ]

    imgs = []
    for index, f in enumerate(files, start=1):
        img = await convert_img(f)
        hash_id = get_hash_id(f.name)
        imgs.append(f"{char}体力背景图id : {hash_id}")
        imgs.append(img)

    # imgs 5个一组
    for i in range(0, len(imgs), 10):
        send = imgs[i : i + 10]
        await bot.send(send)
        await asyncio.sleep(0.5)


async def delete_custom_mr_card(bot: Bot, ev: Event, char: str, hash_id: str):
    at_sender = True if ev.group_id else False
    char_id, char, msg = get_char_id_and_name(char)
    if msg:
        return await bot.send(msg, at_sender)

    temp_dir = CUSTOM_MR_CARD_PATH / f"{char_id}"
    if not temp_dir.exists():
        return await bot.send(f"[鸣潮] 角色【{char}】暂未上传过角色体力背景图！", at_sender)

    files_map = {
        get_hash_id(f.name): f
        for f in temp_dir.iterdir()
        if f.is_file() and f.suffix in [".jpg", ".png", ".jpeg", ".webp"]
    }

    if hash_id not in files_map:
        return await bot.send(
            f"[鸣潮] 角色【{char}】未找到id为【{hash_id}】的角色体力背景图！", at_sender
        )

    # 删除文件
    try:
        files_map[hash_id].unlink()
        return await bot.send(
            f"[鸣潮] 删除角色【{char}】的id为【{hash_id}】的角色体力背景图成功！", at_sender
        )
    except Exception:
        return


async def delete_all_custom_mr_card(bot: Bot, ev: Event, char: str):
    at_sender = True if ev.group_id else False
    char_id, char, msg = get_char_id_and_name(char)
    if msg:
        return await bot.send(msg, at_sender)

    temp_dir = CUSTOM_MR_CARD_PATH / f"{char_id}"
    if not temp_dir.exists():
        return await bot.send(f"[鸣潮] 角色【{char}】暂未上传过角色体力背景图！", at_sender)

    files_map = {
        get_hash_id(f.name): f
        for f in temp_dir.iterdir()
        if f.is_file() and f.suffix in [".jpg", ".png", ".jpeg", ".webp"]
    }

    if len(files_map) == 0:
        return await bot.send(f"[鸣潮] 角色【{char}】暂未上传过角色体力背景图！", at_sender)

    # 删除文件夹包括里面的内容
    try:
        if temp_dir.exists() and temp_dir.is_dir():
            shutil.rmtree(temp_dir)
    except Exception:
        pass

    return await bot.send(f"[鸣潮] 删除角色【{char}】的所有角色体力背景图成功！", at_sender)
