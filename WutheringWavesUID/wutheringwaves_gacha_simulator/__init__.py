import random
import json
from collections import defaultdict
import statistics
import asyncio
import os
import time

from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.logger import logger

# --- 全局配置与数据 ---
try:
    script_dir_for_json = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir_for_json = os.getcwd()
PROB_DIST_FILENAME = os.path.join(script_dir_for_json, "pity_distribution.json")

PROB_DIST_NORMALIZED = []
EMOJI_NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"] 

# --- 用户状态管理 (会话隔离) ---
user_states = {} 

sv_ww_gacha_simulator = SV(
    name='鸣潮抽卡模拟计算器',
    pm=6, 
    priority=5,
    enabled=True,
    area='ALL'
)

INTERACTION_TIMEOUT = 30 
DEFAULT_SIMULATIONS = 100000
USER_STATE_TIMEOUT_SECONDS = 30 

# ... (load_probability_distribution, gacha sim core functions, formatting functions, input helpers remain IDENTICAL to your last provided version) ...
# --- 工具函数 ---
def load_probability_distribution(json_file_path=PROB_DIST_FILENAME):
    global PROB_DIST_NORMALIZED
    logger.info(f"ww_gacha_simulator (Debug): Current Working Directory is: {os.getcwd()}")
    logger.info(f"ww_gacha_simulator (Debug): Attempting to load probability file from: {json_file_path}")

    try:
        with open(json_file_path, 'r') as f:
            PROB_DIST_NORMALIZED = json.load(f)
        logger.info(f"ww_gacha_simulator: 已成功从 {json_file_path} 加载概率分布 ({len(PROB_DIST_NORMALIZED)} 个元素)。")
        if not isinstance(PROB_DIST_NORMALIZED, list) or len(PROB_DIST_NORMALIZED) != 80:
            logger.error(f"ww_gacha_simulator: {json_file_path} 数据格式不正确或长度不为80。")
            PROB_DIST_NORMALIZED = []
            return False
        return True
    except FileNotFoundError:
        logger.error(f"ww_gacha_simulator: 概率分布文件 {json_file_path} 未找到。")
        PROB_DIST_NORMALIZED = []
        return False
    except json.JSONDecodeError:
        logger.error(f"ww_gacha_simulator: 解析 {json_file_path} JSON数据出错。")
        PROB_DIST_NORMALIZED = []
        return False
    except Exception as e:
        logger.error(f"ww_gacha_simulator: 加载概率分布 ({json_file_path}) 时发生未知错误: {e}")
        PROB_DIST_NORMALIZED = []
        return False


# --- 核心模拟辅助函数 ---
def get_pulls_for_next_5star():
    global PROB_DIST_NORMALIZED
    if not PROB_DIST_NORMALIZED:
        logger.error("ww_gacha_simulator: 严重错误: 概率分布未加载 (get_pulls_for_next_5star)。")
        raise ValueError("概率分布未加载，无法进行模拟。")
    u = random.random()
    cumulative_prob = 0
    for i, prob in enumerate(PROB_DIST_NORMALIZED):
        cumulative_prob += prob
        if u < cumulative_prob:
            return i + 1
    return len(PROB_DIST_NORMALIZED)

def simulate_one_featured_character(current_is_guaranteed):
    total_pulls = 0
    is_guaranteed = current_is_guaranteed
    while True:
        pulls_for_5star = get_pulls_for_next_5star()
        total_pulls += pulls_for_5star
        if is_guaranteed:
            return total_pulls, False
        else:
            if random.random() < 0.5:
                return total_pulls, False
            else:
                is_guaranteed = True

def simulate_one_featured_weapon():
    return get_pulls_for_next_5star()


# --- 核心模拟逻辑 ---
def calculate_expected_pulls(target_featured_chars, target_featured_weapons, num_simulations):
    total_pulls_across_simulations = 0
    for _ in range(num_simulations):
        sim_total_pulls = 0
        current_fc = 0 
        current_fw = 0 
        char_is_guaranteed = False
        
        if target_featured_chars > 0 and current_fc < 1 :
            pulls, char_is_guaranteed = simulate_one_featured_character(char_is_guaranteed)
            sim_total_pulls += pulls
            current_fc += 1
        
        if target_featured_weapons > 0 and current_fw < 1:
            pulls = simulate_one_featured_weapon()
            sim_total_pulls += pulls
            current_fw += 1
            
        while current_fc < target_featured_chars:
            pulls, char_is_guaranteed = simulate_one_featured_character(char_is_guaranteed)
            sim_total_pulls += pulls
            current_fc += 1
            
        while current_fw < target_featured_weapons:
            pulls = simulate_one_featured_weapon()
            sim_total_pulls += pulls
            current_fw += 1
            
        total_pulls_across_simulations += sim_total_pulls
    if num_simulations == 0: return 0.0
    return total_pulls_across_simulations / num_simulations

