from typing import List, Union

from gsuid_core.bot import Bot
from gsuid_core.models import Event

from ..utils import hint
from ..utils.api.api import GAME_ID
from ..utils.api.model import KuroWavesUserInfo
from ..utils.database.models import WavesBind, WavesUser
from ..utils.error_reply import ERROR_CODE, WAVES_CODE_101, WAVES_CODE_103
from ..utils.waves_api import waves_api


async def add_cookie(ev: Event, ck: str, did: str) -> str:
    succ, platform, kuroWavesUserInfos = await waves_api.get_kuro_role_list(ck)
    if not succ or not isinstance(kuroWavesUserInfos, list):
        return hint.error_reply(code=WAVES_CODE_101)

    role_list = []
    for kuroWavesUserInfo in kuroWavesUserInfos:
        data = KuroWavesUserInfo.model_validate(kuroWavesUserInfo)
        if data.gameId != GAME_ID:
            continue

        user = await WavesUser.get_user_by_attr(
            ev.user_id, ev.bot_id, "uid", data.roleId
        )

        if user:
            await WavesUser.update_data_by_data(
                select_data={
                    "user_id": ev.user_id,
                    "bot_id": ev.bot_id,
                    "uid": data.roleId,
                },
                update_data={
                    "cookie": ck,
                    "status": "",
                    "platform": platform,
                },
            )
        else:
            await WavesUser.insert_data(
                ev.user_id,
                ev.bot_id,
                cookie=ck,
                uid=data.roleId,
                platform=platform,
            )

        bat = ""
        if user and user.bat:
            bat = user.bat
        else:
            succ, bat = await waves_api.get_request_token(
                data.roleId, ck, did, data.serverId
            )
            if not succ or not bat:
                return bat

        # 更新bat
        await WavesUser.update_data_by_data(
            select_data={
                "user_id": ev.user_id,
                "bot_id": ev.bot_id,
                "uid": data.roleId,
            },
            update_data={"bat": bat, "did": did},
        )

        res = await WavesBind.insert_waves_uid(
            ev.user_id, ev.bot_id, data.roleId, ev.group_id, lenth_limit=9
        )
        if res == 0 or res == -2:
            await WavesBind.switch_uid_by_game(ev.user_id, ev.bot_id, data.roleId)

        role_list.append(
            {
                "名字": data.roleName,
                "特征码": data.roleId,
            }
        )

    if len(role_list) == 0:
        return "登录失败\n"

    msg = []
    for role in role_list:
        msg.append(f"[鸣潮]【{role['名字']}】特征码【{role['特征码']}】登录成功!")
    return "\n".join(msg)


async def delete_cookie(ev: Event, uid: str) -> str:
    user = await WavesUser.get_user_by_attr(ev.user_id, ev.bot_id, "uid", uid)
    if not user or not user.cookie:
        return f"[鸣潮] 特征码[{uid}]的token删除失败!\n❌不存在该特征码的token!\n"

    await WavesUser.update_data_by_data(
        select_data={"user_id": ev.user_id, "bot_id": ev.bot_id, "uid": uid},
        update_data={"cookie": ""},
    )
    return f"[鸣潮] 特征码[{uid}]的token删除成功!\n"


async def get_cookie(bot: Bot, ev: Event) -> Union[List[str], str]:
    uid_list = await WavesBind.get_uid_list_by_game(ev.user_id, ev.bot_id)
    if uid_list is None:
        return ERROR_CODE[WAVES_CODE_103]

    msg = ""  # 修改这里，将 msg 初始化为一个空字符串
    for uid in uid_list:
        ck = await waves_api.get_self_waves_ck(uid, ev.user_id)
        if not ck:
            continue
        message = f"""你的uid: {uid}
你的token: {ck}
如需使用token登陆其他bot，请复制下面的文本:
ww添加token {ck}

"""
        msg += message  # 修改这里，将 message 添加到 msg 字符串中

    if not msg:
        return "您当前未绑定token或者token已全部失效\n"

    return msg  # 返回合并后的字符串
