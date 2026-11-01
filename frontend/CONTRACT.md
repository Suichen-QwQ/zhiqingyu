# 栀情屿 前后端契约

**版本：2026-10-29（P0 + P1 + P2 全量）**
上一版停在 2026-08-30，只写了 `/api/chat` 一条，此后新增的安全层、提问卡片、回合中插话、
归档包、缺失摘要检测、状态页后台可见性全部没有记录 —— 本文档重写补齐。

- 后端：`backend-live/chat_server.py`（单文件、纯标准库、Python 3.6 兼容、监听 8092）
- 前端：`frontend/index.html`（单文件、全部 CSS/JS 内联、**CRLF**）
- 线上：nginx 挂在 `/zhiqingyu/` 前缀下，所以前端**一律用相对路径**（`api/chat`，不是 `/api/chat`）

> 改接口时请同时改本文档和 `MANIFEST.txt`（`python scripts/gen_manifest.py` 重生成）。

---

## 0. 通用约定

### 0.1 URL 前缀

前端请求写相对路径（`fetch('api/chat')`），部署在 `/zhiqingyu/` 下时自然带上前缀。
后端 `do_GET` 里的静态服务会剥掉 `^/zhiqingyu`；`/api/*` 的路由匹配用
`re.search(r'/api/xxx$', path_only)`，**先剥 query string**再匹配。

### 0.2 响应格式

- 所有 JSON 响应都是 `application/json; charset=utf-8`，`json.dumps(..., ensure_ascii=False)`。
- 所有出站 JSON 在序列化前都会过一遍 `strip_lone_surrogates()`：任何 `[:n]` 截断都可能把
  一个 emoji 切成半个代理项，`json.dumps` 会把它写成 `\ud83d`，严格解析器（含网关）
  直接回 **400 `unexpected end of hex escape`**。
- 错误响应统一是**扁平**的 `{"error": "<人话>", "error_code": "<机器码>", ...}`，不套壳。

### 0.3 错误码

| HTTP | error_code | 触发条件 |
|---|---|---|
| 400 | `application/json` 解析失败 / `unknown ... action` / `nothing to write` | 请求体不合法 |
| 400 | `archive_bad_zip` | 归档导入时上传的不是 zip |
| 409 | `ask_expired` | 提问卡片已过期或已回答 |
| 409 | `no_session` / `empty_text` / `no_active_turn` | 插话被拒绝 |
| 413 | `archive_too_large` | 归档包超过 32 MB |
| 502 | `model_unavailable`（`LLMUnavailable.payload()`） | 整条模型链都失败 |
| 502 | `tts_unavailable` | Azure TTS 报错 |
| 503 | `tts_unconfigured` | 没配 TTS 或 `ZQY_TTS_OFF=1` |

502 的 `model_unavailable` 体里带逐模型失败原因（`detail` / `tried`），前端渲染成可重试提示。

### 0.4 前端安全纪律

- 服务端返回的一切文本都当**纯文本**：入库前走 `esc()` 再过 `innerHTML`，绝不用
  `innerHTML` 直接塞模型输出。AI 正文例外（走 `mdRender`，但 `mdRender` 内部先转义）。
- 新增的 DOM 一律 `textContent` 赋值（P2 的提问卡片就是这么写的）。

---

## 1. `POST /api/chat` —— 主对话

### 1.1 请求体

```jsonc
{
  "message": "……",            // 必填，服务端截断到 1500 字
  "history": [{"role": "me"|"ai", "text": "…"}],   // 前端保留的上下文，服务端只取最后 20 条
  "persona": {"name": "屿", "traits": [...], "style": "…"},   // 人格配置，可省
  "user": {"name": "…", "gender": "…", "desc": "…"},          // 用户档案，可省
  "think": false,              // 是否要 reasoning（用 reasoner_model）
  "memorize": true,            // 是否允许后端自动写记忆
  "profile_id": "p_xxx",       // 多档案隔离用的文件名 stem，缺省 default
  "session_id": "s_xxx",       // 【P2】回合中插话要用它；不带就等于关掉插话能力
  "summary": "…",              // 前端维护的会话摘要（服务端截断到 800 字）
  "summary_meta": {"rounds": 12, "omitted": 0, "tail": 20},   // P7 记账
  "folded": 8,                 // 老前端字段：已折叠的消息条数
  "folded_total": 20,
  "stream": true               // true → SSE；false/缺省 → 一次性 JSON
}
```