def _get_outcome_for_budget(pull_budget):
    pulls_remaining = pull_budget
    current_fc = 0  
    current_fw = 0  
    char_is_guaranteed = False

    if pulls_remaining > 0 and current_fc == 0:
        cost_c0, guaranteed_after_c0 = simulate_one_featured_character(char_is_guaranteed)
        if pulls_remaining >= cost_c0:
            pulls_remaining -= cost_c0
            current_fc = 1 
            char_is_guaranteed = guaranteed_after_c0
        else:
            return current_fc, current_fw 

    if current_fc >= 1 and pulls_remaining > 0 and current_fw == 0:
        cost_r1 = simulate_one_featured_weapon()
        if pulls_remaining >= cost_r1:
            pulls_remaining -= cost_r1
            current_fw = 1 

    if current_fc >= 1: 
        while current_fc < 7 and pulls_remaining > 0: 
            cost_next_char, guaranteed_after_next_char = simulate_one_featured_character(char_is_guaranteed)
            if pulls_remaining >= cost_next_char:
                pulls_remaining -= cost_next_char
                current_fc += 1
                char_is_guaranteed = guaranteed_after_next_char
            else:
                break 

    if current_fc >= 1: 
        while current_fw < 5 and pulls_remaining > 0: 
            cost_next_weapon = simulate_one_featured_weapon()
            if pulls_remaining >= cost_next_weapon:
                pulls_remaining -= cost_next_weapon
                current_fw += 1
            else:
                break 
                
    return current_fc, current_fw

def get_top_outcomes(total_pull_budget, num_simulations):
    outcomes_counter = defaultdict(int)
    for _ in range(num_simulations):
        fc, fw = _get_outcome_for_budget(total_pull_budget)
        outcomes_counter[(fc, fw)] += 1
        
    if num_simulations == 0: return [] 
    sorted_outcomes = sorted(outcomes_counter.items(), key=lambda item: item[1], reverse=True)
    top_5 = []
    for i in range(min(len(EMOJI_NUMS), len(sorted_outcomes))): 
        outcome_tuple, count = sorted_outcomes[i] 
        probability = count / num_simulations
        top_5.append({'outcome (FC, FW)': outcome_tuple, 'probability': probability, 'count': count})
    return top_5

def simulate_for_budget_outcome(pull_budget):
    return _get_outcome_for_budget(pull_budget)


# --- 分析结果格式化函数 ---
def format_mode1_analysis_results(history_list_mode1, num_sim_per_run):
    num_reruns = len(history_list_mode1)
    output_lines = [f"--- 期望抽数结果稳定性分析 (基于 {num_reruns} 次运行, 每次 {num_sim_per_run:,} 次模拟) ---"]
    if not history_list_mode1:
        output_lines.append("   没有历史数据可供分析。")
        return "\n".join(output_lines)
    for i, result in enumerate(history_list_mode1):
        output_lines.append(f"   第 {i+1} 次运行的期望抽数: {result:.2f}")
    if num_reruns == 1:
        output_lines.append("   (至少需要两次运行才能进行更详细的稳定性分析)")
    elif num_reruns > 1:
        mean_of_means = statistics.mean(history_list_mode1)
        std_dev_of_means = statistics.stdev(history_list_mode1)
        min_mean = min(history_list_mode1)
        max_mean = max(history_list_mode1)
        output_lines.append(f"\n   多次运行的平均期望抽数: {mean_of_means:.2f}")
        output_lines.append(f"   期望抽数的标准差: {std_dev_of_means:.2f}")
        output_lines.append(f"   观察到的最小期望抽数: {min_mean:.2f}")
        output_lines.append(f"   观察到的最大期望抽数: {max_mean:.2f}")
        if mean_of_means > 0: 
            relative_std_dev = (std_dev_of_means / mean_of_means) * 100
            output_lines.append(f"   相对标准差 (变异系数): {relative_std_dev:.2f}%")
            if relative_std_dev < 1: output_lines.append("   结论: 结果稳定性非常好。")
            elif relative_std_dev < 5: output_lines.append("   结论: 结果稳定性较好。")
            elif relative_std_dev < 10: output_lines.append("   结论: 结果稳定性一般。")
            else: output_lines.append("   结论: 结果稳定性较差。可增加运行次数。") 
        else: output_lines.append("   结论: 平均期望抽数为0。")
    return "\n".join(output_lines)

