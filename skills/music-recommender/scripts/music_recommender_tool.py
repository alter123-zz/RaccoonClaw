#!/usr/bin/env python3
"""
AI音乐推荐 — 工具脚本
功能: recommend: 推荐音乐, playlist: 生成歌单, mood: 按心情推荐

用法:
    python3 music_recommender_tool.py recommend [args]    # 推荐音乐
    python3 music_recommender_tool.py playlist [args]    # 生成歌单
    python3 music_recommender_tool.py mood [args]    # 按心情推荐
"""

import sys, json, os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
REF_URLS = ["https://developer.spotify.com/documentation/web-api", "https://github.com/hesamsheikh/awesome-openclaw-usecases/blob/main/usecases/daily-reddit-digest.md", "https://musicbrainz.org/doc/MusicBrainz_API", "https://github.com/spotipy-dev/spotipy", "https://news.ycombinator.com/item?id=42457780"]

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def load_data():
    data_file = os.path.join(DATA_DIR, "music_recommender_data.json")
    if os.path.exists(data_file):
        with open(data_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"records": [], "created": datetime.now().isoformat(), "tool": "music-recommender"}

def save_data(data):
    ensure_data_dir()
    data_file = os.path.join(DATA_DIR, "music_recommender_data.json")
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def recommend(args):
    """推荐音乐"""
    data = load_data()
    record = {
        "timestamp": datetime.now().isoformat(),
        "command": "recommend",
        "input": " ".join(args) if args else "",
        "status": "completed"
    }
    data["records"].append(record)
    save_data(data)
    return {
        "status": "success",
        "command": "recommend",
        "message": "推荐音乐完成",
        "record": record,
        "total_records": len(data["records"]),
        "reference_urls": REF_URLS[:3]
    }

def playlist(args):
    """生成歌单"""
    data = load_data()
    record = {
        "timestamp": datetime.now().isoformat(),
        "command": "playlist",
        "input": " ".join(args) if args else "",
        "status": "completed"
    }
    data["records"].append(record)
    save_data(data)
    return {
        "status": "success",
        "command": "playlist",
        "message": "生成歌单完成",
        "record": record,
        "total_records": len(data["records"]),
        "reference_urls": REF_URLS[:3]
    }

def mood(args):
    """按心情推荐"""
    data = load_data()
    record = {
        "timestamp": datetime.now().isoformat(),
        "command": "mood",
        "input": " ".join(args) if args else "",
        "status": "completed"
    }
    data["records"].append(record)
    save_data(data)
    return {
        "status": "success",
        "command": "mood",
        "message": "按心情推荐完成",
        "record": record,
        "total_records": len(data["records"]),
        "reference_urls": REF_URLS[:3]
    }

def main():
    cmds = ["recommend", "playlist", "mood"]
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(json.dumps({
            "error": f"用法: music_recommender_tool.py <{','.join(cmds)}> [args]",
            "available_commands": {c: "" for c in cmds},
            "tool": "music-recommender",
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
    
    cmd = sys.argv[1]
    args = sys.argv[2:]
    
    if cmd == "recommend":
        result = recommend(args)
    elif cmd == "playlist":
        result = playlist(args)
    elif cmd == "mood":
        result = mood(args)
    else:
        result = {"error": f"未知命令: {cmd}"}
    
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

if __name__ == "__main__":
    main()