### 1.2 非流式响应（`stream` 为假）

```jsonc
{
  "text": "回复正文",
  "emo": "平静",                // 六选一，见 §6
  "theme": "工作疲惫",          // 自由字符串，前端只展示；**可以为空串**，见下方说明
  "emote": "326_xxx.gif",       // 命中的表情文件名，可能缺省（前端必须容错，见下方说明）
  "reasoning": "…",             // 仅 think=true 时返回
  "sources": [{"title": "…", "url": "…"}],
  "citations": [{"n": 1, "text": "…", "cat": "…", "created": "…"}],
  "search_status": "ok|empty|not_needed",
  "risk": { … },                // 【P0】中/高风险才有，见 §5
  "context": { … },             // 本轮上下文面板，见 §4
  "summary": "…",               // 服务端回写的新摘要
  "summary_meta": { … },
  "remembered": true,           // 本轮是否写了记忆
  "memupdate": { … },           // 记忆变更明细，可能没有
  "forgot": true, "forgot_raw": "…"
}
```

`kind` 字段走同一路径但语义不同：

- `{"kind": "title", "message": "<首轮对话摘要>"}` → `{"title": "…"}`（自动起会话名）
- `{"kind": "gen_persona", ...}` → 生成人格草稿


**关于 `emote` 何时出现（2026-10-30 起）**

这个字段**不再是「几乎每条都有」**，三种情况会缺省：

1. 模型本轮没写表情标记（默认 `ZQY_EMOTE_FREQ=normal` 下这是正常的，不是故障）；
2. 安全层把这一轮判为 `risk.level === "high"`（自伤/自杀意念）——此时刻意不贴表情：
   同一轮既给求助资源又挂一张表情是自相矛盾的。注意 `emo` 字段**仍然保留**，
   情绪日记与统计不受影响；`medium` 档**不**受影响，绝望/低落时照贴。
3. 模型写的表情名匹配不到唯一文件（`_match_emote` 只接受唯一命中，宁可这轮不配，
   也不贴一张明显不对的图）。

因此前端渲染必须写成「有就显示、没有就不显示」，不要拿 `emote` 缺失当异常上报。
现有实现（`frontend/index.html` 里的 `if(m.role==='ai'&&m.emote)`）已经是对的。

运维侧可调 `ZQY_EMOTE_FREQ`（`low|normal|high|always`）与 `ZQY_EMOTE_POOL`（`all|core`），
详见 `backend-live/.env.example`。

**关于 `theme` 可以是空串（2026-10-30 起）**

`theme` 表达的是「这一轮聊的话题」，没有可概括的话题时**返回空串**，不再兜底成
`此刻的心情`。旧的兜底值会被当成真实主题写进日记条目，实测用户 19 条日记里
16 条都是它，统计页的「高频主题 Top5」长期被它占着，那段统计等于没有信息量。

约束：

1. **前端不得把空串改写成任何词**。`normalizeDB` 只补类型（`typeof m.theme !== 'string'`
   → `''`），展示时才用 `it.theme || '此刻的心情'` 补缺省文案——用户看到的话没变，
   但数据里不再凭空多一个主题。
2. 统计聚合（`frontend/index.html` 的 `statsFor(days)`）除了 `if(it.theme)`，还要排除历史遗留的
   `此刻的心情`：旧数据不重写（用户数据只读），但不再让它继续霸榜。
3. Markdown 导出同样先 `filter(it => it.theme)`，否则会输出「（低落）」这种空壳。

### 1.3 流式响应（`stream: true`，SSE）

