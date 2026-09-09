# 明天验收测试

## 今天做了什么

给 OCOS 一个 HUMAN 目标，让它自己学习认知架构/智脑原理：

```
GOAL-HUMAN-16A2C36A  (HUMAN origin, status=ACTIVE)
  "学习认知架构与智脑原理，调研 LLM Agent 自主学习机制，
   沉淀为知识并生成自我能力提升方案"
```

OCOS 已经：
1. daemon 认领 goal → ACTIVE ✅
2. 自我反思注入 retrospect hint (2146 chars)
3. 知识提示注入 self knowledge hint (450 chars)  
4. 调 LLM (deepseek) 成功 → 200 OK
5. PLANNER-OUT → GitHub 搜索 LLM agent autonomous learning

## 明天验收清单（一键脚本已在 /tmp/octest.py）

### 快速运行

```bash
# 一键验收（12 个章节自动跑）
python3 /tmp/octest.py && cat ~/.ocos/acceptance_report.md

# 只看关键指标
python3 -c "
import sqlite3; from pathlib import Path
DB = str(Path.home()/'.ocos'/'ocos.db')
c = sqlite3.connect(DB)
print('=== Goal 状态 ===')
print(c.execute(\"SELECT id, status, progress FROM goals WHERE id='GOAL-HUMAN-16A2C36A'\").fetchone())
print('=== Episodes 新增 ===')
print(c.execute('SELECT COUNT(*) FROM episodes WHERE created_at > datetime(\"now\",\"-12 hours\")').fetchone()[0])
print('=== knowledge 表 ===')
for r in c.execute('SELECT id, substr(statement,1,60) FROM knowledge ORDER BY id DESC LIMIT 10'):
    print(f'  {r[0][:20]} | {r[1]}')
print('=== wisdom 新增 ===')
for r in c.execute('SELECT wisdom_id, substr(principle,1,80) FROM wisdom_items ORDER BY wisdom_id DESC LIMIT 5'):
    print(f'  {r[0]} | {r[1]}')
print('=== belief 新主题 ===')
for r in c.execute('SELECT substr(statement,1,80), confidence FROM belief WHERE created_at > datetime(\"now\",\"-12 hours\") ORDER BY id DESC LIMIT 10'):
    print(f'  conf={r[1]:.2f} | {r[0]}')
print('=== pattern 新 ===')
for r in c.execute('SELECT substr(trigger_condition,1,50), confidence FROM pattern ORDER BY id DESC LIMIT 5'):
    print(f'  conf={r[1]:.2f} | {r[0]}')
print('=== daemon heartbeat ===')
import json
hb = json.loads(open(Path.home()/'.ocos'/'daemon_heartbeat.json').read())
print(f'  cycle={hb[\"cycle\"]} autonomy={hb[\"autonomy_level\"]} braked={hb[\"braked\"]}')
"
```

### 验收标准

| 指标 | 期望 | 说明 |
|------|------|------|
| goal 状态 | ACTIVE 或 COMPLETED | 没卡就行 |
| episodes 新增 | ≥ 20 行 | 有 researcher.execute / goal_result |
| knowledge 表 | ≥ 10 行 | 认知架构相关三元组 |
| belief | 新主题 | 关于智脑/认知架构的新 belief |
| wisdom | ≥ 7 → 增长 | 新 principle |
| autonomy_metrics | completion_rate ↑ | 自主目标完成率 |
| daemon cycle | 持续增长 | 没卡壳 |
| daemon logs | web_research / llm_tutor 有记录 | 外部学习渠道跑了 |

### 关键表查询

```sql
-- OCOS 今天新产出的 episode
SELECT action, substr(decision,1,80) 
FROM episodes 
WHERE created_at > datetime('now','-12 hours')
ORDER BY created_at DESC LIMIT 20;

-- 新 belief（非模板化）
SELECT substr(statement,1,80), confidence 
FROM belief 
WHERE created_at > datetime('now','-12 hours')
ORDER BY id DESC;

-- 新 knowledge
SELECT substr(statement,1,80), confidence, scope_domain 
FROM knowledge 
ORDER BY rowid DESC LIMIT 10;

-- 新 pattern（condition=agent=X 格式）
SELECT substr(trigger_condition,1,60), confidence 
FROM pattern 
ORDER BY rowid DESC LIMIT 10;
```
