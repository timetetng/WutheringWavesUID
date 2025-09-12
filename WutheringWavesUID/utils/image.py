import os
import random
from io import BytesIO
from pathlib import Path
from typing import Literal, Optional, Tuple, Union

from PIL import (
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageFont,
    ImageOps,
)

from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.utils.image.image_tools import crop_center_img
from gsuid_core.utils.image.utils import sget

from ..utils.resource.RESOURCE_PATH import (
    AVATAR_PATH,
    CUSTOM_CARD_PATH,
    CUSTOM_MR_CARD_PATH,
    ROLE_PILE_PATH,
    SHARE_BG_PATH,
    WEAPON_PATH,
)

ICON = Path(__file__).parent.parent.parent / "ICON.png"
TEXT_PATH = Path(__file__).parent / "texture2d"
GREY = (216, 216, 216)
BLACK_G = (40, 40, 40)
YELLOW = (255, 200, 1)
RED = (255, 0, 0)
BLUE = (1, 183, 255)
GOLD = (224, 202, 146)
SPECIAL_GOLD = (234, 183, 4)
AMBER = (204, 140, 0)
GREEN = (144, 238, 144)

# 冷凝-凝夜白霜
WAVES_FREEZING = (53, 152, 219)
# 热熔-熔山裂谷
WAVES_MOLTEN = (186, 55, 42)
# 导电-彻空冥雷
WAVES_VOID = (185, 106, 217)
# 气动-啸谷长风
WAVES_SIERRA = (22, 145, 121)
# 衍射-浮星祛暗
WAVES_CELESTIAL = (241, 196, 15)
# 湮灭-沉日劫明
WAVES_SINKING = (132, 63, 161)
# 治疗-隐世回光
WAVES_REJUVENATING = (45, 194, 107)
# 辅助-轻云出月
WAVES_MOONLIT = (149, 165, 166)
# 攻击-不绝余音
WAVES_LINGERING = (52, 73, 94)

WAVES_ECHO_MAP = {
    "凝夜白霜": WAVES_FREEZING,
    "熔山裂谷": WAVES_MOLTEN,
    "彻空冥雷": WAVES_VOID,
    "啸谷长风": WAVES_SIERRA,
    "浮星祛暗": WAVES_CELESTIAL,
    "沉日劫明": WAVES_SINKING,
    "隐世回光": WAVES_REJUVENATING,
    "轻云出月": WAVES_MOONLIT,
    "不绝余音": WAVES_LINGERING,
}

WAVES_SHUXING_MAP = {
    "冷凝": WAVES_FREEZING,
    "热熔": WAVES_MOLTEN,
    "导电": WAVES_VOID,
    "气动": WAVES_SIERRA,
    "衍射": WAVES_CELESTIAL,
    "湮灭": WAVES_SINKING,
}

CHAIN_COLOR = {
    0: WAVES_MOONLIT,
    1: WAVES_LINGERING,
    2: WAVES_FREEZING,
    3: WAVES_SIERRA,
    4: WAVES_VOID,
    5: AMBER,
    6: WAVES_MOLTEN,
}

CHAIN_COLOR_LIST = [CHAIN_COLOR[i] for i in range(7)]

WEAPON_RESONLEVEL_COLOR = {
    0: WAVES_MOONLIT,
    1: WAVES_LINGERING,
    2: WAVES_FREEZING,
    3: WAVES_SIERRA,
    4: WAVES_VOID,
    5: AMBER,
    6: WAVES_MOLTEN,
}

from .name_convert import char_name_to_char_id 
from .resource.RESOURCE_PATH import CUSTOM_MR_CARD_PATH,CUSTOM_MR_CARD_PATH2
import colorsys
from gsuid_core.logger import logger

def get_ICON():
    return Image.open(ICON)


async def get_random_share_bg():
    path = random.choice(os.listdir(f"{SHARE_BG_PATH}"))
    return Image.open(f"{SHARE_BG_PATH}/{path}").convert("RGBA")


