import asyncio
import copy
import json as j
import random
from typing import Any, Dict, List, Literal, Optional, Union

import httpx
from aiohttp import (
    ClientSession,
    ClientTimeout,
    ContentTypeError,
    FormData,
    TCPConnector,
)

from gsuid_core.logger import logger

from ...wutheringwaves_config import WutheringWavesConfig
from ..database.models import WavesUser
from ..error_reply import (
    WAVES_CODE_100,
    WAVES_CODE_101,
    WAVES_CODE_107,
    WAVES_CODE_998,
    WAVES_CODE_999,
)
from ..hint import error_reply
from ..util import generate_random_string, get_public_ip, timed_async_cache
from .api import (
    BASE_DATA_URL,
    BATCH_ROLE_COST,
    CALABASH_DATA_URL,
    CALCULATOR_REFRESH_DATA_URL,
    CHALLENGE_DATA_URL,
    CHALLENGE_INDEX_URL,
    EXPLORE_DATA_URL,
    GACHA_LOG_URL,
    GACHA_NET_LOG_URL,
    GAME_ID,
    KURO_ROLE_URL,
    LOGIN_URL,
    MONTH_LIST_URL,
    MR_REFRESH_URL,
    ONLINE_LIST_PHANTOM,
    ONLINE_LIST_ROLE,
    ONLINE_LIST_WEAPON,
    PERIOD_LIST_URL,
    QUERY_OWNED_ROLE,
    QUERY_USERID_URL,
    REFRESH_URL,
    REQUEST_TOKEN,
    ROLE_CULTIVATE_STATUS,
    ROLE_DATA_URL,
    ROLE_DETAIL_URL,
    ROLE_LIST_URL,
    SERVER_ID,
    SERVER_ID_NET,
    SLASH_DETAIL_URL,
    SLASH_INDEX_URL,
    TOWER_DETAIL_URL,
    TOWER_INDEX_URL,
    VERSION_LIST_URL,
    WEEK_LIST_URL,
    WIKI_DETAIL_URL,
    WIKI_ENTRY_DETAIL_URL,
    WIKI_HOME_URL,
    WIKI_TREE_URL,
)


async def _check_response(
    res: Union[Dict, int],
    roleId=None,
) -> tuple[bool, Union[Dict, str]]:
    if isinstance(res, dict):
        if res.get("code") == 200 and res.get("data"):
            return True, res["data"]

        if res.get("msg") and res.get("msg") == "请求成功":
            msg = f"\n鸣潮账号id: 【{roleId}】未绑定库街区!!!\n1.是否注册过库街区\n2.库街区能否查询当前鸣潮账号数据\n"
            return False, error_reply(None, msg)

        logger.warning(f"msg: {res.get('msg')} - data: {res.get('data')}")

        if res.get("msg") and ("重新登录" in res["msg"] or "登录已过期" in res["msg"]):
            return False, res.get("msg", "登录已过期")

        if res.get("msg") and "访问被阻断" in res["msg"]:
            return False, error_reply(WAVES_CODE_998)

        if res.get("msg"):
            return False, error_reply(WAVES_CODE_999)
    return False, error_reply(WAVES_CODE_999)


async def get_headers_h5():
    devCode = generate_random_string()
    header = {
        # "b-at": "",
        "source": "h5",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "devCode": devCode,
    }
    return header


async def get_headers_ios():
    ip = await get_public_ip()
    header = {
        # "b-at": "",
        "source": "ios",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko)  KuroGameBox/2.5.0",
        "devCode": f"{ip},  Mozilla/5.0 (iPhone; CPU iPhone OS 18_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko)  KuroGameBox/2.5.0",
    }
    return header


async def get_headers(ck: Optional[str] = None, platform: Optional[str] = None) -> Dict:
    if ck and not platform:
        try:
            waves_user = await WavesUser.select_data_by_cookie(cookie=ck)
            if waves_user:
                platform = waves_user.platform
        except Exception as _:
            pass

    if platform == "ios":
        return await get_headers_ios()
    else:
        return await get_headers_h5()