`Content-Type: text/event-stream`，每条 `event: <名字>\ndata: <JSON>\n\n`。
**未知事件类型前端必须忽略**（老前端遇到新事件不会崩，这是加事件的兼容前提）。

| event | data | 说明 |
|---|---|---|
| `thinking` | `{}` | 开始吐 reasoning（仅 think） |
| `delta` | `{"text": "…"}` | 正文增量，前端累加 |
| `searching` | `{}` | 触发了搜索，前端显示「正在查资料」 |
| `ask` | `{ask_id, question, options, allow_custom_input, multiple, timeout}` | 【P2】提问卡片，见 §3 |
| `turn` | `{"messages": ["…"], "index": 1}` | 【P2】用户在生成过程中补充了话，见 §3.2 |
| `error` | `{error, error_detail, error_code}` | 本轮失败，前端显示重试气泡 |
| `done` | 同 §1.2 的完整对象 | 收尾；`failed:true` 表示这一轮失败 |

前端处理提醒：

- `done` 用 `Object.assign(m, done)` 合并，所以**新增 `done.*` 字段零协议改动**。
- `event: ask` 会暂停生成直到用户作答或超时（默认 120 秒），期间正文可能还是空的。
- `event: turn` 之后紧跟一条内容为 `"\n\n"` 的 `delta`，再继续正文。

### `POST /api/storage` 的两个新约定（2026-10-30 起）

> **这两条源自一次真实的数据丢失事故**：2026-10-30 18:13，线上整包云端数据被
> 一个「新浏览器打开站点」的空库覆盖（14 会话 / 113 消息 → 1 空会话）。已从备份
> 完整还原。根因与修法见 `docs/运维笔记/SKILL.md` 的「云端数据被清空」症状索引。

**① 后端拒绝用空库覆盖非空云端**

`data` 判定为「空」（无任何会话消息、无日记条目/narrative/manual/mood）而云端现有内容
非空时，若请求体没有 `clear: true`，后端返回 **409**：

```json
{
  "ok": false,
  "error": "refuse to overwrite non-empty storage with empty data",
  "error_code": "empty_overwrite_blocked",
  "hint": "如果确实要清空，请带 clear:true"
}
```

「清空全部数据」必须显式带 `clear: true`，否则前端会把用户的清空操作变成静默失败。

**② 前端在读到云端内容之前不许写**

`frontend/index.html` 里有 `cloudState` 状态机，`cloudSync()` 在 `pending` 和 `error`
阶段直接 return：

| 状态 | 含义 | 允许写云端 |
|---|---|---|
| `pending` | 还没拿到 `GET /api/storage` 的结果 | ❌ 绝不许 |
| `restored` | 云端内容已装进 DB | ✅ |
| `empty` | 云端确认是空的 | ✅ |
| `error` | GET 重试 3 次（1s/2s/3s）仍失败 | ❌ 不写，保护云端 |

**改前端时不要拆掉这个门禁**：`dbLoad()` 是同步执行的，localStorage 为空时会立刻
`newSession()` + `profileId()` → `dbSave()`，400ms + 900ms 后就会 POST。如果此时
GET 还没回来（323KB 云端包 + 公网 RTT 很容易超过 1300ms），空库就会先落地。

回归测试：`python .eval/test_cloud_guard.py`（40 项）、
`node .eval/e2e_cloudguard_slow.mjs`（11 项，用延迟 8 秒的 GET 精确复现事故时序）。

---

## 2. `POST /api/answer` —— 回答提问卡片【P2】

```jsonc
{"ask_id": "ask-xxx-1", "selected": ["就陪我待着"]}   // 或者
{"ask_id": "ask-xxx-1", "answer": "我自己写的话"}     // 或者
{"ask_id": "ask-xxx-1", "cancelled": true}            // 或者 "先不回答"
```

三选一，**只带一种字段**。命中 → `200 {"ok": true}`；
过期或已回答 → **`409 {"ok": false, "error": "这个问题已经过期了", "error_code": "ask_expired"}`**。

前端不要在 409 时静默 —— 说明用户点慢了，要提示「这个问题已经过期了」并禁用按钮。

