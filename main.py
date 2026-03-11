import requests
import json
import os
from datetime import datetime

FEISHU_WEBHOOK = os.environ["FEISHU_WEBHOOK"]
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]

def load_tasks():
    with open("tasks.json","r",encoding="utf-8") as f:
        return json.load(f)

def generate_ai_message(tasks):

    today = datetime.now().strftime("%Y-%m-%d")

    if today not in tasks:
        task_text = "今天没有设置任务"
    else:
        task_text = "\n".join(tasks[today])

    prompt = f"""
你是一个严格但理性的科研督促助手。

学生今天的任务是：

{task_text}

现在时间是上午。

请写一段督促消息：

要求：
1 语气自然像真人
2 可以稍微督促
3 不要机械
4 不超过150字
"""

    url = "https://api.deepseek.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role":"user","content":prompt}
        ]
    }

    r = requests.post(url,headers=headers,json=data)

    result = r.json()
    
    print(result)
    if "choices" in result:
        return result["choices"][0]["message"]["content"]
    else:
        return "AI生成失败：" + str(result)
        

def send_feishu(text):

    data = {
        "msg_type":"text",
        "content":{
            "text":text
        }
    }

    requests.post(FEISHU_WEBHOOK,json=data)

def main():

    tasks = load_tasks()

    msg = generate_ai_message(tasks)

    send_feishu(msg)

if __name__ == "__main__":
    main()
