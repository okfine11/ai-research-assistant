import os
import json
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ==============================
# 配置
# ==============================

# ✅ 修复②：统一用 DEEPSEEK_API_KEY（与 run.yml secrets 保持一致）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")

GITHUB_OWNER = "okfine11"    
GITHUB_REPO  = "ai-research-assistant" 

# 你的研究关键词（用于筛选论文）
KEYWORDS = [
    # 一带一路 / 贸易
    "belt and road", "trade policy", "export", "foreign direct investment",
    "comparative advantage", "tariff", "global value chain",
    # 专利 / 创新
    "patent", "patent citation", "innovation", "intellectual property",
    "r&d", "knowledge spillover", "technology spillover", "technology transfer",
    # AI / NLP
    "large language model", "natural language processing", "text analysis",
    "machine learning", "generative ai", "automation"
]

# 你的研究背景（用于AI分析每篇论文的价值）
MY_RESEARCH_BACKGROUND = """
我是一名经济学研究生，导师方向为国际贸易。

当前主要论文：
研究"一带一路"倡议对沿线国家专利引用网络的影响，
使用专利引用数据构建基准回归模型，
并通过 event study 识别政策冲击的动态效应，
核心关注技术溢出与知识流动机制。

研究方法：面板数据回归、event study、双重差分（DID）
数据来源：专利引用数据（USPTO/WIPO）、贸易数据
技术能力：熟悉 Python，了解 LLM 与自然语言处理，有意将文本分析方法引入经济学实证研究。

感兴趣的延伸方向：
- 技术溢出的异质性（行业/国家/距离）
- NLP 方法处理专利文本
- 全球价值链与创新
"""

def beijing_now():
    return datetime.utcnow() + timedelta(hours=8)
    
# ==============================
# 读取每日任务
# ==============================

def load_tasks():
    # ✅ 修复①：用绝对路径，确保 GitHub Actions 环境下也能找到文件
    base_dir = os.path.dirname(os.path.abspath(__file__))
    task_file = os.path.join(base_dir, "tasks.json")

    if not os.path.exists(task_file):
        print(f"[警告] tasks.json 不存在，路径：{task_file}")
        return {}

    with open(task_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        print(f"[调试] 读取到 tasks.json，共 {len(data)} 个日期条目")
        return data

# ==============================
# 调用 AI
# ==============================

def call_llm(prompt):
    # ✅ 修复②：改用 DeepSeek API
    url = "https://api.deepseek.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个经济学研究助理"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=120)
        result = r.json()

        if "choices" not in result:
            return f"AI生成失败：{result}"

        return result["choices"][0]["message"]["content"]

    except Exception as e:
        return f"请求异常：{e}"

# ==============================
# 发送飞书
# ==============================

def send_feishu(msg):
    data = {
        "msg_type": "text",
        "content": {"text": msg}
    }
    r = requests.post(FEISHU_WEBHOOK, json=data, timeout=10)
    print(f"[飞书] 发送状态：{r.status_code}")

# ==============================
# 文献简报生成
# ==============================