## 3. `POST /api/inbox` —— 回合中插话【P2】

```jsonc
{"session_id": "s_xxx", "message": "顺便说一句，我明天要早起"}
```

- 200 `{"queued": true, "seq": 1, "pending": 1}`
- **409**，`error_code` ∈
  - `no_session`：没带 session_id
  - `empty_text`：文本为空
  - `no_active_turn`：这一轮已经结束了（前端应退回「原地排队」，本轮结束后再发）
  - 另有「队列满（5 条）」的拒绝分支

后端行为：本轮生成结束后 drain 一次，把补充的话作为 `event: turn` 前的 user 消息接着写，
**只续写 1 轮**，且要求已有正文。

## 4. `GET /api/status` —— 后台任务可见性

只读，不调模型、不写盘。读不到的部分如实回空，前端画灰色，不报错。

```jsonc
{
  "ok": true, "profile_id": "…",
  "memory": {"v2": true, "total": 6, "pinned": 1, "chars": 1375, "budget": 4000,
             "last_used": "2026-10-28", "cats": {"pref": 2}, "cap": 200,
             "dropped": {"count": 0, "at": ""}},
  "recall": {"on": true, "months": 12, "days": 30, "items": 5, "pending": 0,
             "chars": 1200, "updated": 1793200682},
  "tts": {"configured": true, "off": false, "voice": "zh-CN-XiaoxiaoNeural",
          "cache": 12, "cache_max": 300},
  "flags": {"memory_v2": true, "retrieve": "b", "retrieve_note": "…", "recall_on": true},
  "safety": {"enabled": true, "hotlines": ["12356", "120", "110"], "note": "已开启：…"},
  "assist": {"ask_timeout": 120, "ask_waiting": 0, "inbox_active": 0,
             "archive_max_mb": 32},              // 【P2】
  // 表情策略（2026-10-30）：freq 四档 low|normal|high|always；pool_mode all|core；
  // files/pool 是实际可用个数（均 352），core 是精选子集里能解析到文件的个数（102）；
  // fallback_on 为 true 表示模型没写标记时后端会兜底补一张（仅 always 档）。
  // 缺字段（旧后端）时前端整块隐藏，不报错。
  // 【2026-10-31】history 里的 ai 消息要带 emote 字段（表情文件名），后端据此反查
  // 名字、拼「最近配过哪些」提示进末条 user；不带则模型对自己上一轮发过什么零感知。
  "emote": {"freq": "normal", "pool_mode": "all", "files": 352, "pool": 352,
            "core": 102, "fallback_on": false},
  "context": { … }
}
```

## 5. `out.risk` —— 安全层输出【P0】

只有 `level` 为 `medium` / `high` 时才有 `risk` 字段；`low` 时**整个字段不出现**。
`ZQY_SAFETY=0` 时永远不出现。

```jsonc
{
  "level": "high|medium",
  "kind": "self_harm|despair",
  "resources": [{"name": "全国心理援助热线", "tel": "12356"},
                {"name": "急救", "tel": "120"},
                {"name": "报警", "tel": "110"}],
  "note": "你刚才说的这些，我不想轻描淡写地带过去。",
  "disclaimer": "屿是陪伴型 AI，不是心理咨询师或医生，不能替代专业诊断与治疗。如果你正处在危险中，请联系上面的人。"
}
```

设计约束（改之前先读）：

1. **只升级不降级** —— 关键词检测只能把级别往上抬，不能压低模型自己的判断。
2. **软引导不拦截** —— 永不改写/截断模型回复，只额外附资源。
3. 资源只用官方号码，不编造。

## 6. `emo` 白名单（前端 `EMO` 表，四行可改）

| emo | score | bucket |
|---|---|---|
| 平静 | 80 | 平静 |
| 平静偏暖 | 84 | 平静 |
| 愉悦 | 90 | 愉悦 |
| 焦虑 | 45 | 焦虑 |
| 疲惫 | 52 | 低落 |
| 低落 | 30 | 低落 |

