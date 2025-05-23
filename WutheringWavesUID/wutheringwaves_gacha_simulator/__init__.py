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

# --- 用户状态管理 (会话隔离) ---
user_states = {} # 键: user_id (str), 值: 该用户的状态字典
# user_states[user_id] 结构示例:
# {
#     'last_run_config': None,
#     'current_config_signature': None,
#     'rerun_history_mode1': [],
#     'rerun_history_mode2': [],
#     'last_activity_ts': 0.0 # 上次活动时间戳
# }
# --- 结束用户状态管理 ---

sv_ww_gacha_simulator = SV(
    name='鸣潮抽卡模拟计算器',
    pm=6,
    priority=5,
    enabled=True,
    area='ALL'
)

INTERACTION_TIMEOUT = 30 
MAX_ALLOWED_SIMULATIONS = 500000
USER_STATE_TIMEOUT_SECONDS = 30 # 用户会话状态的超时时间 (秒) - 您可以调整这个值

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
        temp_fc_target = target_featured_chars
        temp_fw_target = target_featured_weapons

        if temp_fc_target > 0 and current_fc < 1:
            pulls, char_is_guaranteed = simulate_one_featured_character(char_is_guaranteed)
            sim_total_pulls += pulls
            current_fc += 1
        
        if temp_fw_target > 0 and current_fw < 1:
            pulls = simulate_one_featured_weapon()
            sim_total_pulls += pulls
            current_fw += 1
            
        while current_fc < min(temp_fc_target, 7): # C6是第7个角色
            pulls, char_is_guaranteed = simulate_one_featured_character(char_is_guaranteed)
            sim_total_pulls += pulls
            current_fc += 1
            
        while current_fc < temp_fc_target: # 如果目标大于C6
            pulls, char_is_guaranteed = simulate_one_featured_character(char_is_guaranteed)
            sim_total_pulls += pulls
            current_fc += 1
            
        while current_fw < temp_fw_target:
            pulls = simulate_one_featured_weapon()
            sim_total_pulls += pulls
            current_fw += 1
            
        total_pulls_across_simulations += sim_total_pulls
    if num_simulations == 0: return 0.0
    return total_pulls_across_simulations / num_simulations

def get_top_outcomes(total_pull_budget, num_simulations):
    outcomes_counter = defaultdict(int)
    for _ in range(num_simulations):
        pulls_remaining = total_pull_budget
        current_fc = 0
        current_fw = 0
        char_is_guaranteed = False
        
        if pulls_remaining > 0 and current_fc == 0:
            cost_fc1, guarantee_after_fc1 = simulate_one_featured_character(char_is_guaranteed)
            if pulls_remaining >= cost_fc1:
                pulls_remaining -= cost_fc1
                current_fc += 1
                char_is_guaranteed = guarantee_after_fc1
        
        if pulls_remaining > 0 and current_fw == 0 and current_fc >= 1:
            cost_fw1 = simulate_one_featured_weapon()
            if pulls_remaining >= cost_fw1:
                pulls_remaining -= cost_fw1
                current_fw += 1
                
        if current_fc >= 1 and current_fw >=1: 
            while pulls_remaining > 0 and current_fc < 7 :
                cost_fc_next, guarantee_after_fc_next = simulate_one_featured_character(char_is_guaranteed)
                if pulls_remaining >= cost_fc_next:
                    pulls_remaining -= cost_fc_next
                    current_fc += 1
                    char_is_guaranteed = guarantee_after_fc_next
                else:
                    break

        if pulls_remaining > 0 and current_fc >=1 and current_fw >=1: # Your original logic for alternating
            pull_for_char_next = True 
            while pulls_remaining > 0:
                if pull_for_char_next:
                    cost_fc_next, new_guarantee = simulate_one_featured_character(char_is_guaranteed)
                    if pulls_remaining >= cost_fc_next:
                        pulls_remaining -= cost_fc_next
                        current_fc += 1
                        char_is_guaranteed = new_guarantee
                    else: break 
                else: 
                    cost_fw_next = simulate_one_featured_weapon()
                    if pulls_remaining >= cost_fw_next:
                        pulls_remaining -= cost_fw_next
                        current_fw += 1
                    else: break
                pull_for_char_next = not pull_for_char_next
                        
        outcomes_counter[(current_fc, current_fw)] += 1
        
    if num_simulations == 0: return [] # Handle division by zero if no simulations
    sorted_outcomes = sorted(outcomes_counter.items(), key=lambda item: item[1], reverse=True)
    top_5 = []
    for i in range(min(5, len(sorted_outcomes))):
        outcome, count = sorted_outcomes[i]
        probability = count / num_simulations
        top_5.append({'outcome (FC, FW)': outcome, 'probability': probability, 'count': count})
    return top_5