async def get_random_share_bg_path():
    path = random.choice(os.listdir(f"{SHARE_BG_PATH}"))
    return SHARE_BG_PATH / path


async def get_random_waves_role_pile(char_id: Optional[str] = None):
    if char_id:
        return await get_role_pile_old(char_id, custom=True)

    path = random.choice(os.listdir(f"{ROLE_PILE_PATH}"))
    return Image.open(f"{ROLE_PILE_PATH}/{path}").convert("RGBA")


async def get_role_pile(
    resource_id: Union[int, str], custom: bool = False
) -> tuple[bool, Image.Image]:
    if custom:
        custom_dir = f"{CUSTOM_CARD_PATH}/{resource_id}"
        if os.path.isdir(custom_dir) and len(os.listdir(custom_dir)) > 0:
            # logger.info(f'使用自定义角色头像: {resource_id}')
            path = random.choice(os.listdir(custom_dir))
            if path:
                return True, Image.open(f"{custom_dir}/{path}").convert("RGBA")

    name = f"role_pile_{resource_id}.png"
    path = ROLE_PILE_PATH / name
    return False, Image.open(path).convert("RGBA")


async def get_role_pile_old(
    resource_id: Union[int, str], custom: bool = False
) -> Image.Image:
    if custom:
        custom_dir = f"{CUSTOM_MR_CARD_PATH2}/{resource_id}"
        if os.path.isdir(custom_dir) and len(os.listdir(custom_dir)) > 0:
            # logger.info(f'使用自定义角色头像: {resource_id}')
            path = random.choice(os.listdir(custom_dir))
            if path:
                return Image.open(f"{custom_dir}/{path}").convert("RGBA")

    name = f"role_pile_{resource_id}.png"
    path = ROLE_PILE_PATH / name
    return Image.open(path).convert("RGBA")


async def get_square_avatar(resource_id: Union[int, str]) -> Image.Image:
    name = f"role_head_{resource_id}.png"
    path = AVATAR_PATH / name
    return Image.open(path).convert("RGBA")


async def cropped_square_avatar(item_icon: Image.Image, size: int) -> Image.Image:
    # 目标尺寸
    target_width, target_height = size, size
    # 原始尺寸
    original_width, original_height = item_icon.size

    width_ratio = target_width / original_width
    height_ratio = target_height / original_height
    scale_ratio = max(width_ratio, height_ratio)
    new_width = int(original_width * scale_ratio)
    new_height = int(original_height * scale_ratio)
    resized_image = item_icon.resize((new_width, new_height), Image.Resampling.LANCZOS)
    x_center = new_width // 2
    y_center = new_height // 2
    crop_area = (
        x_center - target_width // 2,
        y_center - target_height // 2,
        x_center + target_width // 2,
        y_center + target_height // 2,
    )
    resized_image = resized_image.crop(crop_area).convert("RGBA")
    return resized_image


async def get_square_weapon(resource_id: Union[int, str]) -> Image.Image:
    name = f"weapon_{resource_id}.png"
    path = WEAPON_PATH / name
    if os.path.exists(path):
        return Image.open(path).convert("RGBA")
    else:
        return Image.open(WEAPON_PATH / "weapon_21010063.png").convert("RGBA")


async def get_attribute(name: str = "", is_simple: bool = False) -> Image.Image:
    if is_simple:
        name = f"attribute/attr_simple_{name}.png"
    else:
        name = f"attribute/attr_{name}.png"
    return Image.open(TEXT_PATH / name).convert("RGBA")


async def get_attribute_prop(name: str = "") -> Image.Image:
    return Image.open(TEXT_PATH / f"attribute_prop/attr_prop_{name}.png").convert(
        "RGBA"
    )


async def get_attribute_effect(name: str = "") -> Image.Image:
    return Image.open(TEXT_PATH / f"attribute_effect/attr_{name}.png").convert("RGBA")