def generate_paper_report():
    import json as json_lib
    from papers import get_all_papers

    today = beijing_now().strftime("%Y-%m-%d")

    # ==============================
    # 抓取论文
    # ==============================
    papers = get_all_papers(KEYWORDS)

    if not papers:
        return f"📊 经济学研究前沿日报\n{today}\n\n今日暂未找到相关论文。"

    # ==============================
    # 构建论文列表文本
    # ==============================
    paper_text = ""
    for i, p in enumerate(papers):
        paper_text += f"[{i}] 来源：{p['source']}\n标题：{p['title']}\n摘要：{p['abstract']}\n\n"

    # ==============================
    # 第一步：AI 分类（core / watch / skip）
    # ==============================
    filter_prompt = f"""
我的研究背景：
{MY_RESEARCH_BACKGROUND}

以下是今日论文列表（含编号）：
{paper_text}

请对每篇论文分类，只返回JSON数组，不要输出任何其他内容：
[
  {{
    "index": 0,
    "tier": "core",
    "reason": "与我当前论文直接相关，具体说明能用在哪里（思路/方法/数据/角度）"
  }},
  {{
    "index": 1,
    "tier": "watch",
    "reason": "虽与当前论文关联不强，但涉及xxx新方法/延伸方向/前沿热点，值得关注"
  }},
  {{
    "index": 2,
    "tier": "skip",
    "reason": ""
  }}
]

分类标准：
- core：与我当前研究直接相关（方法、数据、主题高度匹配）
- watch：关联不强，但涉及我可能借鉴的新方法、感兴趣的延伸方向、或经济学重要前沿
- skip：与我的研究和兴趣完全无关
"""

    filter_result = call_llm(filter_prompt)

    # ==============================
    # 解析 JSON 分类结果
    # ==============================
    tier_map = {}      # index -> "core" or "watch"
    reason_map = {}    # index -> reason

    try:
        clean = filter_result.strip()
        if "```" in clean:
            parts = clean.split("```")
            for part in parts:
                if part.startswith("json"):
                    clean = part[4:].strip()
                    break
                elif part.strip().startswith("["):
                    clean = part.strip()
                    break
        items = json_lib.loads(clean)
        for item in items:
            tier = item.get("tier", "skip")
            if tier in ("core", "watch"):
                tier_map[item["index"]] = tier
                reason_map[item["index"]] = item.get("reason", "")
        print(f"[分类] core: {sum(1 for t in tier_map.values() if t=='core')} 篇，watch: {sum(1 for t in tier_map.values() if t=='watch')} 篇")
    except Exception as e:
        print(f"[分类] JSON解析失败，保留全部为watch：{e}")
        for i in range(len(papers)):
            tier_map[i] = "watch"
            reason_map[i] = ""

    if not tier_map:
        return f"📊 经济学研究前沿日报\n{today}\n\n今日暂未找到与你研究相关的论文。"

    # ==============================
    # 按分类分组
    # ==============================
    core_papers  = [(papers[i], reason_map[i]) for i, t in tier_map.items() if t == "core"]
    watch_papers = [(papers[i], reason_map[i]) for i, t in tier_map.items() if t == "watch"]

    def build_section(paper_list):
        text = ""
        for p, reason in paper_list:
            text += f"来源：{p['source']}\n"
            text += f"标题：{p['title']}\n"
            text += f"摘要：{p['abstract']}\n"
            text += f"备注：{reason}\n\n"
        return text

    core_text  = build_section(core_papers)
    watch_text = build_section(watch_papers)

    # ==============================
    # 第二步：AI 生成最终简报
    # ==============================
    core_count  = len(core_papers)
    watch_count = len(watch_papers)

    report_prompt = f"""
请生成一份经济学研究前沿日报，分两个板块，每篇按固定格式输出。

【板块一：与你研究直接相关】
{core_text if core_text else "今日暂无直接相关论文。"}

【板块二：值得关注】
{watch_text if watch_text else "今日暂无推荐。"}

每篇论文统一格式如下：

📄 原标题：xxx
   中文标题：xxx（翻译原标题）
来源：xxx
摘要：2-3句话，总结研究问题、方法、主要发现
你能用上 / 为什么推给你：xxx

输出要求：
- 板块一标题用：🎯 与你研究直接相关（{core_count}篇）
- 板块二标题用：👀 值得关注（{watch_count}篇）
- 全程中文，标题保留英文原文并附中文翻译
- 语气专业，像科研简报
- 板块一的"你能用上"要具体指出能用在哪个环节
- 板块二的"为什么推给你"一句话点明价值即可
- 两个板块之间加一条分隔线
"""

    report = call_llm(report_prompt)
    return f"📊 经济学研究前沿日报\n{today}\n\n{report}"
    
# ==============================
# AI督促系统
# ==============================

def generate_supervisor_message(tasks):
    today = beijing_now().strftime("%Y-%m-%d")
    task_list = tasks.get(today, [])

    print(f"[调试] 今天日期：{today}，找到任务数：{len(task_list)}")

    if len(task_list) == 0:
        task_text = "今天没有设定任务"
    else:
        task_text = "\n".join([f"- {t}" for t in task_list])

    hour = beijing_now().hour

    # ✅ 修复：时间段与实际北京时间对应
    if hour < 12:
        prompt = f"""
你是一个严格但理性的科研督促助手。

学生今天的任务：

{task_text}

现在是上午，请写一段督促开始科研的话。语气：理性、像导师提醒学生，不要太生硬。
"""
        return call_llm(prompt)

    elif hour < 18:
        prompt = f"""
学生今天任务：

{task_text}

现在已经是下午，请写一段询问科研进度的话。语气：像导师提醒进度，稍微有一点压力。
"""
        return call_llm(prompt)

    else:
        github_link = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/edit/main/tasks.json"
        prompt = f"""
学生今天计划完成：

{task_text}

现在是晚上，请写一段总结今天科研情况并鼓励继续推进的话。语气：鼓励但保持理性。
"""
        ai_msg = call_llm(prompt)
        return f"{ai_msg}\n\n📝 更新明天的任务：\n{github_link}"

    
    return call_llm(prompt)

# ==============================
# 主程序
# ==============================

def main():
    now = beijing_now()
    today = now.strftime("%Y-%m-%d")
    hour = now.hour
    minute = now.minute

    print(f"[启动] 北京时间：{today} {hour:02d}:{minute:02d}")

    tasks = load_tasks()

    # ✅ 修复：北京时间 09:30（UTC 01:30）发论文简报，其余时间督促
    if hour == 9 and minute >= 30:
        msg = generate_paper_report()
    else:
        msg = generate_supervisor_message(tasks)

    msg += f"\n\n[系统时间] {today} {hour:02d}:{minute:02d}"
    print(msg)
    send_feishu(msg)



if __name__ == "__main__":
    main()