# --- 分析结果格式化函数 ---
def format_mode1_analysis_results(history_list_mode1, num_sim_per_run):
    num_reruns = len(history_list_mode1)
    output_lines = [f"--- 期望抽数结果稳定性分析 (基于 {num_reruns} 次运行, 每次 {num_sim_per_run:,} 次模拟) ---"] # Added comma
    if not history_list_mode1:
        output_lines.append("  没有历史数据可供分析。")
        return "\n".join(output_lines)
    for i, result in enumerate(history_list_mode1):
        output_lines.append(f"  第 {i+1} 次运行的期望抽数: {result:.2f}")
    if num_reruns == 1:
        output_lines.append("  (至少需要两次运行才能进行更详细的稳定性分析)")
    elif num_reruns > 1:
        mean_of_means = statistics.mean(history_list_mode1)
        std_dev_of_means = statistics.stdev(history_list_mode1)
        min_mean = min(history_list_mode1)
        max_mean = max(history_list_mode1)
        output_lines.append(f"\n  多次运行的平均期望抽数: {mean_of_means:.2f}")
        output_lines.append(f"  期望抽数的标准差: {std_dev_of_means:.2f}")
        output_lines.append(f"  观察到的最小期望抽数: {min_mean:.2f}")
        output_lines.append(f"  观察到的最大期望抽数: {max_mean:.2f}")
        if mean_of_means > 0: # Avoid division by zero
            relative_std_dev = (std_dev_of_means / mean_of_means) * 100
            output_lines.append(f"  相对标准差 (变异系数): {relative_std_dev:.2f}%")
            if relative_std_dev < 1: output_lines.append("  结论: 结果稳定性非常好。")
            elif relative_std_dev < 5: output_lines.append("  结论: 结果稳定性较好。")
            elif relative_std_dev < 10: output_lines.append("  结论: 结果稳定性一般。")
            else: output_lines.append("  结论: 结果稳定性较差。可增加模拟次数或运行次数。")
        else: output_lines.append("  结论: 平均期望抽数为0。")
    return "\n".join(output_lines)

def format_mode2_analysis_results(history_list_mode2_top5s, num_sim_per_run):
    num_reruns = len(history_list_mode2_top5s)
    output_lines = [f"--- Top 5 结果稳定性分析 (基于 {num_reruns} 次运行, 每次 {num_sim_per_run:,} 次模拟) ---"] # Added comma
    if not history_list_mode2_top5s:
        output_lines.append("  没有历史数据可供分析。")
        return "\n".join(output_lines)

    aggregated_counts = defaultdict(int)
    valid_reruns_count = 0
    for run_top_5_list in history_list_mode2_top5s:
        if run_top_5_list: # Ensure the list itself is not empty
            valid_reruns_count +=1
            for res_dict in run_top_5_list: # Iterate through actual results
                aggregated_counts[res_dict['outcome (FC, FW)']] += res_dict['count']
    
    total_simulations_all_valid_reruns = valid_reruns_count * num_sim_per_run

    for i, run_top_5_list in enumerate(history_list_mode2_top5s):
        output_lines.append(f"\n  第 {i+1} 次运行的 Top 5 结果:")
        if not run_top_5_list:
            output_lines.append("    未能产生有效结果或预算过低。")
            continue
        for res_dict in run_top_5_list:
            outcome = res_dict['outcome (FC, FW)']
            prob = res_dict['probability']
            output_lines.append(f"    - {outcome[0]} FC, {outcome[1]} FW: 概率 {prob:.2%}")

    if valid_reruns_count > 0 and total_simulations_all_valid_reruns > 0:
        output_lines.append(f"\n  --- 所有 {valid_reruns_count} 次有效运行的聚合Top结果 (总模拟 {total_simulations_all_valid_reruns:,} 次) ---") # Added comma
        aggregated_sorted_outcomes = sorted(aggregated_counts.items(), key=lambda item: item[1], reverse=True)
        for i in range(min(5, len(aggregated_sorted_outcomes))):
            outcome, total_count = aggregated_sorted_outcomes[i]
            overall_probability = total_count / total_simulations_all_valid_reruns
            output_lines.append(f"    {i+1}. {outcome[0]} 限定角色, {outcome[1]} 限定武器 - 总体概率: {overall_probability:.2%} (计数: {total_count:,})") # Added comma
        if valid_reruns_count > 1: output_lines.append("\n  稳定性说明: 比较聚合结果与单次运行结果。")
        elif valid_reruns_count == 1 and history_list_mode2_top5s[0]: output_lines.append("\n  (至少需要两次运行才能进行聚合分析和稳定性评估)")
    return "\n".join(output_lines)