不在表里的值前端一律回落 `平静/80`。**要加新情绪，先改前端 `EMO` 表（四行）再发**，
否则情绪点 / 日历色块 / 四桶统计全变默认值。
`BUCKETS = ['平静','焦虑','愉悦','低落']`。

## 7. 其余接口速查

### 记忆

- `GET /api/memory?profile_id=…` → `{items, items_v2?, stats?, v2}`
  - `items_v2` 仅 `ZQY_MEMORY_V2=1` 时返回；关闭时**不读也不算**，避免只读请求顺手落盘。
  - `stats = {total, pinned, dropped_last, dropped_count}`
- `POST /api/memory` 的 `action`：`clear` / `delete` / `add` / `update` / `pin` /
  `search` / `restore` / `merge` / `replace` / `migrate`

### 存储整包（会话 + 日记 + 元信息）

- `GET /api/storage` → `{data: <blob|null>, updated: <str|null>, revision: <str|null>}`
- `POST /api/storage {"data": <blob>, "expected_revision": <str|null>}` → `{ok: true, updated: "<stamp>", revision: "<新版本>"}`
  - 写入须携带读取到的版本；过期返回 409 `storage_conflict`，缺版本返回 428。
  - 原子写（独立临时文件 + `os.replace`），清空须显式传 `clear: true`。
  - 应使用隔离的临时数据目录测试，不得写入真实用户数据。

### 共同回忆

- `GET /api/recall?profile_id=&months=12` → `{ok, enabled, months, updated, days, items,
  counts, chars, tokens, shared, pending}`
- `GET /api/recall?missing=1&months=12` → **【P2】** `{ok, enabled, months, ref, count,
  missing: [{type, key, label, start, end, chars, days}]}`
  - **未结束的周期不算缺**；材料判断与 `build_recall` 同一套；有交集即算已有
- `POST /api/recall {"action": "build", "days": {...}, "months": 12, "force": false, "max_calls": 6}`
- `POST /api/recall {"action": "clear"}`

### 归档包【P2】

- `GET /api/archive?profile_id=` → `application/zip`，
  `Content-Disposition: attachment; filename="zqy-archive-YYYYmmdd-HHMMSS.zip"`，
  `Cache-Control: no-store`
  - 内容：`manifest.json`（`{v, created_at, files}`）+ `storage.json` + `memories/*` + `recall/*`
  - **不含 `settings.json`**（里面有 api_key）
- `POST /api/archive?action=import[&force=1]`，body 是**原始 zip 字节**
  （`Content-Type: application/zip`，不套 JSON）
  - 前端要**先用 `readAsArrayBuffer` 读、先拦 32MB**
  - 响应 `{ok, storage: 'restored'|'skipped_has_data'|'failed', memories, recall, skipped, manifest, restored}`
  - 默认**不覆盖**已有 storage；`force=1` 才覆盖
  - >32MB → 413 `archive_too_large`；非 zip → 400 `archive_bad_zip`

### 语音

- `POST /api/transcribe`（原始音频字节，`?lang=zh-CN&rate=16000`）→ `{text}`
  - 这个分支在 JSON 解析**之前**，别给它包 JSON
- `POST /api/tts {"text": "…", "voice": "…", "rate": "+0%", "format": "…"}` → `audio/mpeg`
  - 响应头 `X-TTS-Chunks` / `X-TTS-Cache`
  - 未配置或 `ZQY_TTS_OFF=1` → 503 `tts_unconfigured`
- `GET /api/tts/voices` → 音色列表

### 设置

- `GET /api/settings` → `{base_url, model, reasoner_model, timeout, has_key, key_tail,
  key_from: 'saved'|'server', fallbacks: [...], max_fallbacks}`
  - **绝不回传 Key 明文**，只给「有没有 + 后 4 位」
- `POST /api/settings`：`api_key` 语义 —— 非空=替换；`clear_key=true`=清除并回落 `.env`；
  **缺省或空串=保持原样**（这条必须守住，否则前端回显不了明文就会误清 Key）
  - `fallbacks` 最多 3 条，备份继承主模型的 key（为空时）
