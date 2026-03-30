# 🍎 Apple 日历（macOS only · Tier 1 全自动）

### 预检

1. **检测日历 App**
   ```bash
   bash {SKILL_DIR}/scripts/calendar.sh detect
   ```
   输出 `apple_calendar` → 继续 ｜ 其他 → 降级

2. **查询可写日历**
   ```bash
   bash {SKILL_DIR}/scripts/calendar.sh list-calendars
   ```
   返回可写日历列表，每行一个
   ⚠️ **脚本自动选择第一个可写日历，也可通过 JSON `calendar` 字段指定**

### 执行

> ⚠️ **所有操作统一通过 `scripts/calendar.sh` 执行**，脚本内置日期跨月安全处理和参数校验。

**创建日程：**
```bash
echo '{"summary":"产品方案评审","start_date":"2026-03-15","start_time":"15:00","duration":60}' | bash {SKILL_DIR}/scripts/calendar.sh create
```

**查看日程：**
```bash
bash {SKILL_DIR}/scripts/calendar.sh list --start 2026-03-15 --end 2026-03-15
```
> 输出格式: `标题|开始时间|结束时间|日历名` 每行一条

**修改日程：**
```bash
echo '{"summary":"产品方案评审","search_date":"2026-03-15","new_start_date":"2026-03-16","new_start_time":"14:00"}' | bash {SKILL_DIR}/scripts/calendar.sh modify
```

**取消日程：**
```bash
bash {SKILL_DIR}/scripts/calendar.sh delete --summary "产品方案评审" --date 2026-03-15
```

**生成 .ics 降级文件：**
```bash
echo '{"summary":"产品方案评审","start_date":"2026-03-15","start_time":"15:00","duration":60}' | bash {SKILL_DIR}/scripts/calendar.sh generate-ics
```

### AppleScript 日期设置铁律（已由脚本自动处理）

> ℹ️ 以下逻辑已固化在 `scripts/calendar.sh` 中，AI 无需手动处理。
>
> **原理概要**：AppleScript 设置日期时必须先 `set day to 1` 再依次设年、月、日，否则月末日期会溢出报错（如 2 月 set day to 31）。详见脚本源码中的 `build_date_applescript` 函数。

### 踩坑注意

- ~~硬编码日历名~~ → 脚本自动选择第一个可写日历 ✅
- ~~日期用字符串格式~~ → 脚本内置 `current date` + 跨月安全顺序 ✅
- 首次 macOS 弹授权弹窗 → 提前告知用户"点一下【好】就行~"
- 多步操作合并为一步到位，减少中途失败概率
- 查询必须加日期范围过滤，否则返回所有历史日程导致超时

### Apple 日历参会人限制

> 🚧 **进化中**：参会人功能正在开发中，暂未封装到脚本中。用户问起时告知该功能还在进化中。

### 降级链

```
① AppleScript 全自动
  → ② open -a Calendar xxx.ics（半自动）
    → ③ .ics 文件下载
      → ④ 纯文案
```
