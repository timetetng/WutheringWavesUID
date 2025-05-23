from typing import List, Union

from gsuid_core.bot import Bot
from gsuid_core.models import Event

from ..utils import hint
from ..utils.api.model import KuroWavesUserInfo
from ..utils.database.models import WavesBind, WavesUser
from ..utils.error_reply import ERROR_CODE, WAVES_CODE_101, WAVES_CODE_103
from ..utils.waves_api import waves_api


async def add_cookie(ev: Event, ck: str) -> str:
    succ, platform, kuroWavesUserInfos = await waves_api.get_kuro_role_list(ck)
    if not succ or not isinstance(kuroWavesUserInfos, list):
        return hint.error_reply(code=WAVES_CODE_101)

    role_list = []
    for kuroWavesUserInfo in kuroWavesUserInfos:
        data = KuroWavesUserInfo.model_validate(kuroWavesUserInfo)

        # platform_list = ["h5", "ios"]
        # for platform in platform_list:
        #     succ, _ = await waves_api.refresh_data_for_platform(
        #         data.roleId, ck, data.serverId, platform
        #     )
        #     if succ:
        #         break
        # else:
        #     return hint.error_reply(code=WAVES_CODE_101)

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
                update_data={"cookie": ck, "status": "", "platform": platform},
            )
        else:
            await WavesUser.insert_data(
                ev.user_id, ev.bot_id, cookie=ck, uid=data.roleId
            )

        res = await WavesBind.insert_waves_uid(
            ev.user_id, ev.bot_id, data.roleId, ev.group_id, lenth_limit=9
        )
        if res == 0 or res == -2:
            await WavesBind.switch_uid_by_game(ev.user_id, ev.bot_id, data.roleId)

        # await refresh_char(data.roleId, ev.user_id, ck, is_self_ck=True)

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

    msg = []
    for uid in uid_list:
        ck = await waves_api.get_self_waves_ck(uid, ev.user_id)
        if not ck:
            continue
        msg.append(f"鸣潮uid: {uid}")
        msg.append(ck)

    if not msg:
        return "您当前未绑定token或者token已全部失效\n"

    return msg
