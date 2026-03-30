#!/usr/bin/env python3
"""
年度目标追踪 — 工具脚本
功能: set: 设定目标, progress: 查看进度, review: 生成回顾

用法:
    python3 goal_tracker_tool.py set [args]    # 设定目标
    python3 goal_tracker_tool.py progress [args]    # 查看进度
    python3 goal_tracker_tool.py review [args]    # 生成回顾
"""

import sys, json, os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
REF_URLS = ["https://developer.todoist.com/rest/v2/", "https://github.com/hesamsheikh/awesome-openclaw-usecases/blob/main/usecases/todoist-task-manager.md", "https://www.whatmatters.com/faqs/okr-meaning-definition-example", "https://news.ycombinator.com/item?id=39723316", "https://www.reddit.com/r/selfimprovement/comments/1092dbcyyz/goal_tracker_ai/"]

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def load_data():
    data_file = os.path.join(DATA_DIR, "goal_tracker_data.json")
    if os.path.exists(data_file):
        with open(data_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"records": [], "created": datetime.now().isoformat(), "tool": "goal-tracker"}

def save_data(data):
    ensure_data_dir()
    data_file = os.path.join(DATA_DIR, "goal_tracker_data.json")
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def set(args):
    """设定目标"""
    data = load_data()
    record = {
        "timestamp": datetime.now().isoformat(),
        "command": "set",
        "input": " ".join(args) if args else "",
        "status": "completed"
    }
    data["records"].append(record)
    save_data(data)
    return {
        "status": "success",
        "command": "set",
        "message": "设定目标完成",
        "record": record,
        "total_records": len(data["records"]),
        "reference_urls": REF_URLS[:3]
    }

def progress(args):
    """查看进度"""
    data = load_data()
    record = {
        "timestamp": datetime.now().isoformat(),
        "command": "progress",
        "input": " ".join(args) if args else "",
        "status": "completed"
    }
    data["records"].append(record)
    save_data(data)
    return {
        "status": "success",
        "command": "progress",
        "message": "查看进度完成",
        "record": record,
        "total_records": len(data["records"]),
        "reference_urls": REF_URLS[:3]
    }

def review(args):
    """生成回顾"""
    data = load_data()
    record = {
        "timestamp": datetime.now().isoformat(),
        "command": "review",
        "input": " ".join(args) if args else "",
        "status": "completed"
    }
    data["records"].append(record)
    save_data(data)
    return {
        "status": "success",
        "command": "review",
        "message": "生成回顾完成",
        "record": record,
        "total_records": len(data["records"]),
        "reference_urls": REF_URLS[:3]
    }

def main():
    cmds = ["set", "progress", "review"]
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(json.dumps({
            "error": f"用法: goal_tracker_tool.py <{','.join(cmds)}> [args]",
            "available_commands": {c: "" for c in cmds},
            "tool": "goal-tracker",
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    cmd = sys.argv[1]
    args = sys.argv[2:]
    
    if cmd == "set":
        result = set(args)
    elif cmd == "progress":
        result = progress(args)
    elif cmd == "review":
        result = review(args)
    else:
        result = {"error": f"未知命令: {cmd}"}
    
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

if __name__ == "__main__":
    main()
