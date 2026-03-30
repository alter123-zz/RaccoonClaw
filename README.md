# RaccoonClaw-OSS

RaccoonClaw-OSS 是一个基于 OpenClaw 的多 Agent 工作台。它把任务入口、分诊、审核、执行、交付归档放到同一套可观测界面里，并提供一个适合开源分发的社区版基线。

## 3 分钟本地启动

```bash
cp .env.example .env
chmod +x install.sh
./install.sh
bash scripts/run_single_backend.sh
```

打开 `http://127.0.0.1:7891`。

默认主路径是 `本地安装 + 仓库内 .openclaw`。Docker/Compose 保留为可选增强，不是社区版主入口。

## 这是什么

- 一个面向单机/本地优先的 OpenClaw 工作台
- 一个带 `direct / light / full` 分诊体系的多部门协作界面
- 一个把任务、交付物、归档、状态监控放在同一工作台里的产品

## 这不是什么

- 不是成熟 SaaS
- 不是云端托管平台
- 不是默认包含 IM、网关治理、定时自动化的“全功能即开即用”成品

社区版默认只开放最稳的主链路：

- 对话
- 发起任务
- 任务状态
- 交付归档
- 模型与技能配置
- 模板发起

可选高级功能默认关闭，需要在 `.env` 里显式开启：

- IM 渠道
- 网关 / Toolbox
- 定时任务
- 自动化镜像

## 快速开始

1. 安装 OpenClaw CLI，并完成一次初始化。
2. 复制环境模板：

```bash
cp .env.example .env
```

3. 执行安装脚本：

```bash
chmod +x install.sh
./install.sh
```

4. 启动工作台：

```bash
bash scripts/run_single_backend.sh
```

5. 打开：

```text
http://127.0.0.1:7891
```

Docker/Compose 仅作为可选增强，不是社区版主路径：

```bash
docker compose up --build
```

完整安装、seed profile、故障排查见 [docs/getting-started.md](./docs/getting-started.md)。  
功能边界和分级见 [docs/community-edition.md](./docs/community-edition.md)。
发版检查清单见 [docs/releasing.md](./docs/releasing.md)。  
版本变更记录见 [CHANGELOG.md](./CHANGELOG.md)。  
安全披露见 [SECURITY.md](./SECURITY.md)，支持边界见 [SUPPORT.md](./SUPPORT.md)。

## 项目结构

```text
agents/          Agent persona 与默认配置
dashboard/       单后端工作台服务
docs/            社区版文档、边界说明与快速开始
edict/           React 前端与 FastAPI 桥接层
scripts/         安装、同步、seed、调度、采集脚本
shared/          agent registry、workflow config、模式配置
skills/          仓库内置 skills
tests/           回归测试、迁移测试、UI smoke
```

## 设计原则

- canonical-only：默认只使用现代组织命名
- local-first：默认运行在仓库内隔离 runtime，不污染全局环境
- observable：任务流转、交付物、阻塞原因都能在工作台查看
- gated-features：高风险和高脆弱功能默认关闭，显式开启

## 许可

MIT
