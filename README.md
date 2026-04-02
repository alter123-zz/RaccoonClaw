# RaccoonClaw-OSS

[中文](./README.md) | [English](./README_EN.md)

RaccoonClaw-OSS 是一个基于 OpenClaw 的多 Agent 工作台。它把任务入口、分诊、审核、执行、交付归档放到同一套可观测界面里，默认采用现代组织命名。

## 核心能力

- **总裁办入口**：区分闲聊、直办、轻流程、完整流程
- **任务看板**：创建、推进、暂停、取消、归档
- **交付归档**：保存任务时间线与交付物
- **状态监控**：查看部门、Agent、阻塞项与当前活跃任务
- **模型与技能配置**：按 Agent 管理模型、已装技能，内置技能
- **每日简报**：手动和定时采集，可配置信息源

## 架构

```
Browser (React SPA)
    │
    ▼
FastAPI Backend (Raccoon/backend/)
    ├── REST API          — 任务、Agent、配置
    ├── WebSocket          — 实时推送（依赖 Redis）
    ├── Cron Scheduler     — 定时任务调度
    └── Static Files       — 前端构建产物
    │
    ▼
OpenClaw Runtime (~/.openclaw/)
    ├── workspace-chef_of_staff/   等 Agent 工作区
    ├── agents/                    Agent 配置
    └── skills/                    技能库
```

**技术栈**：Python 3.11 + FastAPI | React 18 + TypeScript | OpenClaw Agent Runtime

**依赖**：
- **必须**：[OpenClaw](https://github.com/openclaw/openclaw) 已安装并初始化
- **必须**：Python 3.11+（会自动创建虚拟环境）
- **可选**：Redis（启用实时推送，不填则降级为轮询）
- **可选**：Node.js 18+（仅重新构建前端时需要）
- **可选**：Node.js 18+（仅重新构建前端时需要）

## 组织结构

| ID | 部门 | 职责 |
|----|------|------|
| `chief_of_staff` | 总裁办 | 需求入口与对外沟通 |
| `planning` | 产品规划部 | 需求拆解与方案规划 |
| `review_control` | 评审质控部 | 方案评审与风险把控 |
| `delivery_ops` | 交付运营部 | 任务派发与交付跟踪 |
| `brand_content` | 品牌内容部 | 内容创作与品牌管理 |
| `business_analysis` | 经营分析部 | 数据分析与经营洞察 |
| `secops` | 安全运维部 | 安全监控与事件响应 |
| `compliance_test` | 合规测试部 | 质量保证与合规检查 |
| `engineering` | 工程研发部 | 软件开发与基础设施 |
| `people_ops` | 人力组织部 | 团队协调与资源管理 |

## 快速开始

### 前置要求

- **必须**：已安装并初始化 [OpenClaw](https://github.com/openclaw/openclaw)
- **必须**：Python 3.11+
- **可选**：Node.js 18+（仅重新构建前端时需要）

### 1. 安装

```bash
# 如已有旧目录，先删除：
# rm -rf RaccoonClaw

git clone https://github.com/alter123-zz/RaccoonClaw.git
cd RaccoonClaw
chmod +x install.sh
./install.sh
```

`install.sh` 会：
- 创建 10 个 canonical OpenClaw workspaces
- 注册 Agent 配置到 `~/.openclaw/openclaw.json`
- 创建 Python 虚拟环境并安装依赖
- 构建 React 前端（需要 Node.js）
- 同步初始数据

### 2. 启动

```bash
# 方式一：FastAPI 后端（推荐，支持 WebSocket 实时推送）
bash scripts/run_single_backend.sh

# 方式二：轻量 HTTP 服务器（无 WebSocket，适合简单部署）
python3 dashboard/server.py

# 方式三：Docker（自动包含 Redis）
docker compose up
```

打开工作台：`http://127.0.0.1:7891`

### 3. 持续运行（可选）

```bash
# 数据同步 + 定时调度（每 15 秒刷新，每 2 分钟巡检停滞任务）
bash scripts/run_loop.sh
```

更详细的步骤见 [docs/getting-started.md](./docs/getting-started.md)。

## 项目结构

```
agents/           Agent persona 与默认配置
dashboard/         前端构建产物（由 Raccoon/frontend 构建）
                   也可独立作为轻量 HTTP 服务器运行
Raccoon/
  frontend/       React + TypeScript 前端源码
  backend/        FastAPI 后端（主要服务器）
scripts/          安装、同步、调度、采集脚本
shared/            Agent registry、workflow config、模式配置
skills/            仓库内置 skills
tests/             基础回归测试
docs/              文档与截图
docker/            Docker 部署文件与演示数据
```

## 设计原则

- **canonical-only**：默认只使用现代组织命名
- **可观测**：任务流转、交付物、阻塞原因都能在工作台查看
- **可干预**：任务可暂停、取消、直派或走完整链路
- **可部署**：依赖 OpenClaw，尽量保持本地即可运行

## 文档

- [快速入门](./docs/getting-started.md) — 详细安装指南
- [工作台服务](./docs/dashboard-service.md) — 架构概览
- [贡献指南](./CONTRIBUTING.md) — 如何参与贡献

## 许可

[MIT](./LICENSE)