# --- GsCore 输入辅助函数 ---
async def gscore_get_int_input(bot: Bot, ev: Event, prompt_message: str, default_value=None, non_negative=True, strictly_positive=False, max_value=None, timeout_seconds=INTERACTION_TIMEOUT):
    while True:
        await bot.send(f"{prompt_message}\n(回复 'c' 取消)")
        resp = await bot.receive_resp(timeout=timeout_seconds)

        if resp is None:
            await bot.send(f"输入超时 ({timeout_seconds}秒)，操作已取消。", at_sender=at_sender)
            return None
        input_str = resp.text.strip()
        if input_str.lower() == 'c':
            await bot.send("操作已取消。")
            return None
        try:
            # Handle empty input string for default value or prompt for re-entry
            if not input_str:
                if default_value is not None:
                    value = default_value
                else:
                    await bot.send("输入不能为空，请重新输入。",at_sender=True)
                    continue # Re-prompt if empty and no default
            else:
                value = int(input_str)

            if non_negative and value < 0:
                await bot.send("输入值不能为负数，请重新输入。")
                continue
            if strictly_positive and value <= 0:
                await bot.send("输入值必须为正数且大于0，请重新输入。")
                continue
            if max_value is not None and value > max_value:
                await bot.send(f"输入值过大 (最大允许: {max_value:,})，请重新输入。")
                continue
            return value
        except ValueError:
            await bot.send("输入无效，请输入一个整数。")

# --- 主要插件命令处理函数 ---
SIMULATOR_COMMANDS = ('抽卡模拟', '模拟抽卡', '抽卡计算','模拟') # User's preferred distinct commands