async def get_weapon_type(name: str = "") -> Image.Image:
    return Image.open(TEXT_PATH / f"weapon_type/weapon_type_{name}.png").convert("RGBA")


def get_waves_bg(w: int, h: int, bg: str = "bg") -> Image.Image:
    img = Image.open(TEXT_PATH / f"{bg}.jpg").convert("RGBA")
    return crop_center_img(img, w, h)


def get_crop_waves_bg(w: int, h: int, bg: str = "bg") -> Image.Image:
    img = Image.open(TEXT_PATH / f"{bg}.jpg").convert("RGBA")

    width, height = img.size

    crop_box = (0, height // 2, width, height)

    cropped_image = img.crop(crop_box)

    return crop_center_img(cropped_image, w, h)


async def get_qq_avatar(
    qid: Optional[Union[int, str]] = None,
    avatar_url: Optional[str] = None,
    size: int = 640,
) -> Image.Image:
    if qid:
        avatar_url = f"http://q1.qlogo.cn/g?b=qq&nk={qid}&s={size}"
    elif avatar_url is None:
        avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk=3399214199&s={size}"
    char_pic = Image.open(BytesIO((await sget(avatar_url)).content)).convert("RGBA")
    return char_pic


async def get_event_avatar(
    ev: Event,
    avatar_path: Optional[Path] = None,
    size: int = 640,
    is_valid_at_param: bool = True,
) -> Image.Image:
    img = None

    if is_valid_at_param:
        from ..utils.at_help import is_valid_at

        is_valid_at_param = is_valid_at(ev)

    if ev.bot_id == "onebot" and ev.at and is_valid_at_param:
        try:
            img = await get_qq_avatar(ev.at, size=size)
        except Exception:
            img = None

    if img is None and "avatar" in ev.sender and ev.sender["avatar"]:
        avatar_url: str = ev.sender["avatar"]
        if avatar_url.startswith(("http", "https")):
            try:
                content = (await sget(avatar_url)).content
                img = Image.open(BytesIO(content)).convert("RGBA")
            except Exception:
                img = None

    if img is None and ev.bot_id == "onebot" and not ev.sender:
        try:
            img = await get_qq_avatar(ev.user_id, size=size)
        except Exception:
            img = None

    if img is None and avatar_path:
        pic_path_list = list(avatar_path.iterdir())
        if pic_path_list:
            path = random.choice(pic_path_list)
            img = Image.open(path).convert("RGBA")

    if img is None:
        img = await get_square_avatar(1203)

    return img


def get_small_logo(logo_num=1):
    return Image.open(TEXT_PATH / f"logo_small_{logo_num}.png")


def get_footer(color: Literal["white", "black", "hakush"] = "white"):
    return Image.open(TEXT_PATH / f"footer_{color}.png")


def add_footer(
    img: Image.Image,
    w: int = 0,
    offset_y: int = 0,
    is_invert: bool = False,
    color: Literal["white", "black", "hakush"] = "white",
):
    footer = get_footer(color)
    if is_invert:
        r, g, b, a = footer.split()
        rgb_image = Image.merge("RGB", (r, g, b))
        rgb_image = ImageOps.invert(rgb_image.convert("RGB"))
        r2, g2, b2 = rgb_image.split()
        footer = Image.merge("RGBA", (r2, g2, b2, a))

    if w != 0:
        footer = footer.resize(
            (w, int(footer.size[1] * w / footer.size[0])),
        )

    x, y = (
        int((img.size[0] - footer.size[0]) / 2),
        img.size[1] - footer.size[1] - 20 + offset_y,
    )

    img.paste(footer, (x, y), footer)
    return img


async def change_color(
    chain,
    color: tuple = (255, 255, 255),
    w: Optional[int] = None,
    h: Optional[int] = None,
):
    # 获取图像数据
    pixels = chain.load()  # 加载像素数据
    if w is None:
        w = chain.size[0]
    if h is None:
        h = chain.size[1]

    if not isinstance(h, int) or not isinstance(w, int):
        return chain

    # 遍历图像的每个像素
    for y in range(h):  # 图像高度
        for x in range(w):  # 图像宽度
            r, g, b, a = pixels[x, y]
            pixels[x, y] = color + (a,)

    return chain


def draw_text_with_shadow(
    image: ImageDraw.ImageDraw,
    text: str,
    _x: int,
    _y: int,
    font: ImageFont.FreeTypeFont,
    fill_color: str = "white",
    shadow_color: Union[float, tuple[int, ...], str] = "black",
    offset: Tuple[int, int] = (2, 2),
    anchor="rm",
):
    """描边"""
    for i in range(-offset[0], offset[0] + 1):
        for j in range(-offset[1], offset[1] + 1):
            image.text(
                (_x + i, _y + j), text, font=font, fill=shadow_color, anchor=anchor
            )

    image.text((_x, _y), text, font=font, fill=fill_color, anchor=anchor)
    image.text((_x, _y), text, font=font, fill=fill_color, anchor=anchor)


def compress_to_webp(
    image_path: Path, quality: int = 80, delete_original: bool = False
) -> tuple[bool, Path]:
    try:
        from PIL import Image

        # 确保文件存在
        if not image_path.exists():
            logger.warning(f"图片不存在: {image_path}")
            return False, image_path

        # 检查文件是否已经是webp格式
        if image_path.suffix.lower() == ".webp":
            logger.info(f"图片已经是webp格式: {image_path}")
            return False, image_path

        # 创建webp文件路径
        webp_path = image_path.with_suffix(".webp")

        # 打开图片
        img = Image.open(image_path)

        # 记录原始大小
        orig_size = image_path.stat().st_size

        # 保存为webp格式
        img.save(webp_path, "WEBP", quality=quality, method=6)

        # 计算压缩率
        webp_size = webp_path.stat().st_size
        compression_ratio = (1 - webp_size / orig_size) * 100 if orig_size > 0 else 0
        logger.info(
            f"图片 {image_path.name} 压缩为webp格式, 压缩率: {compression_ratio:.2f}%"
        )

        # 删除原图片（如果需要）
        if delete_original:
            image_path.unlink()
            logger.info(f"原图片已删除: {image_path}")

        return True, webp_path

    except Exception as e:
        logger.error(f"压缩图片为webp格式失败: {e}")
        return False, image_path


async def draw_avatar_with_star(
    avatar: Image.Image,
    star_level: int = 5,
    need_text: bool = True,
    img_color: float | tuple[float, ...] | str | None = (0, 0, 0, 255),
    item_width: int = 144,
    item_height: int = 170,
) -> Image.Image:
    if need_text:
        img = Image.new("RGBA", (item_width, item_height), img_color)
    else:
        img = Image.new("RGBA", (item_width, item_width), img_color)

    # 144*144
    star_bg = Image.open(TEXT_PATH / f"star_{star_level}.png")
    avatar = avatar.resize((item_width, item_width))

    img.alpha_composite(avatar, (0, 0))
    img.alpha_composite(star_bg, (0, 0))
    return img


async def get_star_bg(star_level: int = 5) -> Image.Image:
    return Image.open(TEXT_PATH / f"star_{star_level}.png")


async def pic_download_from_url(
    path: Path,
    pic_url: str,
) -> Image.Image:
    path.mkdir(parents=True, exist_ok=True)

    name = pic_url.split("/")[-1]
    _path = path / name
    if not _path.exists():
        from gsuid_core.utils.download_resource.download_file import download

        await download(pic_url, path, name, tag="[鸣潮]")

    return Image.open(_path).convert("RGBA")


async def get_custom_gaussian_blur(img: Image.Image) -> Image.Image:
    from ..wutheringwaves_config.wutheringwaves_config import ShowConfig

    radius = ShowConfig.get_config("BlurRadius").data
    if radius > 0:
        # 应用高斯模糊
        img = img.filter(ImageFilter.GaussianBlur(radius=radius))
        # 调整亮度和对比度
        brightness = ShowConfig.get_config("BlurBrightness").data
        try:
            brightness = float(brightness)
        except Exception:
            brightness = 1
        contrast = ShowConfig.get_config("BlurContrast").data
        try:
            contrast = float(contrast)
        except Exception:
            contrast = 1

        img = ImageEnhance.Brightness(img).enhance(brightness)
        # 调整对比度
        img = ImageEnhance.Contrast(img).enhance(contrast)
    return img

async def adapt_bg_image(
    img: Image.Image, target_w: int, target_h: int
) -> Image.Image:
    """
    将任意尺寸的背景图自适应处理为目标尺寸。
    策略: 按比例缩放，让短边贴合目标尺寸，然后从中心裁剪长边。
    """
    original_w, original_h = img.size
    target_ratio = target_w / target_h
    original_ratio = original_w / original_h

    if original_ratio > target_ratio:
        # 原始图片比目标更宽，以高度为基准缩放
        new_h = target_h
        new_w = int(new_h * original_ratio)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # --- MODIFICATION START ---
        # 确保所有坐标都是整数
        left = int((new_w - target_w) / 2)
        top = 0
        right = int(left + target_w)
        bottom = int(new_h)
        # --- MODIFICATION END ---
        
        img = img.crop((left, top, right, bottom))
    else:
        # 原始图片比目标更高（或比例相同），以宽度为基准缩放
        new_w = target_w
        new_h = int(new_w / original_ratio)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # --- MODIFICATION START ---
        # 确保所有坐标都是整数
        left = 0
        top = int((new_h - target_h) / 2)
        right = int(new_w)
        bottom = int(top + target_h)
        # --- MODIFICATION END ---
        
        img = img.crop((left, top, right, bottom))

    return img

async def get_random_character_bg(char_name: str) -> Optional[Path]:
    """
    根据角色名获取一个随机的自定义背景图路径。
    """
    char_id = char_name_to_char_id(char_name)
    if not char_id:
        return None

    char_bg_dir = CUSTOM_MR_CARD_PATH / str(char_id)
    if not char_bg_dir.exists() or not char_bg_dir.is_dir():
        return None

    valid_images = [
        f
        for f in char_bg_dir.iterdir()
        if f.is_file() and f.suffix.lower() in [".jpg", ".png", ".jpeg", ".webp"]
    ]
    
    # ===================== 在这里加上日志 =====================
    logger.info(f"为角色 {char_name} 找到了 {len(valid_images)} 张背景图: {[img.name for img in valid_images]}")
    # ==========================================================

    if not valid_images:
        return None

    return random.choice(valid_images)

def adjust_color(rgb_color, brightness_factor, saturation_factor):
    """
    调整RGB颜色的亮度和饱和度。
    :param rgb_color: (r, g, b) 元组, 范围 0-255
    :param brightness_factor: 亮度调整因子, >1 提亮, <1 变暗
    :param saturation_factor: 饱和度调整因子, >1 更鲜艳, <1 更灰
    :return: 调整后的 (r, g, b) 元组
    """
    r, g, b = [x / 255.0 for x in rgb_color[:3]]  # 归一化到 0-1
    
    # RGB 转 HLS (色相, 亮度, 饱和度)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    
    # 调整亮度和饱和度
    l = min(1.0, l * brightness_factor)
    s = min(1.0, s * saturation_factor)
    
    # HLS 转 RGB
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    
    # 转回 0-255 范围
    return int(r * 255), int(g * 255), int(b * 255)

def is_color_light(rgb_color):
    """
    根据人眼感知加权平均法，判断一个颜色是亮色还是暗色。
    :param rgb_color: (r, g, b) 元组, 范围 0-255
    :return: True 如果是亮色, False 如果是暗色
    """
    r, g, b = rgb_color[:3]
    # 计算加权亮度，这个公式更符合人眼对不同颜色的敏感度
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    # 140是一个比较适中的阈值，可以根据需要微调
    return luminance > 140