def format_mode2_analysis_results(history_list_mode2_top5s, num_sim_per_run):
    global EMOJI_NUMS 
    num_reruns = len(history_list_mode2_top5s)
    output_lines = [] 

    if not history_list_mode2_top5s:
        return "" 

    aggregated_counts = defaultdict(int)
    valid_reruns_count = 0
    for run_top_5_list in history_list_mode2_top5s:
        if run_top_5_list: 
            valid_reruns_count +=1
            for res_dict in run_top_5_list: 
                outcome_tuple = tuple(res_dict['outcome (FC, FW)'])
                aggregated_counts[outcome_tuple] += res_dict['count']
    
    total_simulations_all_valid_reruns = valid_reruns_count * num_sim_per_run

    if valid_reruns_count > 0 and total_simulations_all_valid_reruns > 0:
        output_lines.append(f"\n--- 所有 {valid_reruns_count} 次有效运行的聚合Top结果 (总模拟 {total_simulations_all_valid_reruns:,} 次) ---")
        aggregated_sorted_outcomes = sorted(aggregated_counts.items(), key=lambda item: item[1], reverse=True)
        for i in range(min(len(EMOJI_NUMS), len(aggregated_sorted_outcomes))): 
            outcome_tuple, total_count = aggregated_sorted_outcomes[i]
            overall_probability = total_count / total_simulations_all_valid_reruns
            
            fc_total = outcome_tuple[0] 
            fw_total = outcome_tuple[1] 
            
            if fc_total > 0:
                a = fc_total - 1 
                outcome_display_str = f"{a}+{fw_total}"
            else: 
                outcome_display_str = f"0角色, {fw_total}武器"

            emoji_num = EMOJI_NUMS[i]
            output_lines.append(f"   {emoji_num} {outcome_display_str} - 总体概率: {overall_probability:.2%} (计数: {total_count:,})")
        
        # MODIFIED: Updated rerun hint
        if valid_reruns_count == 1:
            pass
        elif valid_reruns_count > 1:
            output_lines.append("\n稳定性说明: 比较聚合结果与单次运行结果.") 
    
    return "\n".join(output_lines)