@sv_ww_gacha_simulator.on_command(SIMULATOR_COMMANDS)
async def handle_gacha_simulator_sub_command(bot: Bot, ev: Event):
    user_id = str(ev.user_id)
    if not user_id: # Should ideally not happen with a valid event
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
    # 会话超时检查 (仅当用户之前有活动时)
    # .get('last_activity_ts', 0) ensures robustness if key is missing (though it shouldn't be)
    if current_user_state.get('last_run_config') or \
       current_user_state.get('rerun_history_mode1') or \
       current_user_state.get('rerun_history_mode2'): # Check if there's any state to timeout
        if (current_time - current_user_state.get('last_activity_ts', current_time - (USER_STATE_TIMEOUT_SECONDS + 1)) > USER_STATE_TIMEOUT_SECONDS):
            logger.info(f"ww_gacha_simulator (User: {user_id}, Debug): 用户会话超时。清除旧配置和历史。")
            await bot.send(f"您好，由于您在 {USER_STATE_TIMEOUT_SECONDS} 秒内没有针对此模拟器的操作，之前的模拟配置已清除。", at_sender=at_sender)
            current_user_state['last_run_config'] = None
            current_user_state['current_config_signature'] = None
            current_user_state['rerun_history_mode1'] = []
            current_user_state['rerun_history_mode2'] = []
            # last_activity_ts will be updated at the end of this current command if it proceeds

    if not PROB_DIST_NORMALIZED:
        if not load_probability_distribution(): # Tries to load PROB_DIST_FILENAME
            await bot.send(f"错误: 概率分布文件加载失败。模拟器无法运行。")
            return

    command_argument = ev.text.strip().lower()
    MAIN_PREFIX = "ww"

    logger.info(f"ww_gacha_simulator (User: {user_id}, Debug): Handler invoked. ev.command='{ev.command}', ev.text='{ev.text}'")
    logger.info(f"ww_gacha_simulator (User: {user_id}, Debug): Parsed command_argument: '{command_argument}'")
    logger.info(f"ww_gacha_simulator (User: {user_id}, Debug): Value of current_user_state['last_run_config'] BEFORE 'if rerun' check: {current_user_state['last_run_config']}")

    action_mode_to_run = None
    params_to_run = {}
    num_sims_to_run = 0

    if command_argument == 'rerun' and current_user_state['last_run_config']:
        logger.info(f"ww_gacha_simulator (User: {user_id}, Debug): Entering 'rerun' logic block.")
        action_mode_to_run = current_user_state['last_run_config']["mode"]
        params_to_run = current_user_state['last_run_config']["params"]
        num_sims_to_run = current_user_state['last_run_config']["num_simulations"]
        await bot.send(f"--- 重新运行上次模拟 (模式 {action_mode_to_run}, 模拟次数 {num_sims_to_run:,}) ---")
    else:
        if command_argument == 'rerun': # Implies last_run_config was None/Falsy
            logger.warning(f"ww_gacha_simulator (User: {user_id}, Debug): 'rerun' command, but no previous config or config timed out. New setup.")
            await bot.send("您还没有配置过模拟或配置已超时，请先设置新的模拟参数。", at_sender=at_sender)
        
        logger.info(f"ww_gacha_simulator (User: {user_id}, Debug): Entering 'new simulation config' block.")
        await bot.send(f"--- {sv_ww_gacha_simulator.name} ---\n请选择模式:\n1. 计算期望抽数\n2. 模拟N抽结果 (Top 5)\n(回复 'q' 退出)")
        mode_resp = await bot.receive_resp(timeout=INTERACTION_TIMEOUT)
        
        if mode_resp is None: # Timeout message sent by receive_resp
            return
        if mode_resp.text.strip().lower() in ['q', 'quit', 'exit', 'c', 'cancel']:
            await bot.send("操作已取消。")
            return
        
        mode_input = mode_resp.text.strip()
        if mode_input not in ['1', '2']:
            await bot.send("无效的模式选择。")
            return

        temp_action_mode = mode_input
        num_sims_prompt = f"请输入模拟次数 (最大: {MAX_ALLOWED_SIMULATIONS:,})"
        num_sims_val = await gscore_get_int_input(
            bot, ev, num_sims_prompt, default_value=20000, 
            strictly_positive=True, max_value=MAX_ALLOWED_SIMULATIONS
        )
        if num_sims_val is None: return
        temp_num_sims = num_sims_val

        temp_run_params = {}
        if temp_action_mode == '1':
            target_fc_val = await gscore_get_int_input(bot, ev, "目标限定五星角色数 (0-7)", default_value=1, non_negative=True, max_value=7)
            if target_fc_val is None: return
            target_fw_val = await gscore_get_int_input(bot, ev, "目标限定五星武器数 (0-5)", default_value=0, non_negative=True, max_value=5)
            if target_fw_val is None: return
            temp_run_params = {"target_fc": target_fc_val, "target_fw": target_fw_val}
        elif temp_action_mode == '2':
            pull_budget_val = await gscore_get_int_input(bot, ev, "总抽数预算 (例如: 300)", default_value=100, strictly_positive=True, max_value=10000) # Example max_value for budget
            if pull_budget_val is None: return
            temp_run_params = {"pull_budget": pull_budget_val}
        else:
            await bot.send("内部错误：未知模式。")
            return

        new_config_signature = f"{temp_action_mode}-{str(temp_run_params)}-{temp_num_sims}"
        if current_user_state['current_config_signature'] != new_config_signature:
            await bot.send("模拟参数已更改，您的历史记录已清空。")
            current_user_state['rerun_history_mode1'] = []
            current_user_state['rerun_history_mode2'] = []
            current_user_state['current_config_signature'] = new_config_signature
        
        action_mode_to_run = temp_action_mode
        params_to_run = temp_run_params
        num_sims_to_run = temp_num_sims
        current_user_state['last_run_config'] = {"mode": action_mode_to_run, "params": params_to_run, "num_simulations": num_sims_to_run}
        logger.info(f"ww_gacha_simulator (User: {user_id}, Debug): New config set. current_user_state['last_run_config'] is now: {current_user_state['last_run_config']}")

    if action_mode_to_run is None:
        logger.error("ww_gacha_simulator (Critical Debug): action_mode_to_run is None before execution.")
        await bot.send("内部逻辑错误，无法执行模拟。")
        return
    
    processing_message = f"模拟计算中 (模拟次数: {num_sims_to_run:,})...请稍候..."
    if num_sims_to_run > 50000: # For a slightly more informative message if many sims
        processing_message = f"模拟计算中 (模拟次数: {num_sims_to_run:,} 较大，可能需要一些时间)...请稍候..."
    await bot.send(processing_message)
    at_sender = True if ev.group_id else False # User's original logic for at_sender

    try:
        if action_mode_to_run == '1':
            expected_pulls = calculate_expected_pulls(params_to_run['target_fc'], params_to_run['target_fw'], num_sims_to_run)
            current_user_state['rerun_history_mode1'].append(expected_pulls)
            result_message = f"✨ 期望结果: {params_to_run['target_fc']}角色 & {params_to_run['target_fw']}武器 ≈ {expected_pulls:.2f}抽"
            analysis_message = format_mode1_analysis_results(current_user_state['rerun_history_mode1'], num_sims_to_run)
            await bot.send(f"{result_message}\n{analysis_message}", at_sender=at_sender)
        elif action_mode_to_run == '2':
            current_run_top_5 = get_top_outcomes(params_to_run['pull_budget'], num_sims_to_run)
            current_user_state['rerun_history_mode2'].append(current_run_top_5)
            current_run_output = [f"✨ {params_to_run['pull_budget']:,}抽 Top 5 结果:"]
            if not current_run_top_5:
                current_run_output.append("  未能产生有效结果或预算过低。",at_sender=at_sender)
            else:
                for res_dict in current_run_top_5:
                    outcome = res_dict['outcome (FC, FW)']; prob = res_dict['probability']
                    current_run_output.append(f"  - {outcome[0]} FC, {outcome[1]} FW: 概率 {prob:.2%}")
            output_string_part = '\n'.join(current_run_output)
            analysis_message = format_mode2_analysis_results(current_user_state['rerun_history_mode2'], num_sims_to_run)
            final_message_to_send = f"{output_string_part}\n{analysis_message}"
            at_sender = True if ev.group_id else False # User's original logic for at_sender
            await bot.send(final_message_to_send, at_sender=at_sender)
        else:
            await bot.send("错误：无效执行模式。")
            # No return here, will fall through to update timestamp and send final msg
    except ValueError as ve:
        logger.error(f"ww_gacha_simulator (User: {user_id}) Simulation ValueError: {ve}")
        await bot.send(f"模拟过程中发生配置错误: {ve}")
        return # Exit on simulation error, don't update timestamp or send "模拟完成"
    except Exception as e:
        logger.error(f"ww_gacha_simulator (User: {user_id}) Simulation Error (Mode {action_mode_to_run}): {e}", exc_info=True)
        await bot.send(f"模拟过程中发生未知错误: {e}")
        return # Exit on simulation error
            
    # Update last activity timestamp after successful processing of the command's main logic
    current_user_state['last_activity_ts'] = time.time()
    logger.info(f"ww_gacha_simulator (User: {user_id}, Debug): Updated last_activity_ts to {current_user_state['last_activity_ts']}")
    
    await bot.send(f"模拟完成!\n输入 `{MAIN_PREFIX}模拟rerun` 可再次以相同参数运行，或 `{MAIN_PREFIX}{ev.command}` 进行新的模拟。")


# --- Initial load ---
initial_load_success = load_probability_distribution()
if not initial_load_success:
    logger.warning(f"ww_gacha_simulator: {sv_ww_gacha_simulator.name} 概率文件加载失败，可能无法正常工作。")
else:
    logger.info(f"ww_gacha_simulator: {sv_ww_gacha_simulator.name} 已加载。")