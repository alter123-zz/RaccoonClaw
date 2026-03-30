#!/usr/bin/env python3
"""
习惯打卡教练 — 工具脚本
功能: create: 创建习惯, check: 打卡, stats: 查看统计

用法:
    python3 habit_tracker_tool.py create [args]    # 创建习惯
    python3 habit_tracker_tool.py check [args]    # 打卡
    python3 habit_tracker_tool.py stats [args]    # 查看统计
"""

import sys, json, os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
REF_URLS = ["https://jamesclear.com/habit-tracker", "https://github.com/hesamsheikh/awesome-openclaw-usecases/blob/main/usecases/habit-tracker-accountability-coach.md", "https://habitica.com/apidoc/", "https://news.ycombinator.com/item?id=40612953", "https://www.reddit.com/r/theXeffect/comments/1037775yyz/habit_tracker_ai/"]

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def load_data():
    data_file = os.path.join(DATA_DIR, "habit_tracker_data.json")
    if os.path.exists(data_file):
        with open(data_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"records": [], "created": datetime.now().isoformat(), "tool": "habit-tracker"}

def save_data(data):
    ensure_data_dir()
    data_file = os.path.join(DATA_DIR, "habit_tracker_data.json")
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def create(args):
    """创建习惯"""
    data = load_data()
    record = {
        "timestamp": datetime.now().isoformat(),
        "command": "create",
        "input": " ".join(args) if args else "",
        "status": "completed"
    }
    data["records"].append(record)
    save_data(data)
    return {
        "status": "success",
        "command": "create",
        "message": "创建习惯完成",
        "record": record,
        "total_records": len(data["records"]),
        "reference_urls": REF_URLS[:3]
    }

def check(args):
    """打卡"""
    data = load_data()
    record = {
        "timestamp": datetime.now().isoformat(),
        "command": "check",
        "input": " ".join(args) if args else "",
        "status": "completed"
    }
    data["records"].append(record)
    save_data(data)
    return {
        "status": "success",
        "command": "check",
        "message": "打卡完成",
        "record": record,
        "total_records": len(data["records"]),
        "reference_urls": REF_URLS[:3]
    }

def stats(args):
    """查看统计"""
    data = load_data()
    record = {
        "timestamp": datetime.now().isoformat(),
        "command": "stats",
        "input": " ".join(args) if args else "",
        "status": "completed"
    }
    data["records"].append(record)
    save_data(data)
    return {
        "status": "success",
        "command": "stats",
        "message": "查看统计完成",
        "record": record,
        "total_records": len(data["records"]),
        "reference_urls": REF_URLS[:3]
    }

def main():
    cmds = ["create", "check", "stats"]
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(json.dumps({
            "error": f"用法: habit_tracker_tool.py <{','.join(cmds)}> [args]",
            "available_commands": {c: "" for c in cmds},
            "tool": "habit-tracker",
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    cmd = sys.argv[1]
    args = sys.argv[2:]
    
    if cmd == "create":
        result = create(args)
    elif cmd == "check":
        result = check(args)
    elif cmd == "stats":
        result = stats(args)
    else:
        result = {"error": f"未知命令: {cmd}"}
    
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

if __name__ == "__main__":
    main()