class WavesApi:
    ssl_verify = True

    def is_net(self, roleId):
        _temp = int(roleId)
        return _temp >= 200000000

    def get_server_id(self, roleId, serverId: Optional[str] = None):
        if serverId:
            return serverId
        if self.is_net(roleId):
            return SERVER_ID_NET
        else:
            return SERVER_ID

    async def get_ck_result(self, uid, user_id) -> tuple[bool, Optional[str]]:
        ck = await self.get_self_waves_ck(uid, user_id)
        if ck:
            return True, ck
        ck = await self.get_waves_random_cookie(uid, user_id)
        return False, ck

    # async def _get_ck(
    #     self, uid: str, user_id, mode: Literal["OWNER", "RANDOM"] = "RANDOM"
    # ) -> Optional[str]:
    #     if mode == "RANDOM":
    #         return await self.get_waves_random_cookie(uid, user_id)
    #     else:
    #         return await self.get_self_waves_ck(uid, user_id)

    async def get_self_waves_ck(self, uid: str, user_id) -> Optional[str]:
        cookie = await WavesUser.select_cookie(user_id, uid)
        if not cookie:
            return

        if not await WavesUser.cookie_validate(uid):
            return ""

        succ, data = await self.refresh_data(uid, cookie)
        if succ:
            return cookie

        if "重新登录" in data or "登录已过期" in data:
            await WavesUser.mark_invalid(cookie, "无效")
            return ""

        if isinstance(data, str):
            logger.warning(f"[{uid}] 获取ck失败: {data}")

        # 返回空串 表示绑定已失效
        return ""

    async def get_waves_random_cookie(self, uid: str, user_id: str) -> Optional[str]:
        if WutheringWavesConfig.get_config("WavesOnlySelfCk").data:
            return None

        # 公共ck 随机一个
        user_list = await WavesUser.get_waves_all_user()
        random.shuffle(user_list)
        ck_list = []
        times = 1
        for user in user_list:
            if not await WavesUser.cookie_validate(user.uid):
                continue
            succ, data = await self.refresh_data(user.uid, user.cookie)
            if not succ:
                if "重新登录" in data or "登录已过期" in data:
                    await WavesUser.mark_invalid(user.cookie, "无效")

                if "封禁" in data:
                    break

                if times <= 0:
                    break

                times -= 1
                continue

            ck_list.append(user.cookie)
            break

        if len(ck_list) > 0:
            return random.choices(ck_list, k=1)[0]

    async def get_kuro_role_info(
        self, token: str, kuro_uid: str = ""
    ) -> tuple[bool, Union[Dict, str]]:
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {}
        if kuro_uid:
            data.update({"queryUserId": kuro_uid})
        raw_data = await self._waves_request(KURO_ROLE_URL, "POST", header, data=data)
        if isinstance(raw_data, dict):
            if raw_data.get("code") == 200 and raw_data.get("data"):
                return True, raw_data["data"]

            if int(raw_data.get("code", 0)) == 500:
                # ? 服了
                await WavesUser.mark_invalid(token, "无效")
                return False, error_reply(WAVES_CODE_101)

            if raw_data.get("msg"):
                return False, raw_data["msg"]
        return False, error_reply(WAVES_CODE_999)

    async def get_kuro_role_list(
        self, token: str
    ) -> tuple[bool, str, Union[List, str, int]]:
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {"gameId": GAME_ID}

        err_msg = error_reply(WAVES_CODE_999)
        for i in ["h5", "ios"]:
            header["source"] = i
            raw_data = await self._waves_request(
                ROLE_LIST_URL, "POST", header, data=data
            )
            if isinstance(raw_data, dict):
                if raw_data.get("code") == 200 and raw_data.get("data"):
                    return True, i, raw_data["data"]

                logger.warning(f"get_kuro_role_list -> msg: {raw_data}")
                if raw_data.get("msg"):
                    err_msg = raw_data["msg"]
                    continue
        return False, "", err_msg

    async def get_game_role_info(
        self, token: str, gameId: Union[str, int] = GAME_ID, kuro_uid: str = ""
    ) -> tuple[bool, Union[Dict, str, int]]:
        succ, data = await self.get_kuro_role_info(token, kuro_uid)
        if not succ or not isinstance(data, Dict):
            return succ, data
        for role in data["defaultRoleList"]:
            if role["gameId"] == gameId:
                return True, role
        return False, WAVES_CODE_100

    async def get_daily_info(
        self, roleId: str, token: str, gameId: Union[str, int] = GAME_ID
    ) -> tuple[bool, Union[Dict, str]]:
        """每日"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "type": "1",
            "sizeType": "2",
            "gameId": gameId,
            "serverId": self.get_server_id(roleId),
            "roleId": roleId,
        }
        raw_data = await self._waves_request(
            MR_REFRESH_URL,
            "POST",
            header,
            data=data,
        )
        return await _check_response(raw_data)

    async def refresh_data(
        self, roleId: str, token: str, serverId: Optional[str] = None
    ) -> tuple[bool, Union[Dict, str]]:
        """刷新数据"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "gameId": GAME_ID,
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
        }
        raw_data = await self._waves_request(REFRESH_URL, "POST", header, data=data)
        return await _check_response(raw_data, roleId)

    async def refresh_query_data(
        self, roleId: str, token: str, serverId: Optional[str] = None
    ) -> tuple[bool, Union[Dict, str]]:
        """刷新数据"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "gameId": GAME_ID,
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
        }
        raw_data = await self._waves_request(
            QUERY_USERID_URL, "POST", header, data=data
        )
        return await _check_response(raw_data, roleId)

    async def refresh_data_for_platform(
        self,
        roleId: str,
        token: str,
        serverId: Optional[str] = None,
        platform: str = "h5",
    ) -> tuple[bool, Union[Dict, str]]:
        """刷新数据"""
        header = copy.deepcopy(await get_headers(token, platform))
        header.update({"token": token})
        data = {
            "gameId": GAME_ID,
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
        }
        raw_data = await self._waves_request(REFRESH_URL, "POST", header, data=data)
        return await _check_response(raw_data, roleId)

    async def get_base_info(
        self, roleId: str, token: str, serverId: Optional[str] = None
    ) -> tuple[bool, Union[Dict, str]]:
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "gameId": GAME_ID,
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
        }
        raw_data = await self._waves_request(BASE_DATA_URL, "POST", header, data=data)
        # flag, res = await _check_response(raw_data)
        # if flag and res.get('creatTime') is None:
        #     return False, error_reply(WAVES_CODE_106)
        # return flag, res
        return await _check_response(raw_data, roleId)

    async def get_role_info(
        self, roleId: str, token: str, serverId: Optional[str] = None
    ) -> tuple[bool, Union[Dict, str]]:
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "gameId": GAME_ID,
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
        }
        raw_data = await self._waves_request(ROLE_DATA_URL, "POST", header, data=data)
        flag, res = await _check_response(raw_data, roleId)
        if flag and isinstance(res, Dict) and res.get("roleList") is None:
            return False, error_reply(WAVES_CODE_107)
        return flag, res

    async def get_tree(self) -> Union[Dict, int]:
        header = copy.deepcopy(await get_headers())
        header.update({"wiki_type": "9"})
        data = {"devcode": ""}
        return await self._waves_request(WIKI_TREE_URL, "POST", header, data=data)

    async def get_wiki(self, catalogueId: str) -> tuple[bool, Union[Dict, str]]:
        header = copy.deepcopy(await get_headers())
        header.update({"wiki_type": "9"})
        data = {"catalogueId": catalogueId, "limit": 1000}
        raw_data = await self._waves_request(WIKI_DETAIL_URL, "POST", header, data=data)
        return await _check_response(raw_data)

    async def get_role_detail_info(
        self, charId: str, roleId: str, token: str, serverId: Optional[str] = None
    ) -> tuple[bool, Union[Dict, str]]:
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        bat = await self.get_request_token(roleId, token)
        if bat:
            header.update({"b-at": bat})
            # logger.info(f"[{roleId}] 获取到b-at: {bat}")
        data = {
            "gameId": GAME_ID,
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
            "channelId": "19",
            "countryCode": "1",
            "id": charId,
        }
        raw_data = await self._waves_request(ROLE_DETAIL_URL, "POST", header, data=data)
        return await _check_response(raw_data)

    async def get_calabash_data(
        self, roleId: str, token: str, serverId: Optional[str] = None
    ) -> tuple[bool, Union[Dict, str]]:
        """数据坞"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "gameId": GAME_ID,
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
        }
        raw_data = await self._waves_request(
            CALABASH_DATA_URL, "POST", header, data=data
        )
        return await _check_response(raw_data, roleId)

    async def get_explore_data(
        self,
        roleId: str,
        token: str,
        serverId: Optional[str] = None,
        countryCode: str = "1",
    ) -> tuple[bool, Union[Dict, str]]:
        """探索度"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "gameId": GAME_ID,
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
            "countryCode": countryCode,
        }
        raw_data = await self._waves_request(
            EXPLORE_DATA_URL, "POST", header, data=data
        )
        return await _check_response(raw_data, roleId)

    async def get_challenge_data(
        self, roleId: str, token: str, serverId: Optional[str] = None
    ) -> tuple[bool, Union[Dict, str]]:
        """全息"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "gameId": GAME_ID,
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
        }
        raw_data = await self._waves_request(
            CHALLENGE_DATA_URL, "POST", header, data=data
        )
        return await _check_response(raw_data, roleId)

    async def get_challenge_index(
        self, roleId: str, token: str, serverId: Optional[str] = None
    ) -> tuple[bool, Union[Dict, str]]:
        """全息"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "gameId": GAME_ID,
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
        }
        raw_data = await self._waves_request(
            CHALLENGE_INDEX_URL, "POST", header, data=data
        )
        return await _check_response(raw_data, roleId)

    async def get_abyss_data(
        self, roleId: str, token: str, serverId: Optional[str] = None
    ) -> Union[Dict, int]:
        """深渊"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "gameId": GAME_ID,
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
        }
        return await self._waves_request(TOWER_DETAIL_URL, "POST", header, data=data)

    async def get_abyss_index(
        self, roleId: str, token: str, serverId: Optional[str] = None
    ) -> Union[Dict, int]:
        """深渊"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "gameId": GAME_ID,
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
        }
        return await self._waves_request(TOWER_INDEX_URL, "POST", header, data=data)

    async def get_slash_index(
        self, roleId: str, token: str, serverId: Optional[str] = None
    ) -> Union[Dict, int]:
        """冥海"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "gameId": GAME_ID,
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
        }
        return await self._waves_request(SLASH_INDEX_URL, "POST", header, data=data)

    async def get_slash_detail(
        self, roleId: str, token: str, serverId: Optional[str] = None
    ) -> Union[Dict, int]:
        """冥海"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "gameId": GAME_ID,
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
        }
        return await self._waves_request(SLASH_DETAIL_URL, "POST", header, data=data)

    @timed_async_cache(
        86400,
        lambda x: isinstance(x, str) and x != "",
    )
    async def get_request_token(
        self, roleId: str, token: str, serverId: Optional[str] = None
    ) -> Optional[str]:
        """请求token"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
        }
        raw_data = await self._waves_request(REQUEST_TOKEN, "POST", header, data=data)
        if isinstance(raw_data, dict) and raw_data.get("code") == 200:
            return raw_data.get("data", {}).get("accessToken", "")
        return ""

    async def calculator_refresh_data(
        self,
        roleId: str,
        token: str,
        serverId: Optional[str] = None,
    ) -> tuple[bool, Union[Dict, str]]:
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
        }
        raw_data = await self._waves_request(
            CALCULATOR_REFRESH_DATA_URL, "POST", header, data=data
        )
        return await _check_response(raw_data, roleId)

    @timed_async_cache(
        86400,
        lambda x: x[0] and isinstance(x[1], (dict, list)),
    )
    async def get_online_list_role(self, token: str) -> tuple[bool, Union[Dict, str]]:
        """所有的角色列表"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {}
        raw_data = await self._waves_request(
            ONLINE_LIST_ROLE, "POST", header, data=data
        )
        return await _check_response(raw_data)

    @timed_async_cache(
        86400,
        lambda x: x[0] and isinstance(x[1], (dict, list)),
    )
    async def get_online_list_weapon(self, token: str) -> tuple[bool, Union[Dict, str]]:
        """所有的武器列表"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {}
        raw_data = await self._waves_request(
            ONLINE_LIST_WEAPON, "POST", header, data=data
        )
        return await _check_response(raw_data)

    @timed_async_cache(
        86400,
        lambda x: x[0] and isinstance(x[1], (dict, list)),
    )
    async def get_online_list_phantom(
        self, token: str
    ) -> tuple[bool, Union[Dict, str]]:
        """所有的声骸列表"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {}
        raw_data = await self._waves_request(
            ONLINE_LIST_PHANTOM, "POST", header, data=data
        )
        return await _check_response(raw_data)

    async def get_owned_role(
        self,
        roleId: str,
        token: str,
        serverId: Optional[str] = None,
    ) -> tuple[bool, Union[Dict, str]]:
        """已拥有角色"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
        }
        raw_data = await self._waves_request(
            QUERY_OWNED_ROLE, "POST", header, data=data
        )
        return await _check_response(raw_data)

    async def get_develop_role_cultivate_status(
        self,
        roleId: str,
        token: str,
        char_ids: List[str],
        serverId: Optional[str] = None,
    ) -> tuple[bool, Union[Dict, str]]:
        """角色培养状态"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
            "ids": ",".join(char_ids),
        }
        raw_data = await self._waves_request(
            ROLE_CULTIVATE_STATUS, "POST", header, data=data
        )
        return await _check_response(raw_data, roleId)

    async def get_batch_role_cost(
        self,
        roleId: str,
        token: str,
        content: List[Any],
        serverId: Optional[str] = None,
    ) -> tuple[bool, Union[Dict, str]]:
        """角色培养成本"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
            "content": j.dumps(content),
        }
        raw_data = await self._waves_request(BATCH_ROLE_COST, "POST", header, data=data)
        return await _check_response(raw_data, roleId)

    async def get_period_list(
        self,
        roleId: str,
        token: str,
    ) -> tuple[bool, Union[Dict, str]]:
        """资源简报列表"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        raw_data = await self._waves_request(PERIOD_LIST_URL, "GET", header)
        return await _check_response(raw_data, roleId)

    async def get_period_detail(
        self,
        type: Literal["month", "week", "version"],
        period: Union[str, int],
        roleId: str,
        token: str,
        serverId: Optional[str] = None,
    ) -> tuple[bool, Union[Dict, str]]:
        """资源简报详情"""
        header = copy.deepcopy(await get_headers(token))
        header.update({"token": token})
        data = {
            "serverId": self.get_server_id(roleId, serverId),
            "roleId": roleId,
            "period": period,
        }
        if type == "month":
            url = MONTH_LIST_URL
        elif type == "week":
            url = WEEK_LIST_URL
        elif type == "version":
            url = VERSION_LIST_URL
        raw_data = await self._waves_request(url, "POST", header, data=data)
        return await _check_response(raw_data, roleId)

    async def get_gacha_log(
        self,
        cardPoolType: str,
        recordId: str,
        roleId: str,
        serverId: Optional[str] = None,
    ):
        """抽卡记录"""
        header = {"Content-Type": "application/json;charset=UTF-8"}
        data = {
            "playerId": roleId,
            "cardPoolType": cardPoolType,
            "serverId": self.get_server_id(roleId, serverId),
            "languageCode": "zh-Hans",
            "recordId": recordId,
        }
        url = GACHA_NET_LOG_URL if self.is_net(roleId) else GACHA_LOG_URL
        return await self._waves_request(url, "POST", header, json=data)

    async def _waves_request(
        self,
        url: str,
        method: Literal["GET", "POST"] = "GET",
        header=None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Union[FormData, Dict[str, Any]]] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> Union[Dict, int]:
        if header is None:
            header = await get_headers()

        for attempt in range(max_retries):
            try:
                async with ClientSession(
                    connector=TCPConnector(verify_ssl=self.ssl_verify)
                ) as client:
                    async with client.request(
                        method,
                        url=url,
                        headers=header,
                        params=params,
                        json=json,
                        data=data,
                        timeout=ClientTimeout(total=10),
                    ) as resp:
                        try:
                            raw_data = await resp.json()
                        except ContentTypeError:
                            _raw_data = await resp.text()
                            raw_data = {"code": WAVES_CODE_999, "data": _raw_data}
                        if (
                            isinstance(raw_data, dict)
                            and "data" in raw_data
                            and isinstance(raw_data["data"], str)
                        ):
                            try:
                                des_data = j.loads(raw_data["data"])
                                raw_data["data"] = des_data
                            except Exception:
                                pass
                        logger.debug(f"url:[{url}] raw_data:{raw_data}")
                        return raw_data
            except Exception as e:
                logger.exception(f"url:[{url}] attempt {attempt + 1} failed", e)
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)

        return {"code": WAVES_CODE_999, "data": "请求服务器失败"}


class KuroLogin:
    ssl_verify = True

    async def login(self, mobile: int | str, code: str):
        header = copy.deepcopy(await get_headers())
        data = {"mobile": mobile, "code": code}
        return await self._kuro_request(LOGIN_URL, "POST", header, data=data)

    async def _kuro_request(
        self,
        url: str,
        method: Literal["GET", "POST"] = "GET",
        header=None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Union[FormData, Dict[str, Any]]] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> Union[Dict, int]:
        if header is None:
            header = await get_headers()

        for attempt in range(max_retries):
            try:
                async with ClientSession(
                    connector=TCPConnector(verify_ssl=self.ssl_verify)
                ) as client:
                    async with client.request(
                        method,
                        url=url,
                        headers=header,
                        params=params,
                        json=json,
                        data=data,
                        timeout=ClientTimeout(total=10),
                    ) as resp:
                        try:
                            raw_data = await resp.json()
                        except ContentTypeError:
                            _raw_data = await resp.text()
                            raw_data = {"code": WAVES_CODE_999, "data": _raw_data}
                        logger.debug(f"url:{url} raw_data:{raw_data}")
                        return raw_data
            except Exception as e:
                logger.exception(f"url:[{url}] attempt {attempt + 1} failed", e)
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)

        return {"code": WAVES_CODE_999, "data": "请求服务器失败"}


class Wiki:
    _HEADER = {
        "source": "h5",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "wiki_type": "9",
    }

    async def get_wiki_home(self):
        headers = copy.deepcopy(self._HEADER)
        async with httpx.AsyncClient(timeout=None) as client:
            res = await client.post(WIKI_HOME_URL, headers=headers, timeout=10)
            return res.json()

    async def get_wiki_catalogue(self, catalogueId: str):
        headers = copy.deepcopy(self._HEADER)
        data = {"catalogueId": catalogueId, "limit": 1000}
        async with httpx.AsyncClient(timeout=None) as client:
            res = await client.post(
                WIKI_DETAIL_URL, headers=headers, data=data, timeout=10
            )
            return res.json()

    async def get_entry_id(self, name: str, catalogueId: str):
        catalogue_data = await self.get_wiki_catalogue(catalogueId)
        if catalogue_data["code"] != 200:
            return
        char_record = next(
            (
                i
                for i in catalogue_data["data"]["results"]["records"]
                if i["name"] == name
            ),
            None,
        )
        # logger.debug(f'【鸣潮WIKI】 名字:【{name}】: {char_record}')
        if not char_record:
            return

        return char_record["entryId"]

    async def get_entry_detail_by_name(self, name: str, catalogueId: str):
        entry_id = await self.get_entry_id(name, catalogueId)
        if not entry_id:
            return

        headers = copy.deepcopy(self._HEADER)
        data = {"id": entry_id}
        async with httpx.AsyncClient(timeout=None) as client:
            res = await client.post(
                WIKI_ENTRY_DETAIL_URL, headers=headers, data=data, timeout=10
            )
            return res.json()

    async def get_entry_detail(self, entry_id: str):
        headers = copy.deepcopy(self._HEADER)
        data = {"id": entry_id}
        async with httpx.AsyncClient(timeout=None) as client:
            res = await client.post(
                WIKI_ENTRY_DETAIL_URL, headers=headers, data=data, timeout=10
            )
            return res.json()
