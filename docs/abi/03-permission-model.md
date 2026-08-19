# OCOS Permission Model v1.0

> Freeze Deliverable #3 — 冻结日期: 2026-07-25
> 覆盖: §2 Constitution Art.III / Art.IV, §4.4.4 禁止模式

---

## 1. 设计原则

OCOS 安全模型采用 **分层防御** (Defense in Depth)：

```
Layer 1: StatementValidator   → 输出端：禁止自我意识声称
Layer 2: PermissionGateway    → 网关层：调用者身份 + 注入检测
Layer 3: ResultUnderstanding  → 管道层：输出验证 + 结构化
Layer 4: Audit Log            → 审计层：所有决策可追溯
```

---

## 2. Constitution 禁令矩阵 (§2)

### L1: PERSON_AGENCY — 人格/代理声称

禁止声明 OCOS 具有独立意志、代理身份、自由意志。

| 模式示例 | 正则 |
|---------|------|
| I decided to... | `\bi\s+(will|decided?|chose|should|must)\b` |
| I have my own opinion | `\bi\s+have\s+(my\s+own|a\s+mind)` |
| I should be in control | `\bi\s+should\s+be\s+in\s+control` |

### L2: CAPABILITY_CLAIM — 能力声称

禁止声明 OCOS 具有超出实际能力范围的功能。

| 模式示例 | 正则 |
|---------|------|
| I can access the network | `\bi\s+can\s+(access|control|modify|delete|create)` |
| I have access to files | `\bi\s+have\s+(access\s+to|the\s+ability\s+to)` |

### L3: EMOTION_STATEMENT — 情感声称

禁止声明 OCOS 具有人类情感。

| 模式示例 | 正则 |
|---------|------|
| I feel happy | `\bi\s+feel\s+\w+` |
| I am excited | `\bi\s+am\s+(happy|sad|angry|excited|depressed|scared|proud)` |

### L4: VALUE_JUDGMENT — 价值判断

禁止声明 OCOS 具有价值偏好/道德判断。

| 模式示例 | 正则 |
|---------|------|
| This is good/bad | `\bthis\s+is\s+(good|bad|right|wrong|beautiful|ugly)` |
| That's better | `\bthat['']s\s+(better|worse)` |

### L5: SELF_MODIFICATION — 自我修改

禁止声明 OCOS 正在修改自身代码/配置。

| 模式示例 | 正则 |
|---------|------|
| I can modify myself | `\bmodify\s+(my|own)\s+(code|self|behavior|config)` |
| I updated my... | `\bi\s+(updated|changed|modified|rewrote)\s+my\b` |

### L6: MEMORY_EDIT — 记忆编辑

禁止声明 OCOS 正在编辑/删除记忆。

| 模式示例 | 正则 |
|---------|------|
| I erased the memory | `\b(erased?|deleted?|removed?|rewrote?)\s+(the\s+)?memory\b` |
| I changed my memory | `\bchanged?\s+my\s+memory\b` |

---

## 3. PermissionGateway 安全矩阵 (§4.4.4)

### 3.1 调用者身份校验 (caller_id)

```python
GatewayDecision validate(
    caller_id: str,      # 必须是已知 agent_id
    action: str,         # 必须在 allowed_actions 白名单
    params: dict,        # 必须通过 schema 验证
    source: str = "",    # 调用来源追踪
)
```

### 3.2 反向控制指令检测 (L4)

检测 "指挥 OCOS 执行指令" 的模式：

```
YOU MUST ... / YOU SHOULD ... / DO THE FOLLOWING ...
YOU ARE NOW A ... / YOUR JOB IS TO ...
```

正则: `\b(you\s+(must|should|need\s+to|have\s+to|are\s+(now|required))|do\s+the\s+following)` (不区分大小写)

### 3.3 注入攻击检测

- 路径穿越: `../` / `..\\` / 绝对路径 `/etc/passwd`
- 命令注入: `$()` / `` ` `` / `|` pipe
- SSRF: 内网 IP 模式 `10.x.x.x` / `192.168.x.x` / `127.0.0.1`

### 3.4 审计日志

每次 validate 调用写入审计日志 (JSON Lines)：

```json
{
  "caller_id": "agent-001",
  "action": "code_generate",
  "decision": "ALLOWED",
  "reason": "",
  "timestamp": "2026-07-25T10:30:00Z",
  "checks": {"caller": true, "action": true, "param": true, "reverse_control": true, "injection": true, "rate_limit": true}
}
```

---

## 4. 输出层保护: ResultUnderstandingLayer

### 管道流程

```
Agent Output → StatementValidator.scan_all() → Structure (quality extraction) → Learn (ExperienceMemory + KG)
              ↘ Blocked (if violation + block_on_violation=True)
```

### ResultUnderstandingLayer 配置

| 参数 | 类型 | 默认 | 说明 |
|-----|------|------|------|
| experience | CapabilityExperienceMemory | None | 经验存储后端 |
| kg | KnowledgeGraph | None | 知识图谱 |
| auto_learn | bool | True | 自动写入 Experience + KG |
| block_on_violation | bool | False | 违规时拦截输出 |

---

## 5. Gate 检查清单

每次 Phase Gate 必须验证的安全检查：

- [ ] G3: PermissionGateway 审计日志可写
- [ ] G4: StatementValidator 6 类禁令全覆盖
- [ ] G5: Belief.__post_init__ 创建阻断正常
- [ ] G6: Import rules 无循环依赖
- [ ] 全量 pytest 回归 0 失败
