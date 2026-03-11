import requests
import json
import os
from datetime import datetime

FEISHU_WEBHOOK = os.environ["FEISHU_WEBHOOK"]

def load_tasks():
    with open("tasks.json","r",encoding="utf-8") as f:
        return json.load(f)

def generate_message(tasks):

    today = datetime.now().strftime("%Y-%m-%d")

    if today not in tasks:
        return "科研提醒：今天没有设置任务。"

    message = "科研督促\n\n"
    message += f"今天日期：{today}\n\n"
    message += "你今天计划完成：\n"

    for t in tasks[today]:
        message += f"- {t}\n"

    message += "\n现在进度如何？请不要拖延。"

    return message

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

    msg = generate_message(tasks)

    send_feishu(msg)

if __name__ == "__main__":
    main()
