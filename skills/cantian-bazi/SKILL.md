---
name: cantian-bazi
description: 八字排盘与农历/干支日期查询技能。用于用户请求“算八字”“四柱排盘”“阳历/农历时间转八字”“查询某天农历或干支日期”“查黄历/宜忌”等场景；关键词包括：八字、四柱、命理、阳历转八字、农历转八字、黄历、宜忌、干支日期、农历日期。 / Bazi charting and Chinese calendar conversion skill. Use for requests like “calculate my Bazi”, “Four Pillars chart”, “convert solar/lunar datetime to Bazi”, “check Chinese almanac (huangli)”, or “check auspicious/inauspicious activities (yi-ji) for a date”; keywords include: Bazi, Four Pillars, solar-to-Bazi, lunar-to-Bazi, Chinese calendar, Chinese almanac (huangli), yi-ji, heavenly stems and earthly branches.
---

# 八字排盘与农历日期查询 (Bazi & Chinese Calendar)

## 何时使用 / When to Use

- 用户要根据阳历出生时间计算四柱八字。 / User wants Four Pillars from Gregorian birth datetime.
- 用户要根据农历出生时间计算四柱八字。 / User wants Four Pillars from lunar birth datetime.
- 用户要查询某一天对应的农历、干支、宜忌等信息。 / User wants Chinese calendar info for a specific date.
- 用户要“查黄历”或看某天宜忌。 / User wants almanac-style daily auspicious/inauspicious info.

## 前置依赖 / Prerequisites

- 推荐运行环境：Node 24（可直接运行 TypeScript 源码）。 / Recommended runtime: Node 24 (can run TypeScript source directly).
- 兼容方案：若 Node 版本较低，使用 `tsx` 执行。 / Fallback: use `tsx` on lower Node versions.
- 执行目录：在 skill 根目录（`SKILL.md` 所在目录）执行以下命令。 / Run commands in the skill root (where `SKILL.md` is located).

```bash
npm i

# 仅在需要兼容运行时安装
# Install only for fallback mode
npm i -D tsx
```

## 脚本清单 / Script Index

- `scripts/buildBaziFromSolar.ts`：根据阳历时间生成八字 Markdown。 / Build Bazi from solar datetime.
- `scripts/buildBaziFromLunar.ts`：根据农历时间生成八字 Markdown。 / Build Bazi from lunar datetime.
- `scripts/getChineseCalendar.ts`：查询指定日期（默认今天）的农历与干支信息。 / Get Chinese calendar for a given date (defaults to today).

## 脚本与参数 / Scripts & Parameters

### `scripts/buildBaziFromSolar.ts`

```bash
# 推荐方式
node scripts/buildBaziFromSolar.ts <solarTime> [gender] [sect]

# 兼容方式（fallback）
tsx scripts/buildBaziFromSolar.ts <solarTime> [gender] [sect]
```

参数定义 / Parameters:

- `solarTime`（必填 / required）
  - 格式：ISO 8601 日期时间（不带时区），如 `1990-05-15T14:30:00`
  - 默认值：无
  - 非法输入：格式不合法或为空时，由底层解析失败并报错
- `gender`（可选 / optional）
  - 取值范围：`1`（男 / male）、`0`（女 / female）
  - 默认值：`1`
  - 非法输入：抛错 `性别参数无效。男性传 1，女性传 0。`
- `sect`（可选 / optional）
  - 取值范围：`1`（23:00-23:59 视为明天）、`2`（23:00-23:59 视为当天）
  - 默认值：`2`
  - 非法输入：抛错 `早晚子时配置参数无效。传 1 表示 23:00-23:59 日干支为明天，传 2 表示 23:00-23:59 日干支为当天。`

### `scripts/buildBaziFromLunar.ts`

```bash
# 推荐方式
node scripts/buildBaziFromLunar.ts <lunarTime> [gender] [sect]

# 兼容方式（fallback）
tsx scripts/buildBaziFromLunar.ts <lunarTime> [gender] [sect]
```

参数定义 / Parameters:

- `lunarTime`（必填 / required）
  - 格式：ISO 8601 日期时间（不带时区），如 `1990-04-21T14:30:00`
  - 默认值：无
  - 非法输入：格式不合法或为空时，由底层解析失败并报错
- `gender`（可选 / optional）
  - 取值范围：`1`（男 / male）、`0`（女 / female）
  - 默认值：`1`
  - 非法输入：抛错 `性别参数无效。男性传 1，女性传 0。`
- `sect`（可选 / optional）
  - 取值范围：`1`（23:00-23:59 视为明天）、`2`（23:00-23:59 视为当天）
  - 默认值：`2`
  - 非法输入：抛错 `早晚子时配置参数无效。传 1 表示 23:00-23:59 日干支为明天，传 2 表示 23:00-23:59 日干支为当天。`

### `scripts/getChineseCalendar.ts`（黄历/农历查询）

```bash
# 推荐方式（不传参默认今天）
node scripts/getChineseCalendar.ts [date]

# 兼容方式（fallback）
tsx scripts/getChineseCalendar.ts [date]
```

参数定义 / Parameters:

- `date`（可选 / optional）
  - 格式：`YYYY-MM-DD`（兼容 `YYYY/MM/DD`），如 `2024-02-10`
  - 默认值：当天日期
  - 取值范围：有效公历日期
  - 非法输入：
    - 格式错误时抛错 `日期格式无效。请传入 YYYY-MM-DD（也兼容 YYYY/MM/DD）。`
    - 日期不存在时抛错 `日期值无效。请确认年月日是实际存在的日期。`

## 示例 / Examples

```bash
# buildBaziFromSolar.ts 最小可用示例
node scripts/buildBaziFromSolar.ts "1990-05-15T14:30:00"

# buildBaziFromLunar.ts 最小可用示例
node scripts/buildBaziFromLunar.ts "1990-04-21T14:30:00"

# getChineseCalendar.ts 最小可用示例（默认今天）
node scripts/getChineseCalendar.ts

# getChineseCalendar.ts 指定日期
node scripts/getChineseCalendar.ts 2024-02-10
```

## 注意事项 / Notes

1. 所有命令均在 skill 根目录执行，不依赖仓库根目录路径。 / Run all commands in the skill root; do not rely on repo-root paths.
2. 时间字符串不要携带时区后缀（如 `Z`、`+08:00`），以免产生与预期不一致的换日结果。 / Do not append timezone suffixes (such as `Z` or `+08:00`) to avoid unexpected day shifts.
3. 涉及 23:00-23:59 出生时，建议显式传 `sect`，避免晚子时归属歧义。 / For births between 23:00-23:59, explicitly set `sect` to avoid ambiguity.
