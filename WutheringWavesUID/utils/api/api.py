# waves

GAME_ID = 3
SERVER_ID = "76402e5b20be2c39f095a152090afddc"
SERVER_ID_NET = "919752ae5ea09c1ced910dd668a63ffb"

MAIN_URL = "https://api.kurobbs.com"
KURO_GET_CODE_URL = "https://api.kurobbs.com/user/getSmsCode"
GACHA_LOG_URL = "https://gmserver-api.aki-game2.com/gacha/record/query"
GACHA_NET_LOG_URL = "https://gmserver-api.aki-game2.net/gacha/record/query"

REQUEST_TOKEN = f"{MAIN_URL}/aki/roleBox/requestToken"
LOGIN_URL = f"{MAIN_URL}/user/sdkLoginForH5"
KURO_ROLE_URL = f"{MAIN_URL}/gamer/role/default"
ROLE_LIST_URL = f"{MAIN_URL}/gamer/role/list"
QUERY_USERID_URL = f"{MAIN_URL}/gamer/role/queryUserId"
REFRESH_URL = f"{MAIN_URL}/aki/roleBox/akiBox/refreshData"
MR_REFRESH_URL = f"{MAIN_URL}/gamer/widget/game3/refresh"
GAME_DATA_URL = f"{MAIN_URL}/gamer/widget/game3/getData"
BASE_DATA_URL = f"{MAIN_URL}/aki/roleBox/akiBox/baseData"
ROLE_DATA_URL = f"{MAIN_URL}/aki/roleBox/akiBox/roleData"
CALABASH_DATA_URL = f"{MAIN_URL}/aki/roleBox/akiBox/calabashData"
CHALLENGE_DATA_URL = f"{MAIN_URL}/aki/roleBox/akiBox/challengeDetails"
CHALLENGE_INDEX_URL = f"{MAIN_URL}/aki/roleBox/akiBox/challengeIndex"
EXPLORE_DATA_URL = f"{MAIN_URL}/aki/roleBox/akiBox/exploreIndex"
SIGNIN_URL = f"{MAIN_URL}/encourage/signIn/v2"
SIGNIN_TASK_LIST_URL = f"{MAIN_URL}/encourage/signIn/initSignInV2"
ROLE_DETAIL_URL = f"{MAIN_URL}/aki/roleBox/akiBox/getRoleDetail"
ANN_CONTENT_URL = f"{MAIN_URL}/forum/getPostDetail"
BBS_LIST = f"{MAIN_URL}/forum/getMinePost"
ANN_LIST_URL = f"{MAIN_URL}/forum/companyEvent/findEventList"
TOWER_INDEX_URL = f"{MAIN_URL}/aki/roleBox/akiBox/towerIndex"
TOWER_DETAIL_URL = f"{MAIN_URL}/aki/roleBox/akiBox/towerDataDetail"
SLASH_INDEX_URL = f"{MAIN_URL}/aki/roleBox/akiBox/slashIndex"
SLASH_DETAIL_URL = f"{MAIN_URL}/aki/roleBox/akiBox/slashDetail"
HOME_WIKI_DETAIL_URL = f"{MAIN_URL}/wiki/core/homepage/getPage"
WIKI_TREE_URL = f"{MAIN_URL}/wiki/core/catalogue/config/getTree"
WIKI_HOME_URL = f"{MAIN_URL}/wiki/core/homepage/getPage"
WIKI_DETAIL_URL = f"{MAIN_URL}/wiki/core/catalogue/item/getPage"
WIKI_ENTRY_DETAIL_URL = f"{MAIN_URL}/wiki/core/catalogue/item/getEntryDetail"


# refresh
CALCULATOR_REFRESH_DATA_URL = f"{MAIN_URL}/aki/calculator/refreshData"
# 角色列表 - 已经上线的角色列表
ONLINE_LIST_ROLE = f"{MAIN_URL}/aki/calculator/listRole"
# 武器列表 - 已经上线的武器列表
ONLINE_LIST_WEAPON = f"{MAIN_URL}/aki/calculator/listWeapon"
# 声骸列表 - 已经上线的声骸列表
ONLINE_LIST_PHANTOM = f"{MAIN_URL}/aki/calculator/listPhantom"

# 角色培养状态
ROLE_CULTIVATE_STATUS = f"{MAIN_URL}/aki/calculator/roleCultivateStatus"
# 角色培养成本
BATCH_ROLE_COST = f"{MAIN_URL}/aki/calculator/batchRoleCost"
# 武器培养成本
BATCH_WEAPON_COST = f"{MAIN_URL}/aki/calculator/batchWeaponCost"
# 声骸培养成本
BATCH_PHANTOM_COST = f"{MAIN_URL}/aki/calculator/batchPhantomCost"
# 已拥有角色
QUERY_OWNED_ROLE = f"{MAIN_URL}/aki/calculator/queryOwnedRole"


# 资源简报
PERIOD_LIST_URL = f"{MAIN_URL}/aki/resource/period/list"
MONTH_LIST_URL = f"{MAIN_URL}/aki/resource/month"
WEEK_LIST_URL = f"{MAIN_URL}/aki/resource/week"
VERSION_LIST_URL = f"{MAIN_URL}/aki/resource/version"


WIKI_CATALOGUE_MAP = {
    "共鸣者": "1105",
    "武器": "1106",
    "声骸": "1107",
    "合鸣效果": "1219",
    "敌人": "1158",
    "可合成道具": "1264",
    "道具合成图纸": "1265",
    "补给": "1217",
    "资源": "1161",
    "素材": "1218",
    "特殊道具": "1223",
    "活动": "1293",
}
