---
name: playwright-community-publisher
description: 使用 Playwright 半自动发布雪球、富途、老虎社区内容，支持帖子评论，以及雪球/富途/老虎社区“发帖 -> 发讨论”的预览确认后发布流程。
tools: Bash, Write
---

# Playwright 社区发布

当任务需要在 `xueqiu`、`futu`、`tiger` 这类社区页面里登录后发表评论，或在社区首页发帖/发讨论时，使用本 skill。

默认工作流是“半自动发布”：

1. 先保存平台登录态
2. 打开目标页面
3. 自动填充评论或讨论正文
4. 默认停在发布前预览
5. 人工确认后再真正提交

不要默认做静默批量发布。优先使用 `preview` 模式，避免误发和风控。

雪球模式额外支持：

- 自动补股票代码
- 自动补话题标签
- 从 OpenClaw 任务结果自动生成讨论正文
- 一键 `预览 -> 终端确认 -> 发布`

## 先准备登录态

如果脚本提示 `missing_dependency`，推荐在 `~/.openclaw` 根目录安装一次依赖，供所有 workspace 复用：

```bash
cd ~/.openclaw
npm install playwright
```

如果你只想给单个 agent workspace 安装，也可以在对应目录执行：

```bash
cd ~/.openclaw/workspace-chief_of_staff/skills/playwright-community-publisher
npm install
```

首次使用前，先保存平台登录态：

```bash
node scripts/save_auth_state.mjs --site xueqiu
node scripts/save_auth_state.mjs --site futu
node scripts/save_auth_state.mjs --site tiger
```

登录态会保存到：

- `~/.openclaw/playwright-community-publisher/auth/xueqiu.json`
- `~/.openclaw/playwright-community-publisher/auth/futu.json`
- `~/.openclaw/playwright-community-publisher/auth/tiger.json`

## 预览评论

```bash
node scripts/community_publisher.mjs \
  --site xueqiu \
  --action comment \
  --url "https://xueqiu.com/..." \
  --content-file /tmp/comment.txt \
  --mode preview
```

## 雪球发讨论

```bash
node scripts/community_publisher.mjs \
  --site xueqiu \
  --action discussion \
  --content-file /tmp/discussion.txt \
  --mode preview
```

这条链会默认打开雪球首页，点击右上角 `发帖`，再选择 `发讨论`。

如果要一起带一张配图：

```bash
node scripts/community_publisher.mjs \
  --site xueqiu \
  --action discussion \
  --content-file /tmp/discussion.txt \
  --image /tmp/discussion-cover.png \
  --mode preview
```

当前先按“单张配图”实现，图片路径不存在或站点上传控件未命中时，会明确返回 `blocked`。

## 从 OpenClaw 任务结果自动生成雪球讨论

```bash
node scripts/community_publisher.mjs \
  --site xueqiu \
  --action discussion \
  --task-id JJC-20260314-001 \
  --mode confirm
```

这条链会自动：

1. 从 `tasks_source.json` 找到任务
2. 读取对应交付物 / 报告文件
3. 生成雪球讨论正文
4. 自动提取股票代码和话题标签
5. 先打开预览，再在终端里确认是否发布

如果你想手工补充股票代码或话题标签，也可以：

```bash
node scripts/community_publisher.mjs \
  --site xueqiu \
  --action discussion \
  --task-id JJC-20260314-001 \
  --stocks "腾讯控股(00700),青云科技(688316)" \
  --topics "AI,大模型,知乎" \
  --mode confirm
```

## 富途/老虎社区发讨论

```bash
node scripts/community_publisher.mjs \
  --site futu \
  --action discussion \
  --content-file /tmp/discussion.txt \
  --mode preview

node scripts/community_publisher.mjs \
  --site tiger \
  --action discussion \
  --content-file /tmp/discussion.txt \
  --mode preview
```

这两条链会默认打开社区首页，尝试点击 `发帖/发布` 入口，再进入 `发讨论` 或等价的帖子编辑流程。

## 真正发布

```bash
node scripts/community_publisher.mjs \
  --site futu \
  --action comment \
  --url "https://www.futunn.com/..." \
  --content "这条观点我认同，补充两个观察..." \
  --mode publish
```

## 调整站点选择器

如果页面结构变化，复制模板并改成你的站点覆盖配置：

```bash
cp assets/site-overrides.example.json /tmp/community-site-overrides.json
```

然后传入：

```bash
node scripts/community_publisher.mjs ... --config /tmp/community-site-overrides.json
```

## 输出与留痕

每次执行都会写入：

- 截图
- trace zip
- 执行结果 json

目录默认在：

- `~/.openclaw/playwright-community-publisher/artifacts/<site>/<timestamp>/`

## 阻塞处理

以下情况必须返回阻塞，不要假装成功：

- 登录态缺失或已失效
- 页面需要验证码/二次验证
- 没找到评论输入框或讨论输入框
- 没找到发布按钮
- 平台明确提示频率限制或风控

阻塞时，优先给出：

- 缺什么
- 哪一步失败
- 截图路径
- 建议下一步动作