# --- GsCore 输入辅助函数 ---
async def gscore_get_int_input(bot: Bot, ev: Event, prompt_message: str, default_value=None, non_negative=True, strictly_positive=False, max_value=None, timeout_seconds=INTERACTION_TIMEOUT):
    at_sender = True if ev.group_id else False
    while True:
        await bot.send(f"{prompt_message}\n(回复 'c' 取消)", at_sender=at_sender)
        resp = None 
        try:
            resp = await bot.receive_resp(timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.debug(f"ww_gacha_simulator: Timeout waiting for user input for: {prompt_message} from user {ev.user_id}")
            return None 

        if resp is None: 
            logger.debug(f"ww_gacha_simulator: receive_resp returned None for: {prompt_message} from user {ev.user_id}")
            return None 
        
        input_str = resp.text.strip()
        if input_str.lower() == 'c':
            await bot.send("操作已取消。", at_sender=at_sender)
            return None
        try:
            if not input_str:
                if default_value is not None:
                    value = default_value
                else:
                    await bot.send("输入不能为空，请重新输入。",at_sender=at_sender)
                    continue
            else:
                value = int(input_str)

            if non_negative and value < 0:
                await bot.send("输入值不能为负数，请重新输入。", at_sender=at_sender)
                continue
            if strictly_positive and value <= 0:
                await bot.send("输入值必须为正数且大于0，请重新输入。", at_sender=at_sender)
                continue
            if max_value is not None and value > max_value:
                await bot.send(f"输入值过大 (最大允许: {max_value:,})，请重新输入。", at_sender=at_sender)
                continue
            return value
        except ValueError:
            await bot.send("输入无效，请输入一个整数。", at_sender=at_sender)

async def gscore_get_fc_fw_input(bot: Bot, ev: Event, prompt_message: str, timeout_seconds=INTERACTION_TIMEOUT):
    at_sender = True if ev.group_id else False
    while True:
        await bot.send(f"{prompt_message}\n(回复 'c' 取消)", at_sender=at_sender)
        resp = None
        try:
            resp = await bot.receive_resp(timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.debug(f"ww_gacha_simulator: Timeout waiting for FC+FW input from user {ev.user_id}")
            return None

        if resp is None:
            logger.debug(f"ww_gacha_simulator: FC+FW input receive_resp returned None for user {ev.user_id}")
            return None
        
        input_str = resp.text.strip().lower()
        if input_str == 'c':
            await bot.send("操作已取消。", at_sender=at_sender)
            return None

        parts = input_str.split('+')
        if len(parts) == 2:
            try:
                a = int(parts[0]) 
                b = int(parts[1]) 

                if not (0 <= a <= 6 and 0 <= b <= 5): 
                    await bot.send("输入值超出范围。共鸣链数为 0-6，武器数为 0-5。请重新输入。", at_sender=at_sender)
                    continue
                
                target_fc = a + 1 
                target_fw = b       
                return target_fc, target_fw
            except ValueError:
                await bot.send("输入格式错误。请输入如 `0+1` 的数字格式。", at_sender=at_sender)
        else:
            await bot.send("输入格式错误。请输入 `共鸣链数+武器数` 的格式，例如 `0+1`。", at_sender=at_sender)


# --- 主要插件命令处理函数 ---
SIMULATOR_COMMANDS = ('抽卡模拟', '模拟抽卡', '抽卡计算','模拟')
SIMULATOR_HELP_COMMANDS = ('抽卡模拟帮助', '模拟帮助', '抽卡计算帮助')
MAIN_COMMAND_EXAMPLE = SIMULATOR_COMMANDS[0] 

@sv_ww_gacha_simulator.on_fullmatch(SIMULATOR_COMMANDS, block=True)
async def handle_gacha_simulator_sub_command(bot: Bot, ev: Event):
    global EMOJI_NUMS 
    user_id = str(ev.user_id)
    if not user_id:
        logger.error("ww_gacha_simulator: 无法从事件中获取 user_id。")
        await bot.send("无法识别用户身份，操作失败。")
        return

    current_time = time.time()
    if user_id not in user_states:
        logger.info(f"ww_gacha_simulator (User: {user_id}, Debug): 为用户 {user_id} 初始化新的状态。")
        user_states[user_id] = {
            'last_run_config': None,
            'current_config_signature': None,
            'rerun_history_mode1': [],
            'rerun_history_mode2': [],
            'last_activity_ts': current_time 
        }
    current_user_state = user_states[user_id]
    at_sender = True if ev.group_id else False

    if current_user_state.get('last_run_config') or \
       current_user_state.get('rerun_history_mode1') or \
       current_user_state.get('rerun_history_mode2'):
        if (current_time - current_user_state.get('last_activity_ts', current_time - (USER_STATE_TIMEOUT_SECONDS + 1)) > USER_STATE_TIMEOUT_SECONDS):
            logger.info(f"ww_gacha_simulator (User: {user_id}, Debug): 用户会话超时。清除旧配置和历史。")
            current_user_state['last_run_config'] = None
            current_user_state['current_config_signature'] = None
            current_user_state['rerun_history_mode1'] = []
            current_user_state['rerun_history_mode2'] = []

    if not PROB_DIST_NORMALIZED:
        if not load_probability_distribution():
            await bot.send(f"错误: 概率分布文件加载失败。模拟器无法运行。")
            return

    logger.info(f"ww_gacha_simulator (User: {user_id}, Debug): Handler invoked by fullmatch. Matched command: '{ev.command}'. ev.text: '{ev.text}'")

    action_mode_to_run = None
    params_to_run = {}
    num_sims_to_run = DEFAULT_SIMULATIONS
    
    perform_rerun = False
    if current_user_state.get('last_run_config'):
        await bot.send("检测到您有上次的模拟配置。\n是否直接以重新运行上次配置? (回复 `y` 或 `n`, `q`退出)", at_sender=at_sender)
        rerun_choice_resp = None
        try:
            rerun_choice_resp = await bot.receive_resp(timeout=INTERACTION_TIMEOUT)
        except asyncio.TimeoutError:
            logger.debug(f"ww_gacha_simulator (User: {user_id}): Timeout waiting for rerun choice.")
            return

        if rerun_choice_resp:
            choice = rerun_choice_resp.text.strip().lower()
            if choice == 'y' or choice == 'yes':
                perform_rerun = True
                action_mode_to_run = current_user_state['last_run_config']["mode"]
                params_to_run = current_user_state['last_run_config']["params"]
                current_user_state['last_run_config']["num_simulations"] = DEFAULT_SIMULATIONS 
                await bot.send(f"--- 重新运行上次模拟 (模式 {action_mode_to_run}, 模拟次数 {num_sims_to_run:,}) ---", at_sender=at_sender)
            elif choice == 'q' or choice == 'quit' or choice == 'exit' or choice == 'c' or choice == 'cancel':
                await bot.send("操作已取消。", at_sender=at_sender)
                return
        else: 
             return
    
    if not perform_rerun:
        logger.info(f"ww_gacha_simulator (User: {user_id}, Debug): Entering 'new simulation config' block (not a rerun).")
        await bot.send(f"--- {sv_ww_gacha_simulator.name} ---\n请选择模式:\n1. 计算给定目标的期望抽数 \n2. 模拟N抽结果 (Top 5)\n3. 计算预算内达成目标的成功率\n(回复 'q' 退出)", at_sender=at_sender)
        mode_resp = None
        try:
            mode_resp = await bot.receive_resp(timeout=INTERACTION_TIMEOUT)
        except asyncio.TimeoutError:
            logger.debug(f"ww_gacha_simulator (User: {user_id}): Timeout waiting for mode selection.")
            return 

        if mode_resp is None: 
            logger.debug(f"ww_gacha_simulator (User: {user_id}): Mode selection returned None or was cancelled.")
            return
        
        mode_input_str = mode_resp.text.strip().lower()
        if mode_input_str in ['q', 'quit', 'exit', 'c', 'cancel']:
            await bot.send("操作已取消。", at_sender=at_sender)
            return
        
        if mode_input_str not in ['1', '2', '3']:
            await bot.send("无效的模式选择。", at_sender=at_sender)
            return
        temp_action_mode = mode_input_str 
        
        temp_run_params = {}
        if temp_action_mode == '1':
            fc_fw_result = await gscore_get_fc_fw_input(bot, ev, "请输入目标配置(例如'0+1')")
            if fc_fw_result is None: return 
            target_fc_val, target_fw_val = fc_fw_result
            temp_run_params = {"target_fc": target_fc_val, "target_fw": target_fw_val}
        elif temp_action_mode == '2':
            pull_budget_val = await gscore_get_int_input(bot, ev, "请输入总抽数(正整数)", default_value=100, strictly_positive=True, max_value=10000)
            if pull_budget_val is None: return
            temp_run_params = {"pull_budget": pull_budget_val}
        elif temp_action_mode == '3':
            pull_budget_val = await gscore_get_int_input(bot, ev, "请输入您的抽卡预算(正整数)", strictly_positive=True, max_value=20000) 
            if pull_budget_val is None: return

            target_fc_fw_result = await gscore_get_fc_fw_input(bot, ev, "请输入您的目标配置(例如'0+1')")
            if target_fc_fw_result is None: return 
            
            target_tc_val, target_tw_val = target_fc_fw_result 
            temp_run_params = {
                "pull_budget": pull_budget_val,
                "target_tc": target_tc_val, 
                "target_tw": target_tw_val  
            }

        if not temp_action_mode: 
             logger.error(f"ww_gacha_simulator (User: {user_id}, Critical Debug): temp_action_mode not set after interactive flow.")
             await bot.send("内部逻辑错误，无法继续。", at_sender=at_sender)
             return

        new_config_signature = f"{temp_action_mode}-{str(temp_run_params)}-{DEFAULT_SIMULATIONS}"
        if current_user_state['current_config_signature'] != new_config_signature:
            logger.info(f"ww_gacha_simulator (User: {user_id}, Debug): Config changed, history cleared silently.")
            current_user_state['rerun_history_mode1'] = []
            current_user_state['rerun_history_mode2'] = []
            current_user_state['current_config_signature'] = new_config_signature
        
        action_mode_to_run = temp_action_mode
        params_to_run = temp_run_params
        current_user_state['last_run_config'] = {"mode": action_mode_to_run, "params": params_to_run, "num_simulations": DEFAULT_SIMULATIONS}
        logger.info(f"ww_gacha_simulator (User: {user_id}, Debug): New config set. current_user_state['last_run_config'] is now: {current_user_state['last_run_config']}")

    if action_mode_to_run is None: 
        logger.info(f"ww_gacha_simulator (User: {user_id}, Debug): No action mode determined (e.g. user cancelled all choices).")
        return 
    
    processing_msg_mode_suffix = f" (模式 {action_mode_to_run})" if action_mode_to_run else ""
    processing_message = f"模拟计算中{processing_msg_mode_suffix}, 模拟次数: {num_sims_to_run:,}...请稍候..."
    await bot.send(processing_message, at_sender=False) 

    final_output_message = ""
    try:
        if action_mode_to_run == '1':
            expected_pulls = calculate_expected_pulls(params_to_run['target_fc'], params_to_run['target_fw'], num_sims_to_run)
            current_user_state['rerun_history_mode1'].append(expected_pulls)
            
            a_val = params_to_run['target_fc'] - 1 
            b_val = params_to_run['target_fw']
            target_display_str = f"{a_val}+{b_val}"
            result_message = f"✨ 目标 {target_display_str} 期望 ≈ {expected_pulls:.2f}抽"
            
            analysis_message = format_mode1_analysis_results(current_user_state['rerun_history_mode1'], num_sims_to_run)
            final_output_message = f"{result_message}\n{analysis_message}"

        elif action_mode_to_run == '2':
            current_run_top_5 = get_top_outcomes(params_to_run['pull_budget'], num_sims_to_run)
            current_user_state['rerun_history_mode2'].append(current_run_top_5) 
            
            current_run_output_lines = [f"✨ {params_to_run['pull_budget']:,}抽 Top 5 结果 (当前运行):"]
            if not current_run_top_5:
                current_run_output_lines.append("   未能产生有效结果或预算过低。")
            else:
                for idx, res_dict in enumerate(current_run_top_5):
                    if idx >= len(EMOJI_NUMS): break 
                    outcome_tuple = res_dict['outcome (FC, FW)'] 
                    prob = res_dict['probability']
                    
                    fc_total = outcome_tuple[0] 
                    fw_total = outcome_tuple[1] 
                    
                    if fc_total > 0:
                        a = fc_total - 1 
                        outcome_display_str = f"{a}+{fw_total}"
                    else: 
                        outcome_display_str = f"0角色, {fw_total}武器"
                    
                    emoji_num = EMOJI_NUMS[idx]
                    current_run_output_lines.append(f"   {emoji_num} {outcome_display_str}: 概率 {prob:.2%}")
            
            current_run_formatted_string = '\n'.join(current_run_output_lines)
            analysis_message = format_mode2_analysis_results(current_user_state['rerun_history_mode2'], num_sims_to_run)
            final_output_message = f"{current_run_formatted_string}{analysis_message}"
        
        elif action_mode_to_run == '3':
            budget = params_to_run['pull_budget']
            target_tc = params_to_run['target_tc'] 
            target_tw = params_to_run['target_tw'] 

            success_count = 0
            for _ in range(num_sims_to_run): 
                obtained_tc, obtained_tw = simulate_for_budget_outcome(budget)
                if obtained_tc >= target_tc and obtained_tw >= target_tw:
                    success_count += 1
            
            success_rate = (success_count / num_sims_to_run) * 100
            
            target_a_display = target_tc - 1
            target_b_display = target_tw
            target_str_display = f"{target_a_display}+{target_b_display}"

            result_message = f"✨ {budget:,}抽预算, 目标 {target_str_display}:\n达成成功率: {success_rate:.2f}% ({success_count:,}/{num_sims_to_run:,}次)"
            final_output_message = result_message
        
        else: 
            await bot.send("错误：无效执行模式。", at_sender=at_sender) 
            current_user_state['last_activity_ts'] = time.time() 
            return
        
        # MODIFIED: Updated completion prompt for on_fullmatch flow
        completion_prompt = f"\n模拟完成!\n输入 `ww{MAIN_COMMAND_EXAMPLE}` 可再次运行或开始新的模拟。"
        await bot.send(f"{final_output_message}{completion_prompt}", at_sender=at_sender)

    except ValueError as ve:
        logger.error(f"ww_gacha_simulator (User: {user_id}) Simulation ValueError: {ve}")
        await bot.send(f"模拟过程中发生配置错误: {ve}", at_sender=at_sender)
        return 
    except Exception as e:
        logger.error(f"ww_gacha_simulator (User: {user_id}) Simulation Error (Mode {action_mode_to_run}): {e}", exc_info=True)
        await bot.send(f"模拟过程中发生未知错误: {e}", at_sender=at_sender)
        return
            
    current_user_state['last_activity_ts'] = time.time()
    logger.info(f"ww_gacha_simulator (User: {user_id}, Debug): Updated last_activity_ts to {current_user_state['last_activity_ts']}")


@sv_ww_gacha_simulator.on_fullmatch(SIMULATOR_HELP_COMMANDS, block=True)
async def handle_gacha_simulator_help(bot: Bot, ev: Event):
    at_sender = True if ev.group_id else False
    
    # Common variables for f-strings
    _name = sv_ww_gacha_simulator.name
    _example_cmd = MAIN_COMMAND_EXAMPLE # Assuming MAIN_COMMAND_EXAMPLE is defined
    _sim_count = DEFAULT_SIMULATIONS # Assuming DEFAULT_SIMULATIONS is defined
    _help_cmd_actual = SIMULATOR_HELP_COMMANDS[0] # Assuming SIMULATOR_HELP_COMMANDS is defined

    # Message 1: Title and basic commands
    msg1_content = "\n".join([
        f"--- {_name} 帮助 ---",
        "",  # Blank line
        "命令: `ww抽卡模拟`, `ww模拟抽卡`, `ww抽卡计算`, `ww模拟`",
        "输入命令后，将引导您进行操作。"
    ])

    # Message 2: Operation flow
    msg2_content = "\n".join([
        " ",
        "--------------",
        "操作流程:",
        f"1. 输入命令 (例如: ww{_example_cmd})",
        "2. 如果有上次配置，机器人会询问是否重新运行。",
        "   - 回复 `y` 重新运行上次配置。",
        "   - 回复 `n` 进入新模拟配置。",
        "   - 回复 `q` 退出操作。",
        "3. 选择模式:",
        "   - 1: 计算目标的期望抽数",
        "   - 2: 模拟N抽结果 (Top 5)",
        "   - 3: 计算预算内达成目标成功率",
        "4. 根据提示输入相应参数。"
    ])

    # Message 3: Parameter format explanation
    msg3_content = "\n".join([
        " ",
        "--------------",
        "参数格式说明:",
        "  - 目标配置: `A+B`",
        "    (A: 角色共鸣链数 [0-6], B: 武器谐振数 [0-5])",
        "    - 0+0 → 1个角色本体, 0把武器",
        "    - 0+1 → 1个角色本体, 1把武器",
        "    - 6+5 → 7个角色本体, 5把武器 (上限)",
        "  - 抽数预算: 一个正整数"
    ])

    # Message 4: Simulation details and how to re-invoke help
    msg4_content = "\n".join([
        " ",
        "--------------",
        f"所有模拟均基于 {_sim_count:,} 次运算；",
        "考虑大小保底，不考虑珊瑚换抽和换共鸣链；",
        "概率分布来源\"wuwa tracker\"约20,000,000次唤取记录统计", # Literal quotes around "wuwa tracker"
        "",  # Blank line
        f"要查看此帮助: `ww{_help_cmd_actual}`"
    ])

    # Combine messages into a list to be sent as a forwarded message
    forwarded_help_messages = [msg1_content,msg2_content,msg3_content,msg4_content]

    # Send the list of messages.
    await bot.send(forwarded_help_messages)


# --- Initial load ---
initial_load_success = load_probability_distribution()
if not initial_load_success:
    logger.warning(f"❌ww_gacha_simulator: {sv_ww_gacha_simulator.name} 概率文件加载失败，可能无法正常工作。")
else:
    logger.info(f"✅ww_gacha_simulator: {sv_ww_gacha_simulator.name} 已加载。")