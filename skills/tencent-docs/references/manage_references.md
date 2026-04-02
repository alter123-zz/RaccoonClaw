# 腾讯文档 MCP 工具完整参考

本文件包含腾讯文档 MCP 中 文件管理类 相关工具的完整 API 说明、支持文件的增删改查、文件搜索、文件夹列表、文件夹信息查询、文档权限设置。

---
## 目录
- [文档创建操作](#文档创建操作)
  - [manage.create_file](#managecreate_file)
- [文档搜索操作](#文档搜索操作)
- [文档重命名](#文档重命名)
- [云文档最近浏览列表页查询](#云文档最近浏览列表页查询)
- [文档权限设置](#文档权限设置)
  - [manage.set_privilege](#manageset_privilege)
- [文档导入操作](#文档导入操作)
  - [manage.import_file](#manageimport_file)
  - [manage.import_progress](#manageimport_progress)
- [文档导出操作](#文档导出操作)
  - [manage.export_file](#manageexport_file)
  - [manage.export_progress](#manageexport_progress)
- [典型工作流示例](#典型工作流示例)

---

## 文档创建操作

### manage.create_file

**功能**：创建腾讯云文档，支持创建多种类型的文档。

**使用场景**：
- 在指定文件夹下创建新的在线文档（如文档、表格、幻灯片等）

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|-----|------|
| `title` | string | ✅ | 文档标题 |
| `doc_type` | string | ✅ | 文档类型，可选值：`smartcanvas`、`doc`、`sheet`、`form`、`slide`、`mind`、`flowchart`、`smartsheet` |
| `folder_id` | string |  | 文档所在文件夹唯一标识 |

**doc_type 取值说明**：

| 值              | 含义   |
|-----------------|--------|
| `smartcanvas`   | 文档   |
| `doc`           | Word   |
| `sheet`         | 表格   |
| `form`          | 收集表 |
| `slide`         | 幻灯片 |
| `mind`          | 思维导图 |
| `flowchart`     | 流程图 |
| `smartsheet`    | 智能表 |

**返回字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `file_id` | string | 文档ID |
| `title` | string | 文档名称 |
| `url` | string | 文档链接 |
| `type` | string | 文档类型 |

**调用示例**：

```json
{
  "title": "项目计划",
  "doc_type": "doc"
}
```

**返回示例**：

```json
{
  "file_id": "doc_1234567890",
  "title": "项目计划",
  "url": "https://docs.qq.com/doc/DV2h5cWJ0R1lQb0lH",
  "type": "doc",
  "trace_id": "trace_xyz"
}
```

---

## 文档搜索操作

### manage.search_file

**功能**：根据关键词搜索云文档，返回匹配关键词的文档列表。

**使用场景**：
- 搜索文档标题包含"MCP"关键字的文档

**请求参数**：

| 参数 | 类型 | 必填 | 说明                                                   |
|------|------|-----|------------------------------------------------------|
| `search_key` | string | ✅ | 搜索关键字                                                |

**返回字段**：

| 字段             | 类型     | 说明       |
|----------------|--------|----------|
| `list[].file_id`    | string | 文档id     |
| `list[].title` | string | 文档标题     |
| `list[].url`   | string | 文档链接     |

**调用示例**：

```json
{
  "search_key": "MCP"
}
```

**返回示例**：

```json
{
  "list":[
    {
      "file_id": "sheet_1",
      "title": "sheet_name_1",
      "url": "https://docs.qq.com/sheet/sheet_file_id_1"
    },
    {
      "file_id": "sheet_2",
      "title": "sheet_name_2",
      "url": "https://docs.qq.com/sheet/sheet_file_id_2"
    }
  ],
  "trace_id": "trace_xyz"
}
```

---

## 文档重命名

### manage.rename_file_title

**功能**：根据云文档ID更新文档标题。

**使用场景**：
- 将文档(file_id)标题更新为"MCP重命名"

**请求参数**：

| 参数 | 类型 | 必填 | 说明                      |
|------|------|-----|-------------------------|
| `file_id` | string | ✅ | 文档ID                    |
| `title` | string | ✅ | 文档标题                    |

**返回字段**：

| 字段             | 类型     | 说明         |
|----------------|--------|------------|
| `file_id`      | string  | 文档ID       |
| `title`        | string  | 文档新标题      |

**调用示例**：

```json
{
  "file_id": "MCP",
  "title": "title"
}
```

**返回示例**：

```json
{
  "file_id": "MCP",
  "title": "new_title",
  "trace_id": "trace_xyz"
}
```

---

## 云文档最近浏览列表页查询

### manage.recent_online_file

**功能**：查询云文档最近浏览页文档列表

**使用场景**：
- 用户查询最近查看或者编辑过的文档列表

**请求参数**：

| 参数 | 类型 | 必填 | 说明             |
|------|------|-----|----------------|
| `num` | uint32 | ✅ | 当前查询页码数，默认为1   |
| `count` | uint32 | ✅ | 分页条数，默认为100,每页最多查询的记录数量   |
| `order_by` | uint32 | ✅ | 排序方式：0-按文档查看时间排序，1-按文件修改时间排序，默认为0，2-按文档名称排序   |

**返回字段**：

| 字段                  | 类型     | 说明   |
|---------------------|--------|------|
| `files[].file_id`   | string  | 文档ID |
| `files[].file_name` | string  | 文档标题 |
| `files[].file_url`  | string  | 文档链接 |

**调用示例**：

```json
{
  "num": "1"
}
```

**返回示例**：

```json
{
  "file":[
    {
      "file_id": "file_1",
      "file_name": "file_name_1",
      "file_url": "xxx"
    },
    {
      "file_id": "file_2",
      "file_name": "file_name_2",
      "file_url": "xxx"
    }
  ],
  "trace_id":"trace_abc"
}
```

---

## 文档权限管理

### manage.get_privilege

**功能**：根据文档ID查询文档权限策略。返回当前文档的权限设置，仅支持返回 0（私密文档）、1（部分成员可见）、2（所有人可读）、3（所有人可编辑）四种权限场景，其他权限类型暂不支持。

**使用场景**：
- 查看文档当前的权限状态，决定是否需要调整
- 在设置权限前先查询当前状态，避免重复设置
- 确认文档分享权限是否符合预期

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|-----|------|
| `file_id` | string | ✅ | 文档ID |

**返回字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `file_id` | string | 文档ID |
| `policy` | uint32 | 权限策略，0-私密文档，1-部分成员可见，2-所有人可读，3-所有人可编辑 |

**policy 返回值说明**：

| 值 | 含义 | 说明 |
|----|------|------|
| 0 | 私密文档 | 仅文档所有者可访问 |
| 1 | 部分成员可见 | 仅指定的协作者可访问 |
| 2 | 所有人可读 | 任何获得链接的人都可以查看文档 |
| 3 | 所有人可编辑 | 任何获得链接的人都可以编辑文档 |

> ⚠️ **注意**：当前仅支持返回上述四种权限场景（0/1/2/3），如果文档设置了其他权限类型（如所有人可执行、所有人可标注等），将返回错误。

**调用示例**：

```json
{
  "file_id": "DtDywXFgYFru"
}
```

**返回示例**：

```json
{
  "file_id": "DtDywXFgYFru",
  "policy": 2
}
```

---

### manage.set_privilege

**功能**：根据文档ID设置文档权限。当前仅支持设置文档为所有人可读或所有人可编辑。

**使用场景**：
- 创建文档后设置为所有人可查看，方便团队成员浏览
- 设置文档为所有人可编辑，支持多人协作编辑

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|-----|------|
| `file_id` | string | ✅ | 文档ID |
| `policy` | uint32 | ✅ | 权限策略，2-所有人可读，3-所有人可编辑 |

**policy 取值说明**：

| 值 | 含义 | 说明 |
|----|------|------|
| 2 | 所有人可读 | 任何获得链接的人都可以查看文档 |
| 3 | 所有人可编辑 | 任何获得链接的人都可以编辑文档 |

> ⚠️ **注意**：目前仅支持 policy=2（所有人可读）和 policy=3（所有人可编辑）两种权限设置，其他权限值暂不支持。

**返回字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `trace_id` | string | 请求追踪ID |

**调用示例（设置所有人可读）**：

```json
{
  "file_id": "DtDywXFgYFru",
  "policy": 2
}
```

**调用示例（设置所有人可编辑）**：

```json
{
  "file_id": "DtDywXFgYFru",
  "policy": 3
}
```

**返回示例**：

```json
{
  "trace_id": "trace_xyz"
}
```

---

## 文档导入操作

### manage.import_file

**功能**：将本地文件导入到腾讯云文档。调用后返回task_id，必须配合 `manage.import_progress` 轮询查询导入进度（建议间隔3-5秒），直到progress=100表示导入完成。

**使用场景**：
- 将本地 docx/xlsx/pptx 等文件导入为腾讯云文档在线文档
- 批量迁移本地文件到云端

**支持的文件格式**：`xls`、`xlsx`、`csv`、`doc`、`docx`、`txt`、`text`、`ppt`、`pptx`、`pdf`、`xmind`

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|-----|------|
| `file_name` | string | ✅ | 文件名称（含后缀），如 `report.docx`。支持的文件后缀有xls,xlsx,csv,doc,docx,txt,text,ppt,pptx,pdf,xmind |
| `file_size` | integer | ✅ | 文件大小，单位为字节(bytes)，如 `36752` |
| `file_md5` | string | ✅ | 文件的MD5哈希值，hex编码的32位小写字符串，如 `d41d8cd98f00b204e9800998ecf8427e` |
| `file_base64` | string | ✅ | 文件完整内容经标准Base64编码(StdEncoding)后的字符串，注意不是URL-safe编码 |

**返回字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 导入任务 ID，用于查询导入进度 |

**调用示例**：

```json
{
  "file_name": "report.docx",
  "file_size": 36752,
  "file_md5": "a1b2c3d4e5f6...",
  "file_base64": "UEsDBBQAAAAI..."
}
```

**返回示例**：

```json
{
  "task_id": "144115210435508643_e52cf886-5eae-e61c-c828-a0dddb59703d",
  "trace_id": "trace_xyz"
}
```

> **注意**：由于 `file_base64` 字段可能非常大（文件越大 Base64 字符串越长），建议通过 Python 脚本等方式直接构造 HTTP 请求调用 MCP 接口，避免 AI 模型逐 token 生成 Base64 字符串导致超时或截断。

---

### manage.import_progress

**功能**：根据导入任务 `task_id` 查询导入进度。每隔3-5秒轮询一次，当progress=100时表示导入完成，此时返回file_id和file_url。

**使用场景**：
- 调用 `manage.import_file` 后轮询查询导入状态
- 导入完成后获取生成的云文档 ID 和访问链接

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|-----|------|
| `task_id` | string | ✅ | 导入任务 ID（由 `manage.import_file` 返回） |

**返回字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `progress` | integer | 导入进度百分比（0-100） |
| `status` | string | 任务状态 |
| `file_id` | string | 导入完成后的云文档 ID |
| `file_name` | string | 文档名称 |
| `file_url` | string | 文档访问链接 |
| `error` | string | 错误信息（失败时返回） |

**调用示例**：

```json
{
  "task_id": "144115210435508643_e52cf886-5eae-e61c-c828-a0dddb59703d"
}
```

**返回示例（进行中）**：

```json
{
  "progress": 25,
  "trace_id": "trace_xyz"
}
```

**返回示例（完成）**：

```json
{
  "progress": 100,
  "file_id": "DjVlDHwqVVzs",
  "file_name": "report",
  "file_url": "https://docs.qq.com/doc/DRGpWbERId3FWVnpz",
  "trace_id": "trace_xyz"
}
```

---

## 文档导出操作

### manage.export_file

**功能**：根据云文档 ID 发起导出任务，返回导出任务 ID。需配合 `manage.export_progress` 轮询查询导出进度（建议间隔3-5秒），导出完成后获取file_url下载链接（带签名的临时URL，有效期约30分钟）。

**使用场景**：
- 将云端在线文档导出为本地 docx/xlsx/pptx 文件
- 备份云文档到本地

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|-----|------|
| `file_id` | string | ✅ | 云文档 ID |

**返回字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 导出任务 ID，用于查询导出进度 |

**调用示例**：

```json
{
  "file_id": "DAJpzYoLEpWS"
}
```

**返回示例**：

```json
{
  "task_id": "144115210435508643_0e15f9be-a2ed-b40a-27c2-10561b7c5072",
  "trace_id": "trace_xyz"
}
```

---

### manage.export_progress

**功能**：根据导出任务 `task_id` 查询导出进度。每隔3-5秒轮询一次，当progress=100时表示导出完成，此时返回file_url（带签名的临时下载链接，有效期约30分钟）。

**使用场景**：
- 调用 `manage.export_file` 后轮询查询导出状态
- 导出完成后获取文件下载 URL，通过 curl 等工具下载到本地

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|-----|------|
| `task_id` | string | ✅ | 导出任务 ID（由 `manage.export_file` 返回） |

**返回字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `progress` | integer | 导出进度百分比（0-100），100表示导出完成 |
| `status` | string | 任务状态 |
| `file_name` | string | 导出的文件名 |
| `file_url` | string | 文件下载链接（导出完成后返回，带签名的临时URL，有效期约30分钟） |
| `error` | string | 错误信息（失败时返回） |

**调用示例**：

```json
{
  "task_id": "144115210435508643_0e15f9be-a2ed-b40a-27c2-10561b7c5072"
}
```

**返回示例（进行中）**：

```json
{
  "progress": 50,
  "trace_id": "trace_xyz"
}
```

**返回示例（完成）**：

```json
{
  "progress": 100,
  "file_name": "mcp_import.docx",
  "file_url": "https://docs-import-export-xxx.cos.ap-guangzhou.myqcloud.com/export/docx/...",
  "trace_id": "trace_xyz"
}
```

> **注意**：`file_url` 为带签名的临时下载链接，有效期约 30 分钟，需及时下载。可通过 `curl -L -o <本地路径> "<file_url>"` 命令保存到本地。

---

## 典型工作流示例

### 工作流一：从零在指定目录下创建指定品类文档

```
步骤 1：获取文件夹列表
 → manage.folder_list（判断is_folder=true后获取文件夹id）

步骤 2：创建指定品类文档
 → manage.create_file（传入文件夹id和品类枚举）
```

### 工作流二：按照关键字搜索文件列表

```
步骤 1：搜索文档
 → manage.search_file（传入用户指定的关键词）

步骤 2：处理数据
 → 从返回的文档列表中获取所需的文档信息
 
```

### 工作流三：给指定文档生成副本到指定目录

```
步骤 1：获取文件夹列表
 → manage.folder_list（判断is_folder=true后获取文件夹ID）

步骤 2：按照指定文档ID生成副本
 → manage.copy_file（传入文件夹ID和待生成副本的文档ID）

 
```

### 工作流四：根据关键词搜索后删除文档

```
步骤 1：搜索文档
 → manage.search_file（传入用户指定的关键词，获取文档id）

步骤 2：删除文档
  → manage.delete_file（传入指定的file_id）
 
```

### 工作流五：将本地文件导入为云文档

```
步骤 1：读取本地文件并编码
 → 读取本地文件的二进制内容
 → 计算文件大小（file_size，单位字节）
 → 计算文件 MD5 哈希值（file_md5）
 → 将文件内容进行 Base64 编码（file_base64）

步骤 2：调用导入接口
 → manage.import_file（传入 file_name、file_size、file_md5、file_base64）
 → 返回 task_id

步骤 3：轮询查询导入进度
 → manage.import_progress（传入 task_id）
 → 每隔 3-5 秒轮询一次，直到 progress=100 或返回错误
 → 导入完成后获取 file_id 和 file_url
```

> **特别说明**：由于 `file_base64` 字段数据量大，建议通过 Python 脚本直接构造 HTTP 请求调用 MCP 接口，
> 而非由 AI 模型逐 token 生成 Base64 字符串。示例脚本流程：
> 1. 用 Python 读取文件并计算 md5、base64
> 2. 构造 JSON-RPC 请求体（method: `tools/call`, tool: `manage.import_file`）
> 3. POST 到 MCP 端点 `https://docs.qq.com/openapi/mcp`（携带 Authorization 和 Cookie 头）
> 4. 拿到 task_id 后通过 `manage.import_progress` 查询进度

### 工作流六：将云文档导出到本地

```
步骤 1：发起导出任务
 → manage.export_file（传入 file_id）
 → 返回 task_id

步骤 2：轮询查询导出进度
 → manage.export_progress（传入 task_id）
 → 每隔 3-5 秒轮询一次，直到 progress=100 或返回错误
 → 导出完成后获取 file_url（临时下载链接）

步骤 3：下载文件到本地
 → 使用 curl 或其他 HTTP 工具下载文件
 → curl -L -o <本地保存路径> "<file_url>"
```

> **注意事项**：
> - 导出的下载链接（file_url）为带签名的临时 URL，有效期约 30 分钟，需及时下载
> - 导出的文件格式取决于原始文档类型（doc→docx，sheet→xlsx，slide→pptx 等）

### 工作流七：导入本地文件后再导出验证（完整闭环）

```
步骤 1：导入本地文件
 → 按工作流五执行导入操作
 → 记录返回的 file_id

步骤 2：导出刚导入的文件
 → manage.export_file（传入步骤 1 返回的 file_id）
 → 返回 task_id

步骤 3：轮询导出进度并下载
 → manage.export_progress（传入 task_id）
 → 导出完成后通过 file_url 下载到本地

步骤 4：验证文件完整性
 → 对比原文件与导出文件的大小（可能有微小差异，属正常现象）
 → 导入导出过程中腾讯文档会对文件内部 XML 结构做标准化处理
```

### 工作流八：创建文档并设置分享权限

```
步骤 1：创建文档
 → create_smartcanvas_by_markdown（传入标题和Markdown内容）
 → 返回 file_id 和 url

步骤 2：设置文档权限
 → manage.set_privilege（传入 file_id 和 policy）
 → policy=2 设置所有人可读，policy=3 设置所有人可编辑

步骤 3：分享文档链接
 → 将步骤 1 返回的 url 分享给相关人员
```

### 工作流九：查询文档权限后按需调整

```
步骤 1：查询文档当前权限
 → manage.get_privilege（传入 file_id）
 → 返回 policy：0-私密文档、1-部分成员可见、2-所有人可读、3-所有人可编辑

步骤 2：根据需要调整权限
 → 如果 policy 不符合预期，调用 manage.set_privilege（传入 file_id 和目标 policy）
 → policy=2 设置所有人可读，policy=3 设置所有人可编辑
```