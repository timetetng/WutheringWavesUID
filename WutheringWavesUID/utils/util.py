import asyncio
import random
import string
import time
from functools import wraps
from typing import Any, List

import httpx
from subscribe import gs_subscribe


def timed_async_cache(expiration, condition=lambda x: True):
    def decorator(func):
        cache = {}
        locks = {}

        @wraps(func)
        async def wrapper(*args):
            current_time = time.time()
            # 如果是类方法，args[0]是实例，我们获取类名
            if args and hasattr(args[0], "__class__"):
                cache_key = f"{args[0].__class__.__name__}.{func.__name__}"
            else:
                cache_key = func.__name__

            # 为每个缓存键创建一个锁
            if cache_key not in locks:
                locks[cache_key] = asyncio.Lock()

            # 检查缓存，如果有效则直接返回
            if cache_key in cache:
                value, timestamp = cache[cache_key]
                if current_time - timestamp < expiration:
                    return value

            # 获取锁以确保并发安全
            async with locks[cache_key]:
                # 双重检查，避免等待锁期间其他协程已经更新了缓存
                if cache_key in cache:
                    value, timestamp = cache[cache_key]
                    if current_time - timestamp < expiration:
                        return value

                # 执行原始函数
                value = await func(*args)
                if condition(value):
                    cache[cache_key] = (value, current_time)
                return value

        return wrapper

    return decorator


# 使用示例
@timed_async_cache(86400)
async def get_public_ip(host="127.0.0.1"):
    # 尝试从 ipify 获取 IP 地址
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("https://api.ipify.org/?format=json", timeout=4)
            ip = r.json()["ip"]
            return ip
    except:  # noqa:E722, B001
        pass

    # 尝试从 httpbin.org 获取 IP 地址
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("https://httpbin.org/ip", timeout=4)
            ip = r.json()["origin"]
            return ip
    except Exception:
        pass

    return host


def generate_random_string(length=32):
    # 定义可能的字符集合
    characters = string.ascii_letters + string.digits + string.punctuation
    # 使用random.choice随机选择字符，并连接成字符串
    random_string = "".join(random.choice(characters) for i in range(length))
    return random_string


def generate_random_ipv6_manual():
    return ":".join([hex(random.randint(0, 0xFFFF))[2:].zfill(4) for _ in range(8)])


def hide_uid(uid: str) -> str:
    from ..wutheringwaves_config import WutheringWavesConfig

    HideUid = WutheringWavesConfig.get_config("HideUid").data
    if not HideUid:
        return uid
    if len(uid) < 2:
        return uid
    return uid[:2] + "*" * 4 + uid[-2:]


def format_with_defaults(desc: str, params: List[Any], default_value: str = "N/A"):
    num_placeholders = desc.count("{")  # 简单估计位置参数数量
    params_list = list(params)
    while len(params_list) < num_placeholders:
        params_list.append(default_value)
    return desc.format(*params_list)


def get_version():
    from ..version import WutheringWavesUID_version

    return WutheringWavesUID_version


@timed_async_cache(300)
async def send_master_info(msg: str):
    subscribes = await gs_subscribe.get_subscribe("联系主人")
    if not subscribes:
        return
    if subscribes:
        for sub in subscribes:
            await sub.send(f"【联系主人】：{msg}")


def login_platform() -> str:
    from ..wutheringwaves_config import WutheringWavesConfig

    LoginType = WutheringWavesConfig.get_config("WavesLoginType").data
    return LoginType if LoginType else "h5"
