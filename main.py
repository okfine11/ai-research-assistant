import os
import json
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ==============================
# 配置
# ==============================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")

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

    if not os.path.exists("tasks.json"):
        return {}

    with open("tasks.json","r",encoding="utf-8") as f:
        return json.load(f)

# ==============================
# 调用 AI
# ==============================

def call_llm(prompt):

    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type":"application/json"
    }

    data = {
        "model":"gpt-4o-mini",
        "messages":[
            {"role":"system","content":"你是一个经济学研究助理"},
            {"role":"user","content":prompt}
        ],
        "temperature":0.7
    }

    r = requests.post(url,headers=headers,json=data)

    result = r.json()

    if "choices" not in result:
        return f"AI生成失败：{result}"

    return result["choices"][0]["message"]["content"]

# ==============================
# 发送飞书
# ==============================

def send_feishu(msg):

    data = {
        "msg_type":"text",
        "content":{
            "text":msg
        }
    }

    requests.post(FEISHU_WEBHOOK,json=data)

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

    task_list = tasks.get(today,[])

    if len(task_list)==0:

        task_text = "今天没有设定任务"

    else:

        task_text = "\n".join(task_list)

    hour = beijing_now().hour

    # 上午督促
    if hour < 5:

        prompt = f"""
你是一个严格但理性的科研督促助手。

学生今天的任务：

{task_text}

现在是上午。

请写一段督促开始科研的话。

语气：
理性、像导师提醒学生
不要太生硬
"""

    # 下午追问
    elif hour < 10:

        prompt = f"""
学生今天任务：

{task_text}

现在已经是下午。

请写一段询问科研进度的话。

语气：
像导师提醒进度
稍微有一点压力
"""

    # 晚上总结
    else:

        prompt = f"""
学生今天计划完成：

{task_text}

现在是晚上。

请写一段总结今天科研情况并鼓励继续推进的话。

语气：
鼓励但保持理性
"""

    return call_llm(prompt)

# ==============================
# 主程序
# ==============================

def main():

    tasks = load_tasks()

    hour = beijing_now().hour

    # 北京时间 09:30
    if hour == 1:

        msg = generate_paper_report()

    # 其它时间为督促
    else:

        msg = generate_supervisor_message(tasks)

    send_feishu(msg)

# ==============================

if __name__ == "__main__":

    main()
