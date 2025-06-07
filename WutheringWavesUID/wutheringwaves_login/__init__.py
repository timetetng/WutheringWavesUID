import re

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..wutheringwaves_config import PREFIX
from .login import code_login, page_login

sv_kuro_login = SV("库洛登录")
sv_kuro_login_help = SV("库洛登录帮助", pm=0, priority=4)

@sv_kuro_login_help.on_fullmatch(("登录帮助", "登陆帮助", "登入帮助", "登龙帮助", "login help"),block=True)
async def get_login_help_msg(bot: Bot, ev: Event):
    msg = ["""
[鸣潮]wwuid登录教程
1、使用ww登录命令来登录账号，并且不要再次登录库街区，目前wwuid登录方式与库街区APP相同，因此通常情况下，重复登录会互踢下线；
2、如果你需要登录/绑定多个游戏账号，请使用不同库街区账号绑定不同的游戏账号，再重新登陆。或者仅使用ww绑定特征码方式绑定另一个账号；
3、如果你同一个账号需要登录多个bot，请使用私聊已登录bot ww获取token，来获取token和did，然后在其他bot处使用【ww添加token token,did】命令以使用token登录；
4、已绑定的token长期有效，did通常不变，如果你重新登录或退出已登录的库街区账号，可能会导致原token失效，此时需要重新登录；
5、如果你执意同时登录库街区和bot，请查看下面教程：

[鸣潮] 库街区和bot共存教程
1、手机登录库街区APP（网页端不支持）
2、打开抓包软件开始抓包(推荐使用ProxyPin,支持安卓和iOS且开源免费
https://github.com/wanghongenpin/proxypin/tree/main,下载后只需要HTTP抓包，不需要配置SSL证书)
3、点进鸣潮终端界面
4、停止抓包
5、搜索关键词“kurobbs”，找到相关POST请求
6、查找请求体里“token”、“did”这两个字段，token字段以ey开头，did字段是数字+大写字母的组合
7、复制token和did，以命令“ww添加token token,did”的格式发送给bot
例如：ww添加token ey*****************************,20CDF7XXXXXXXXXXXXXXXXXXXX4DDBA1A59C46
8、登录成功即可实现库街区和bot共存
"""
]
    await bot.send(msg)
    return msg



@sv_kuro_login.on_fullmatch(("登录", "登陆", "登入", "登龙", "login"),block=True)
async def get_login_msg(bot: Bot, ev: Event):
    game_title = "[鸣潮]"

    # uid_list = await WavesBind.get_uid_list_by_game(ev.user_id, ev.bot_id)
    # if uid_list is None:
    #     return await bot.send(ERROR_CODE[WAVES_CODE_103])

    text = re.sub(r'["\n\t ]+', "", ev.text.strip())
    text = text.replace("，", ",")
    if text == "":
        return await page_login(bot, ev)

    elif "," in text:
        return await code_login(bot, ev, text)

    elif text.isdigit():
        return

    at_sender = True if ev.group_id else False
    return await bot.send(
        f"{game_title} 账号登录失败\n请重新输入命令【{PREFIX}登录】进行登录\n",
        at_sender=at_sender,
    )
