# 从 server.py 迁移到 FastAPI 后端

## 背景

RaccoonClaw-OSS 曾长期使用 `dashboard/server.py`（4400 行单一文件）作为 HTTP 后端。
Phase 1 将其替换为 `Raccoon/backend/app/main.py`（FastAPI 结构），两个后端功能完全等效。

**当前状态**：
- `dashboard/server.py` → 进程 `PID 93049` 跑在 `http://127.0.0.1:7891`
- `Raccoon/backend/` → 完整的 FastAPI 后端，所有 legacy API 已补齐

---

## 变更清单

### 新增端点（Phase 0 完成）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/model-change-log` | GET | 读 model 切换历史 |
| `/api/last-result` | GET | 读上次 model 切换结果 |
| `/api/agent-activity/{agent_id}` | GET | Agent 活跃记录 |
| `/api/repair-flow-order` | POST | 修复历史任务流转错序 |
| `/api/update-remote-skill` | POST | 更新远程 skill |

### FastAPI 端点覆盖对比

| 端点 | server.py | FastAPI |
|------|-----------|---------|
| `/api/live-status` | ✅ | ✅ |
| `/api/agent-config` | ✅ | ✅ |
| `/api/model-change-log` | ✅ | ✅（新增） |
| `/api/last-result` | ✅ | ✅（新增） |
| `/api/officials-stats` | ✅ | ✅ |
| `/api/remote-skills-list` | ✅ | ✅ |
| `/api/available-skills` | ✅ | ✅ |
| `/api/agents-status` | ✅ | ✅ |
| `/api/toolbox/status` | ✅ | ✅ |
| `/api/im-channels/status` | ✅ | ✅ |
| `/api/bootstrap-status` | ✅ | ✅ |
| `/api/desktop/startup-status` | ✅ | ✅ |
| `/api/chat/sessions` | ✅ | ✅ |
| `/api/scheduler-scan` | ✅ | ✅ |
| `/api/repair-flow-order` | ✅ | ✅（新增） |
| `/api/scheduler-retry/escalate/rollback` | ✅ | ✅ |
| `/api/add-skill` | ✅ | ✅ |
| `/api/add-remote-skill` | ✅ | ✅ |
| `/api/remove-remote-skill` | ✅ | ✅ |
| `/api/update-remote-skill` | ✅ | ✅（新增） |
| `/api/task-action` | ✅ | ✅ |
| `/api/archive-task` | ✅ | ✅ |
| `/api/task-todos` | ✅ | ✅ |
| `/api/create-task` | ✅ | ✅ |
| `/api/review-action` | ✅ | ✅ |
| `/api/advance-state` | ✅ | ✅ |
| `/api/agent-wake` | ✅ | ✅ |
| `/api/set-model` | ✅ | ✅ |
| `/api/add-model` | ✅ | ✅ |
| `/api/test-model` | ✅ | ✅ |
| `/api/toolbox/action` | ✅ | ✅ |
| `/api/im-channels/upsert/toggle/delete/test` | ✅ | ✅ |
| `/api/open-path` | ✅ | ✅ |
| `/api/agent-activity/{id}` | ✅ | ✅（新增） |
| `/api/bootstrap/provision` | ✅ | ✅ |
| `/healthz` | ✅ | ❌（可通过 `/api/bootstrap-status` 替代） |
| `/api/tasks/*` (新版 UUID) | ❌ | ✅ |

**覆盖率：100%**（`/healthz` 除外，可通过 `GET /api/bootstrap-status` 替代）

---

## 切换步骤

### 1. 停止旧后端

```bash
# 找到 server.py 进程
lsof -i :7891

# 杀掉旧进程（PID 替换为实际值）
kill <PID>
```

### 2. 启动 FastAPI 后端

```bash
cd /Users/altergoo/Documents/033009RaccoonClaw-OSS

# 方式一：直接运行（默认端口 7891）
./.venv-backend/bin/python -m edict.backend.app.main

# 方式二：用 uvicorn（支持热重载）
./.venv-backend/bin/uvicorn edict.backend.app.main:app --host 127.0.0.1 --port 7891 --reload

# 方式三：用项目脚本
./.venv-backend/bin/python Raccoon/backend/run_desktop_backend.py
```

### 3. 验证

```bash
curl http://127.0.0.1:7891/api/live-status
curl http://127.0.0.1:7891/api/agent-config
curl http://127.0.0.1:7891/api/model-change-log
```

### 4. 前端配置（无需改动）

前端 `store.ts` 中的 API base URL 为相对路径 `/api`，FastAPI 后端同样配置了 CORS，切换后**前端无需任何改动**。

### 5. 数据兼容性

- 所有 `data/*.json` 文件（`tasks_source.json`、`live_status.json`、`agent_config.json` 等）**完全兼容**，路径不变。
- OpenClaw workspace 数据路径**不变**。
- FastAPI 默认端口同为 **7891**，无需修改 `OPENCLAW_GATEWAY_PORT` 等环境变量。

---

## 废弃清单

切换完成后，以下文件可以删除（建议保留一周再删除以防回滚）：

```
dashboard/server.py          # 废弃
dashboard/dashboard.html      # 废弃（FastAPI serving static files）
```

---

## 回滚方案

如 FastAPI 后端有问题，只需重启旧进程：

```bash
kill $(lsof -ti :7891) 2>/dev/null
cd /Users/altergoo/Documents/033009RaccoonClaw-OSS
./.venv-backend/bin/python dashboard/server.py &
```

---

## 技术差异说明

| 差异点 | server.py | FastAPI |
|--------|-----------|---------|
| 架构 | 单一文件 4400 行 | 模块化（`api/`/`services/`/`models/`） |
| 数据库 | 文件 JSON 轮询 | SQLite + SQLAlchemy async（可选 PG） |
| 实时推送 | 无（5s 轮询） | WebSocket (`/ws`) |
| API 文档 | 无 | Swagger UI (`/docs`) |
| CORS | 手动处理 | FastAPI middleware |
| 并发 | threading + 文件锁 | async/await + DB connection pool |
| 启动探针 | 无 | `lifespan` startup/shutdown |

---

## 下一步（Phase 2+）

Phase 1 完成后遗留的工作：

1. **数据路径统一** — 消除 `legacy_deliverables_root()`，全走 `canonical_deliverables_root()`
2. **删除废弃文件** — 确认无误后删除 `dashboard/server.py`
3. **前端 WebSocket** — 接入 `/ws` 实时推送，消除 5s 轮询
4. **前端结构拆分** — `store.ts` 和 CSS 按领域拆分
