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
    "belt and road",
    "patent",
    "innovation",
    "technology spillover",
    "trade",
    "global value chain"
]

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
        r = requests.post(url, headers=headers, json=data, timeout=30)
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
# 抓取论文
# ==============================

def get_nber_papers():

    url = "https://www.nber.org/papers"

    r = requests.get(url)

    soup = BeautifulSoup(r.text,"html.parser")

    papers = []

    cards = soup.select(".paper-card")

    for c in cards:

        title = c.select_one(".title")

        if title:

            title_text = title.text.strip()

            papers.append(title_text)

    return papers

# ==============================
# 过滤与你研究相关论文
# ==============================

def filter_related_papers(papers):

    related = []

    for p in papers:

        p_lower = p.lower()

        for k in KEYWORDS:

            if k in p_lower:

                related.append(p)

                break

    return related[:5]

# ==============================
# 文献简报生成
# ==============================

def generate_paper_report():

    papers = get_nber_papers()

    related = filter_related_papers(papers)

    if len(related) == 0:

        related = papers[:5]

    paper_text = "\n".join(related)

    prompt = f"""
今天最新经济学论文标题如下：

{paper_text}

请生成一份经济学研究前沿日报。

要求：
1 中文
2 每篇论文一句话总结
3 语气像科研简报
4 适合经济学研究生阅读
"""

    report = call_llm(prompt)

    today = beijing_now().strftime("%Y-%m-%d")

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


    # ===== 临时测试：发全部三种消息 =====
    for test_hour, label in [(9, "上午"), (15, "下午"), (21, "晚上")]:
        task_list = tasks.get(today) or tasks.get("default", [])
        task_text = "\n".join([f"- {t}" for t in task_list]) if task_list else "今天没有设定任务"

        if test_hour < 12:
            prompt = f"你是科研督促助手。学生今天的任务：\n{task_text}\n现在是上午，请写一段督促开始科研的话。语气：理性、像导师提醒学生，不要太生硬。"
        elif test_hour < 18:
            prompt = f"学生今天任务：\n{task_text}\n现在已经是下午，请写一段询问科研进度的话。语气：像导师提醒进度，稍微有一点压力。"
        else:
            github_link = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/edit/main/tasks.json"
            prompt = f"学生今天计划完成：\n{task_text}\n现在是晚上，请写一段总结今天科研情况并鼓励继续推进的话。语气：鼓励但保持理性。"

        msg = call_llm(prompt)
        if test_hour >= 21:
            msg += f"\n\n📝 更新明天的任务：\nhttps://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/edit/main/tasks.json"
        msg += f"\n\n[测试-{label}] {today}"
        print(msg)
        send_feishu(msg)






if __name__ == "__main__":
    main()
