## 变更描述
<!-- 简要描述此 PR 的目的和变更内容 -->

## 变更类型
- [ ] Bug 修复
- [ ] 新功能
- [ ] 重构 / 代码优化
- [ ] 文档更新
- [ ] CI / 工程配置

## 社区版边界

- [ ] 这次改动没有重新引入硬编码个人路径（如 `/Users/...`、默认 `~/.openclaw`）
- [ ] 这次改动符合主支持路径：本地安装 + repo-local `.openclaw`
- [ ] 如果涉及可选功能，我已经确认默认 feature flag 仍然安全
- [ ] 如果涉及用户可见行为，我已经同步更新文档 / changelog / release docs

## 检查清单
- [ ] 代码已通过 `python3 -m py_compile` 检查
- [ ] 后端回归已运行：`python3 -m unittest discover -s tests -p 'test_*.py'`
- [ ] 前端构建已运行：`cd edict/frontend && npm install && npm run build`
- [ ] 如有 UI 变更，已做浏览器验证或 `python3 scripts/ui_smoke.py`
- [ ] 如有 seed / 迁移 / 定时任务变更，已验证 `clean` / `demo` 或对应回归
- [ ] 更新了相关文档（如适用）

## 关联 Issue
<!-- 如 Fixes #123 -->

## 验证备注
<!-- 粘贴最关键的验证结果、截图、或 smoke 输出 -->