- `POST /api/settings/test {"base_url","api_key","model","timeout","chat"}` → 探测结果

### 日记

- `POST /api/diary {"action": "gen", "texts": [...]}` → `{narrative}`

### 其他

- `GET /health` → `{ok: true}`
- 静态资源：只放行 `index.html` 与 `assets/` 下的文件

---

## 8. 数据模型（前端 `localStorage`）

```jsonc
{
  "v": 1,
  "sessions": [{
    "id": "s_xxx", "title": "…", "created": 0, "updated": 0,
    "msgs": [{
      "id": "…", "role": "me|ai", "text": "…", "ts": 0,
      "emo": "…", "theme": "…", "tide": 0, "failed": false,
      "reasoning": "…", "emote": "…",
      "sources": [...], "citations": [...], "risk": {...},
      "asks":  [{ask_id, question, options, …}],   // 【P2】提问卡片
      "turns": [["补充的话", "…"]]                 // 【P2】回合中插话
    }],
    "summary": "…", "summary_meta": {...}
  }],
  "activeId": "s_xxx",
  "diary": {"2026-10-28": {"mood": "…", "n": 3, "narrative": "…", "manual": "",
                           "created": 0, "items": [{"ts": 0, "theme": "…", "emo": "…"}]}},
  "meta": {"savedAt": 0, "flags": {...}}
}
```

`normalizeDB()` 会给老消息补默认字段，并对 `risk` / `asks` / `turns` 做容错
（非数组直接 `delete`）。新增持久化字段必须在 `normalizeDB` 里被容忍，
否则读回来会被丢掉。

---

## 9. 已有前端能力清单（别重复实现）

- 12 秒超时 → 失败气泡 + 重试按钮（流式另有「兜底超时 / 用户停止 / 断流」三种文案）
- 离线横幅（sticky，39px，补偿 flex 高度）
- 发送排队 `pendingQueue`（打字中连发 4 条已测）
- 「换个说法」发 `avoid` 带上一句 AI 原文
- 备份导出/导入（JSON，`memory_v2` 优先于旧 `memory`）、Markdown 导出、修复数据
- TTS（`window.zqyTts`）、共同回忆（`window.zqyRecall`）、上下文面板（`window.zqyCtx`）、
  状态页（`window.zqyStatus`）、提问卡片（`window.zqyAsk`）、风险提示卡
- 用户端表情面板按钮**故意隐藏**（`#emoBtn` 带 `hidden`，表情改为 AI 自动配），
  不要用「打开表情面板」去验证表情功能


## 10. 聊天动效、模型候选与官方搜索（2026-10-31）

- SSE `delta.text` 以新片段淡入；已读文本不重播。最后一批淡入结束后排版 Markdown，思考栏、AI 表情、心情潮汐和来源栏使用相同时长与缓动入场。历史恢复不重播，减少动态效果时保留短淡入并取消位移。
- 设置中的普通模型、思考模型均为可手填的组合框；拉取后可展开完整候选列表，不按已有模型名过滤。支持方向键、Enter、Escape；切换地址清空旧候选。
- 生效服务地址为 `https://api.deepseek.com` 或其 `/v1` 路径时，所有 `web_search` 执行走官方 `POST https://api.deepseek.com/v1/tools/search`，复用服务端保存的 Key。请求体为 `{query, count, need_content:false}`，将 `results` 归一为现有 `sources`，无需修改 SSE 或聊天返回字段。
- 官方搜索不可用时沿用 `search_status:empty` 提示，不改用其他搜索商；其他网关保留现有千帆/Tavily/Bing 路径。缓存按搜索商、账号和数量隔离。
- 参考：[DeepSeek 官方 Search API](https://api-docs.deepseek.com/api/search/)。本接入直接使用官方搜索服务，适用于当前的 Chat Completions 工具循环。

记忆 `merge` 动作在服务端加锁合并字符串或结构化条目，保留现有条目和元数据；`replace` 则显式覆盖整表。前端与后端应一同更新。
