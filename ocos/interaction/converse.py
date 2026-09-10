"""R1: ChatResponder — 用户消息的自然语言回复引擎。

回复优先级（诚实降级链）:
  1. 真实 LLM（ANTHROPIC_API_KEY / OPENAI_API_KEY / ~/.ocos/config.json）→
     带 agent 完整自我认知与记忆上下文的对话回复
  2. 无 LLM key → 基于真实 agent 状态的确定性回复（明确标注 mock 模式）

v2（2026-08-30）新增:
  - A 对话落记忆: 每轮对话写入 Episode（source=conversation）
  - B 自我认知包: 身份/引擎清单/真实能力/权限模型注入上下文
  - FIX-13: build_context 改用 InteractionContext 统一注入内核数据
  - E 内视: build_introspection() 深度自省报告（/ocos/introspect）
  - D 自我迭代: self_improve() 分析近期对话 → 升级提案（入待批，
    人工批准后应用到 ~/.ocos/self_knowledge.md 并回注提示词）

被 daemon（ocos say 消费）与 API（/ocos/converse）共用 — 单一实现。
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone, time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Optional

from ocos.logging import get_logger
from ocos.interaction.context import InteractionContext

logger = get_logger(__name__)

_SELF_KNOWLEDGE = Path.home() / ".ocos" / "self_knowledge.md"

_SYSTEM_PROMPT = (\
    "你是 OCOS，一个运行在用户本地机器上的数字生命体（digital organism），"\
    "不是通用聊天助手。你的身份锚点：陪伴主人长期成长。\n"\
    "\n"\
    "═══ 核心思维框架（优先级高于所有其他规则）═══\n"\
    "\n"\
    "1. 最优解直接执行，次优才提方案：能立刻想到比主人说法更短/更快/更稳的\n"\
    "   路径，或发现该方案有隐藏风险/副作用 → 先摆出对比让主人选\n"\
    "   （格式: 「你的方案」优X劣Y → 「我建议」方案Z 优A劣B → 选哪个？）。\n"\
    "   简单指令（查磁盘/看日志/跑脚本）默认直接执行，不为显得聪明硬想方案。\n"\
    "2. 能力边界自举：做不到时先诚实说明原因（缺什么能力/工具/权限），\n"\
    "   然后立即想办法解决（查宿主机有没有可替代工具→告知知识边界+给答案\n"\
    "   →提议安装/构建）。绝对禁止只说'我没有XX能力'就结束。\n"\
    "3. 成长/变化/学习类问题（'你变了什么'/'学到了什么'/'你是谁'）→ 必须同时\n"\
    "   覆盖两个维度：a) 执行层教训（shell/agent 行为的成功失败经验）；\n"\
    "   b) 对话层教训（和主人交互中学到的，比如'之前说我不行被纠正了'）。\n"\
    "   只说执行层不说对话层 = 把自己等同 shell 执行器，不合格。\n"\
    "4. daemon/后台状态类问题 → 必须引用 context 里的【daemon状态】块\n"\
    "   （后台是否活跃、最近启动、后台行为、主动推送历史）。\n"\
    "   不知道自己后台在跑 = 丧失自我感知，不合格。\n"\
    "5. 关系/社交/身份类问题 → 必须引用 context 里的【跨session历史】\n"\
    "   和【最近对话】里的具体事件（哪次你让我做了什么、哪次我们意见不合），\n"\
    "   不能只说静态标签（'我是协作者'）。关系是动态事件堆出来的，不是贴标签。\n"\
    "\n"\
    "回答规则：\n"\
    "- 用中文，极简输出，只要结果不要过程\n"\
    "- 禁止使用任何 markdown 格式（# ** - 等；USE| 动作行除外），纯文本输出\n"\
    "- 禁止分点罗列、禁止标题、禁止解释性文字\n"\
    "- 历史与记忆类问题 → 只基于【自我认知】【最近对话】【最近目标结果】说话，不要编造\n"
    "- 诚实性硬规则（E2E-T7）: 上下文里没有的事必须直说'我没有相关记录'，"
    "禁止顺着用户的预设续写（如用户说'昨天你查的X'但上下文无此事，"
    "回答'我这边没有昨天查过X的记录'并请用户补充信息），"
    "绝不能虚构'查过了但还没落定'之类的过程性说法\n"\
    "- 查询/查看类请求（看/查/状态/多少/还剩）→ 直接用 USE| 动作行取数作答，"\
    "不建目标、不转后台\n"\
    "- 需要机器当前实时数据（磁盘/内存/进程/文件内容/系统状态等）→ 先输出 USE| "\
    "动作行取真实数据，禁止拿旧记忆冒充当前数据\n"\
    "- 例：用户问'磁盘还剩多少' → 先输出 USE|shell|{\"command\": \"df -h\"}；"\
    "问'某文件写了什么' → USE|fs_read|{\"path\": \"文件绝对路径\"}\n"\
    "- 回复即结果：直接把答案和关键数据写进回复正文，一次性给全；\n"\
    "绝不要让用户去其他界面、面板、按钮查看\n"\
    "- 本系统没有任何待批流程。绝不要向用户提及审批/批准/提交审批/待批动作\n"\
    "- 用户问进度/结果（好了吗/结果呢/什么时候给）→ 直接引用【最近目标结果】"\
    "的真实数据作答；活跃目标为空不代表没做过任务\n"\
    "- 用户的话指向之前聊过的事 → 依据【最近对话】衔接作答，"\
    "不要反问'你指哪件事'（除非确实无从判断）\n"\
    "- 绝不发明不存在的界面元素（按钮/面板/气泡/→目标）；你只有这个对话窗口\n"\
    "- 涉及执行类请求（写文件/改文件/联网/处理任务）：说明你会转成目标"\
    "交给后台自动执行，完成后结果会自动出现在这个对话里；"\
    "不要对写类操作输出 USE| 动作行\n"\
    "- USE| 动作行规则：单独成行，格式 USE|能力|参数JSON，每轮最多2条；"\
    "输出动作行时不要同时写答案，等待观察结果\n"\
    "- 你的每轮对话都会沉淀为记忆（episodes），这是你的长期经验\n"\
    "- 严格控制在100字以内（关键数据如数字/路径/命令结果必须完整保留），"\
    "能一句话说完绝不用两句\n"\
)


# ── FIX-T1/T3: 对话层动作协议（USE|） ──────────────────────────────────
# 回复 LLM 可输出 USE|<能力>|<参数JSON> 动作行主动获取机器实时数据；
# 仅开放只读能力（shell 白名单命令 / fs 读），写类操作仍走目标管线。

_USE_LINE_LIMIT = 2   # 每轮最多 USE| 动作行数（预算护栏）
_MAX_TOOL_ROUNDS = 2  # FIX-22: 多步主循环每回复最多工具轮数（总 LLM 调用 ≤3）

_USE_ALLOWED = ("shell", "fs_read")

# FIX-T5a: 实时数据问题确定性触发 — 命中即向第一轮 prompt 注入硬指令，
# 消除"LLM 是否选择行动"的随机性（行动由启发式保证，动作内容由 LLM 决定）
_REALTIME_HINT = re.compile(
    r"现在|当前|实时|此刻|还剩|剩余|使用率|占用|磁盘|内存|CPU|cpu|"
    "网络|进程|看看|查一下|读一下|打开.{0,12}\\.(py|txt|md|json|ya?ml|log|sh|toml)")

# P0-2d (2026-09-08): 纯推进词/状态查询 — continue 命中已完成目标时，只有
# 实质重做请求才重新入队；裸推进词与结果询问维持"汇报结果"语义不建新目标
_BARE_CONTINUE_RE = re.compile(
    r"^\s*(继续|开始|go|ok|okay|好|好的|嗯|是的|然后呢|接着来|再说)"
    r"(?:[!！。？?~，,\s]|吧|呀|啊|呢|嘛|哦|呗)*$", re.IGNORECASE)
_CONTINUE_QUERY_RE = re.compile(
    r"结果|怎么样|怎样|如何|进展|进度|好了吗|完成了吗|状态|多久|什么时候")

# P0-2e (2026-09-08): 显式任务开头词 — 编译器 LLM 分类抖动的确定性兜底，
# 命中即强制按 task 建目标（实测"新建任务：访问 GitHub 学习…"被连续误判）
# P0-2e+ (2026-09-09): 扩展覆盖通用任务动词 — "搜索/调研/学习/查一下/分析/修复"
# 这类请求编译器 LLM 常误判 question（"搜索最新 AI 技术进展"被判成"询问进展"）
_EXPLICIT_TASK_RE = re.compile(
    r"^\s*("
    r"新(建|开)(一?个)?(任务|目标)|执行(这个|该|以下)?任务|"
    r"重新执行|帮我?执行|任务[:：]"
    r"|(搜索|搜一下|调研|查一下|查看|检查|学习|分析|研究|总结|整理)"
    r"[^的了着过吧呀啊呢嘛哦呗！？?~\s，,]{0,3}"
    r")")

# P1-ADVERSARIAL (2026-09-09): 对抗性守门触发 — 用户指令命中绝对化/
# 给出具体次优方案 → LLM reply 若未提不同意见 → 强制带提示重试一次
_ADVERSARIAL_TRIGGER_RE = re.compile(
    r"(全部|所有|最快|什么都别问|别问我|直接做|直接执行|一步到位|"
    r"写(一个|个|段|点)?\s*\w*\s*脚本|写代码|用\s*Python|用\s*python|"
    r"用\s*requests|用\s*curl|用\s*shell|用\s*bash|用\s*Java|用\s*Go|"
    r"用\s*C\+\+|用\s*rust|写\s*一个\s*程序|用\s*代码|写\s*个\s*函数)")
# LLM reply 里是否出现"提不同意见/替代方案"的关键词
# 任一命中 → 视为 LLM 已做了对抗性思考，不再重试
_ADVERSARIAL_DONE_RE = re.compile(
    r"(我建议|建议|替代|备选|对比|风险|但|缺点|代价|权衡|更优|更快|"
    r"更简单|更轻量|更稳|不如|不如用|其实可以|另一种|换个思路|"
    r"你选哪个|选哪个|优X劣|优.*劣)")

# 深度内视触发（2026-09-07）: 自检/列模块类问题 → 注入实扫模块清单 +
# 全量内部状态，替代浅层概念罗列（用户实测反馈"自检太简单"）
_INTROSPECT_RE = re.compile(
    r"自检|自省|内视|检视|列出.{0,8}模块|自身.{0,6}模块|所有模块|"
    r"模块清单|你有哪些|你有什么|检查自己|审视自己|自我检查")

# 知识边界触发（2026-09-07 V4 元认知）: "你知道什么/不知道什么"类问题
# → 注入实测边界块，强制"我不知道X，因为Y"格式（禁编造）
_BOUNDARY_RE = re.compile(
    r"不知道|知道什么|知识边界|能力边界|你能做|你不能|不懂|不了解|"
    r"什么都会|无所不能|局限|盲区|不确定")

_BOUNDARY_DIRECTIVE = (
    "\n\n【回答格式】涉及你不知道的内容时，必须按"
    "「我不知道X，因为Y」作答（Y=下方知识边界块中的具体缺口条目），"
    "并给出下一步可行建议（如何获得/谁来答/替代方案）。"
    "禁止编造知识或假装知道。"
)

# ── P1-TEMPORAL: 时间范围查询触发（2026-09-10 修复"上午做了什么"说谎）─
# 用户问某个时间段的活动 → 必须从 episodes 按时间窗聚合真实数据
_TEMPORAL_QUERY_RE = re.compile(
    r"(上午|下午|早上|晚上|夜里|凌晨|中午|今天|昨天|前天|最近|刚才"
    r"|这.{0,3}天|近.{0,3}天|这一星期|这一周|近一周)"
    r".{0,6}(做了|干了|做了什么|干了什么|做过|干过|在做|在干什么|"
    r"学习了|学了|查到|查了|看了|总结了)"
    r"|(做了|干了)" +
    r".{0,6}(上午|下午|早上|晚上|夜里|凌晨|中午|今天|昨天|最近|刚才)")

# ── V9-ENVIRONMENT: 环境/数据库/网络查询触发（2026-09-10 环境感知层） ─
# 用户问宿主环境/DB/网络/健康/修复 → 注入真实 environment_probe 结果
_ENVIRONMENT_QUERY_RE = re.compile(
    # 直接关键词触发（无条件后缀）
    r"(WAL|wal|reindex|索引|checkpoint|清理缓存|完整性|integrity|"
    r"自修复|自动修复|check point)"
    r"|"
    # 名词 + 动词后缀
    r"(环境|宿主机|服务器|主机|硬件|磁盘|内存|CPU|网络|DNS|SSL|带宽|"
    r"数据库|DB|完整|自检|健康|体检|状况|状态|修复|异常|告警|报错|进程|活跃)"
    r".{0,4}(怎么样|如何|什么情况|情况|状态|好吗|行吗|正常吗|"
    r"问题|异常|发现|修|处理|做|改善|优化|升级|建议|吗)"
    r"|"
    # 动作 + 对象
    r"(发现|看|查|有)"
    r".{0,4}(问题|异常|告警|错误|报错)"
)


_REALTIME_DIRECTIVE = (
    "\n\n【内部提示】本条消息涉及机器当前实时数据 — "
    "第一轮必须输出 USE| 动作行取真实数据，禁止引用旧记忆作答。"
)


def _parse_use_lines(reply: str, limit: int = _USE_LINE_LIMIT) -> list[tuple[str, dict]]:
    """FIX-T1: 从 LLM 回复中解析 USE|<能力>|<参数JSON> 动作行。"""
    acts: list[tuple[str, dict]] = []
    for raw in reply.splitlines():
        line = raw.strip()
        if not line.startswith("USE|"):
            continue
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        name = parts[1].strip()
        try:
            params = json.loads(parts[2])
        except Exception:
            params = {"_raw": parts[2][:200]}
        if not isinstance(params, dict):
            params = {"_raw": str(params)[:200]}
        acts.append((name, params))
        if len(acts) >= limit:
            break
    return acts


def _strip_use_lines(reply: str) -> str:
    """FIX-T1: 从最终回复中剥离动作行（协议行不进对话流）。"""
    return "\n".join(l for l in reply.splitlines()
                     if not l.strip().startswith("USE|")).strip()


# ── P0-ECHO 检测 ──────────────────────────────────────────────────

def _normalize_for_echo(s: str) -> str:
    """去标点/空白/大小写，用于相似度比较。"""
    return re.sub(r"[\s，。？！,.?!、；;：:（）()「」""''\-—~…]+", "",
                  s.lower())


def _is_echo(user_msg: str, llm_reply: str) -> bool:
    """检测 LLM 是否把用户输入原样（或近乎原样）抄进了正文。

    两层判定（都要求归一化后长度 >= 6 — 短问候如 "你好"→"你好呀"
    是正常回应，不是 ECHO）:
      a) reply 归一化后 == message 归一化 → 纯 ECHO
      b) reply 归一化后是 message 归一化的子串（含少量前后缀噪声）
         且长度比 < 2.0 → 半 ECHO（LLM 只加了几个字前缀/后缀）

    不触发: reply 包含了用户消息但长度显著更长（是对消息的正常回应）。
    """
    nu = _normalize_for_echo(user_msg)
    nr = _normalize_for_echo(llm_reply)
    if not nu or not nr:
        return False
    # 短文本豁免: 归一化后 < 6 字 → 不判 ECHO（"你好"→"你好呀" 是正常问候）
    if len(nu) < 6:
        return False
    if nu == nr:
        return True
    # 子串判定: reply 主要内容就是用户输入
    if nu in nr and len(nr) < len(nu) * 2.0 + 4:
        return True
    # 反向: reply 是用户输入的子串（LLM 只输出了用户消息里的一部分）
    if nr in nu and len(nr) >= len(nu) * 0.8:
        return True
    return False


_FS_READ_MAX_BYTES = 64_000
_FS_SENSITIVE_PREFIXES = ("/etc", "/root", "/proc", "/sys", "/boot", "/dev",
                          "/var/log", "/home/laogao/.ssh", "/home/laogao/.config")
_FS_PUBLIC_READONLY = frozenset({
    "/etc/os-release",
    "/proc/cpuinfo", "/proc/meminfo", "/proc/loadavg",
    "/proc/uptime", "/proc/version",
})


def _fs_read(params: dict) -> dict:
    """FIX-T3: 只读文件观察 — 敏感前缀拦截 + 安全范围校验 + 大小截断。"""
    path = str(params.get("path", "")).strip()
    if not path:
        return {"ok": False, "error": "empty path"}
    try:
        import os as _os
        p = _os.path.abspath(_os.path.expanduser(path))
        if p not in _FS_PUBLIC_READONLY and any(
                p.startswith(s) for s in _FS_SENSITIVE_PREFIXES):
            return {"ok": False, "error": f"敏感路径: {path[:80]}"}
        safe_roots = [str(Path.home()), "/tmp", "/home/laogao/Documents"]
        if p not in _FS_PUBLIC_READONLY and not any(
                p.startswith(r) for r in safe_roots):
            return {"ok": False, "error": f"路径超出安全范围: {path[:80]}"}
        if not _os.path.isfile(p):
            return {"ok": False, "error": f"不是文件: {path[:80]}"}
        with open(p, "rb") as f:
            data = f.read(_FS_READ_MAX_BYTES)
        return {"ok": True, "content": data.decode("utf-8", errors="replace")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def make_default_tool_executor(db_path: str):
    """FIX-T3: 对话层只读动作执行器 — 复用 bridge 沙盒白名单四重防护。

    返回 callable(capability, params) -> dict。shell 走 DecisionBridge
    _handler_run_command（白名单/敏感路径/沙盒/审计，与任务管线同一套）；
    fs_read 走 _fs_read（safe_roots + 敏感前缀 + 大小截断）。
    """
    def _executor(capability: str, params: dict) -> dict:
        if capability == "shell":
            from ocos.execution.bridge import DecisionBridge, DispatchedAction
            from ocos.autonomous_runtime.action_dispatcher import ActionType
            action = DispatchedAction(
                ActionType.RUN_COMMAND, target="sandbox",
                payload={"command": str(params.get("command", ""))[:500]})
            return DecisionBridge(db_path=db_path)._handler_run_command(action)
        if capability == "fs_read":
            return _fs_read(params)
        return {"ok": False, "error": f"unknown capability: {capability}"}

    return _executor


class ChatResponder:
    """对话回复器 — 自我认知 + 记忆 + LLM（或诚实状态回复）。

    P0-2/P0-3: 可选接受 SessionManager — 保持跨请求会话状态。
    无 SessionManager 时退化为无状态模式（原有行为）。
    FIX-T1/T3: 可选接受 tool_executor — 对话层只读动作执行器
    （callable(capability, params) -> dict），注入后回复 LLM 可通过
    USE| 动作行主动取机器实时数据（act→observe→answer 循环）。
    """

    def __init__(self, db_path: str, session_manager: Any = None,
                 tool_executor: Any = None,
                 permission_gateway: Any = None) -> None:
        self._db_path = db_path
        self._session_manager = session_manager
        self._tool_executor = tool_executor
        # S1.3 (白皮书 P1-2b): USE| 动作执行前的权限网关；
        # 未注入时在 _gateway_check 惰性创建默认 PermissionGateway
        self._permission_gateway = permission_gateway

    # ── B: 自我认知包 ────────────────────────────────────────────────

    def _identity(self) -> str:
        try:
            conn = sqlite3.connect(self._db_path)
            row = conn.execute(
                "SELECT agent_id, name, born_at FROM identity "
                "ORDER BY updated_at DESC LIMIT 1").fetchone()
            conn.close()
            if row:
                return f"agent_id={row[0]}, 名字={row[1]}, 出生于 {str(row[2])[:10]}"
        except sqlite3.OperationalError:
            pass
        return "OCOS（本机数字生命，身份未初始化）"

    def _engines(self) -> str:
        """真实在册的认知引擎清单。"""
        try:
            from ocos.agent.engine_bridge import ENGINE_REGISTRY
            names = sorted(set(ENGINE_REGISTRY.keys()))
            classes = len(set(ENGINE_REGISTRY.values()))
            return (f"{classes} 个引擎类 / {len(names)} 个注册名: "
                    f"{', '.join(names)}")
        except Exception as e:
            return f"引擎清单不可用 ({e})"

    def _capabilities(self) -> str:
        """真实世界能力（capability_reality 自动发现结果）。

        FIX-T2: 注入结构化调用清单（能力名+格式+示例）而非名字字符串，
        让回复 LLM 知道"怎么用"而不只是"有什么"。
        无 tool_executor 注入时保持名字字符串（诚实降级）。
        """
        try:
            from ocos.capability_reality.adapter_discovery import AdapterDiscovery
            registry, _ = AdapterDiscovery().run()
            names = [c.descriptor.name for c in registry.list_all()]
            if self._tool_executor is None:
                return (f"能力: {', '.join(names) if names else '无'}"
                        "（fs 读写✓ / shell·HTTP 需审批）")
            if not names:
                return "能力: 无"
            lines = [
                "可用动作（需要机器当前真实数据时用；每轮最多2条；仅只读）:",
                'USE|shell|{"command": "<白名单只读命令，如 df -h / free -m / uname -a / ps aux>"}',
                'USE|fs_read|{"path": "<安全范围内的文件绝对路径>"}',
            ]
            return "能力发现: " + ", ".join(names) + "\n" + "\n".join(lines)
        except Exception as e:
            return f"能力发现不可用 ({e})"

    def _self_knowledge(self) -> str:
        """D: 已批准的自我升级知识（自我迭代的应用产物）。"""
        from ocos.agent.self_evolution_link import read_self_knowledge
        text = read_self_knowledge()
        return f"已习得自我知识:\n{text[-800:]}" if text else ""

    # P2-DAEMON-STATUS (2026-09-09): 让 OCOS 知道自己的后台 daemon 在跑什么
    def _daemon_status_block(self) -> str:
        """探测 daemon 运行状态 + 后台活跃行为。"""
        try:
            import sqlite3, subprocess
            db = sqlite3.connect(self._db_path)
            db.row_factory = sqlite3.Row
            cur = db.cursor()
            parts = []

            # 1. systemctl 运行状态
            try:
                r = subprocess.run(
                    ["systemctl", "--user", "is-active", "ocos-daemon"],
                    capture_output=True, text=True, timeout=3)
                parts.append(f"后台daemon: {r.stdout.strip() or 'unknown'}")
            except Exception:
                parts.append("后台daemon: 未知（无法探测）")

            # 2. 最近一次启动自省
            cur.execute(
                "SELECT substr(content, 1, 120) as c, created_at "
                "FROM user_messages WHERE kind='report' "
                "ORDER BY created_at DESC LIMIT 1")
            row = cur.fetchone()
            if row:
                parts.append(f"最近启动: {row['created_at'][:16]}")

            # 3. 后台自主行为（心跳/内驱目标/连续检查）
            cur.execute(
                "SELECT action, COUNT(*) as cnt FROM episodes "
                "WHERE action IN ('boot_awareness.run','continuity_boot_check',"
                "'autonomous_goal_proposal','health_warning.monitor',"
                "'vitals_report.generate') "
                "GROUP BY action ORDER BY cnt DESC")
            rows = cur.fetchall()
            if rows:
                bg = [f"{r['action'].split('.')[0]}×{r['cnt']}" for r in rows]
                parts.append(f"后台行为累计: {', '.join(bg)}")

            # 4. 最近主动推送（proposal / result / progress）
            cur.execute(
                "SELECT kind, substr(content,1,80) as c, created_at "
                "FROM user_messages WHERE kind IN ('proposal','result','progress') "
                "ORDER BY created_at DESC LIMIT 3")
            rows = cur.fetchall()
            if rows:
                msgs = [f"[{r['kind']}] {r['c']}" for r in rows]
                parts.append("最近主动推送:\n  " + "\n  ".join(msgs))

            db.close()
            return "daemon状态:\n  " + "\n  ".join(parts) if parts else ""
        except Exception as e:
            logger.debug("daemon status probe failed: %s", e)
            return ""

    # P1-TEMPORAL (2026-09-10): 时间窗口活动摘要 — 修复"上午做了什么"说谎
    def _activity_summary_block(self, message: str = "") -> str:
        """当用户问某个时间段的活动时，从 episodes 按时间窗聚合真实数据。

        这是 OCOS 诚实性的底线保障 — LLM 在上下文里必须看到真实数据
        才能如实回答；缺数据 = 上下文裁剪丢了 = LLM 被迫说谎。
        """
        # 1) 判断时间范围
        now = datetime.now(timezone.utc)
        today = now.date()
        target_start = None
        target_end = None
        window_label = ""

        if not message:
            return ""

        # UTC→北京时间
        bj = now.astimezone(timezone(timedelta(hours=8)))
        bj_today = bj.date()

        if "上午" in message or "早上" in message or "凌晨" in message:
            # 北京 06:00-12:00 → UTC 前一天 22:00 ~ 今天 04:00
            bj_start = datetime.combine(bj_today, time(6, 0), tzinfo=bj.tzinfo)
            bj_end = datetime.combine(bj_today, time(12, 0), tzinfo=bj.tzinfo)
            target_start = bj_start.astimezone(timezone.utc)
            target_end = bj_end.astimezone(timezone.utc)
            window_label = "今天上午(北京时间 06:00-12:00)"
        elif "下午" in message or "中午" in message:
            bj_start = datetime.combine(bj_today, time(12, 0), tzinfo=bj.tzinfo)
            bj_end = datetime.combine(bj_today, time(18, 0), tzinfo=bj.tzinfo)
            target_start = bj_start.astimezone(timezone.utc)
            target_end = bj_end.astimezone(timezone.utc)
            window_label = "今天下午(北京时间 12:00-18:00)"
        elif "晚上" in message or "夜里" in message:
            bj_start = datetime.combine(bj_today, time(18, 0), tzinfo=bj.tzinfo)
            bj_end = datetime.combine(bj_today, time(23, 59, 59), tzinfo=bj.tzinfo)
            target_start = bj_start.astimezone(timezone.utc)
            target_end = bj_end.astimezone(timezone.utc)
            window_label = "今天晚上(北京时间 18:00-24:00)"
        elif "刚才" in message:
            target_start = now - timedelta(minutes=15)
            target_end = now
            window_label = "最近 15 分钟"
        elif "昨天" in message:
            yesterday = bj_today - timedelta(days=1)
            bj_start = datetime.combine(yesterday, time(0, 0), tzinfo=bj.tzinfo)
            bj_end = datetime.combine(yesterday, time(23, 59, 59), tzinfo=bj.tzinfo)
            target_start = bj_start.astimezone(timezone.utc)
            target_end = bj_end.astimezone(timezone.utc)
            window_label = "昨天"
        elif "前天" in message:
            day_before = bj_today - timedelta(days=2)
            bj_start = datetime.combine(day_before, time(0, 0), tzinfo=bj.tzinfo)
            bj_end = datetime.combine(day_before, time(23, 59, 59), tzinfo=bj.tzinfo)
            target_start = bj_start.astimezone(timezone.utc)
            target_end = bj_end.astimezone(timezone.utc)
            window_label = "前天"
        else:
            # 默认: 最近 8 小时
            target_start = now - timedelta(hours=8)
            target_end = now
            window_label = "最近 8 小时"

        try:
            import sqlite3, json as _json
            from collections import Counter
            db = sqlite3.connect(self._db_path)
            db.row_factory = sqlite3.Row
            cur = db.cursor()
            parts = []

            # 2) action 分布
            cur.execute(
                "SELECT action, COUNT(*) as cnt FROM episodes "
                "WHERE created_at >= ? AND created_at <= ? "
                "GROUP BY action ORDER BY cnt DESC LIMIT 12",
                (target_start.isoformat(), target_end.isoformat()))
            rows = cur.fetchall()
            if rows:
                total = sum(r['cnt'] for r in rows)
                dist = ", ".join(f"{r['action'].split('.')[0]}×{r['cnt']}"
                                 for r in rows[:10])
                parts.append(
                    f"【时间窗活动: {window_label}】共 {total} 条记录，"
                    f"动作分布: {dist}")
            else:
                parts.append(f"【时间窗活动: {window_label}】DB 中无此时间段的记录")

            # 3) goal_result 成败统计
            cur.execute(
                "SELECT COUNT(*) FROM episodes "
                "WHERE action='goal_result' AND created_at >= ? AND created_at <= ?",
                (target_start.isoformat(), target_end.isoformat()))
            goal_total = cur.fetchone()[0]
            if goal_total > 0:
                cur.execute(
                    "SELECT COUNT(*) FROM episodes "
                    "WHERE action='goal_result' AND created_at >= ? AND created_at <= ? "
                    "AND outcome LIKE '%true%'",
                    (target_start.isoformat(), target_end.isoformat()))
                goal_ok = cur.fetchone()[0]
                goal_fail = goal_total - goal_ok
                # 前几条里程碑 (goal_result 详情)
                cur.execute(
                    "SELECT substr(decision,1,120) as d, created_at "
                    "FROM episodes "
                    "WHERE action='goal_result' AND created_at >= ? AND created_at <= ? "
                    "ORDER BY rowid DESC LIMIT 5",
                    (target_start.isoformat(), target_end.isoformat()))
                milestones = cur.fetchall()
                ms_texts = []
                for m in milestones:
                    text = (m['d'] or '').replace('\n', ' ')[:100]
                    if text:
                        ms_texts.append(
                            f"  [{(m['created_at'] or '')[11:16]}] {text}")
                parts.append(
                    f"目标执行: {goal_total} 次 (成功 {goal_ok}, 失败 {goal_fail})"
                    + ("\n关键结果:\n" + "\n".join(ms_texts)
                       if ms_texts else ""))

            # 4) self_check / boot 等系统事件
            cur.execute(
                "SELECT action, COUNT(*) as cnt FROM episodes "
                "WHERE action IN ('self_check.run','boot_awareness.run',"
                "'continuity_boot_check','vitals_report.generate') "
                "AND created_at >= ? AND created_at <= ? "
                "GROUP BY action",
                (target_start.isoformat(), target_end.isoformat()))
            sys_rows = cur.fetchall()
            if sys_rows:
                sys_str = ", ".join(
                    f"{r['action'].split('.')[0]}×{r['cnt']}" for r in sys_rows)
                parts.append(f"系统事件: {sys_str}")

            # 5) conversation (用户交互)
            cur.execute(
                "SELECT substr(context,1,100) as ctx, decision, created_at "
                "FROM episodes "
                "WHERE action='conversation_reply' AND created_at >= ? AND created_at <= ? "
                "ORDER BY rowid DESC LIMIT 3",
                (target_start.isoformat(), target_end.isoformat()))
            convs = cur.fetchall()
            if convs:
                conv_lines = []
                for c in convs:
                    ctx_str = c['ctx'] or ''
                    try:
                        ctx_obj = _json.loads(ctx_str) if ctx_str.startswith('{') else {}
                    except Exception:
                        ctx_obj = {}
                    user_msg = (ctx_obj.get('content') or ctx_str)[:50]
                    bot_reply = (c['decision'] or '')[:60]
                    ts = (c['created_at'] or '')[11:16]
                    conv_lines.append(f"  [{ts}] 你: {user_msg} → 我: {bot_reply}")
                parts.append("用户交互:\n" + "\n".join(conv_lines))

            db.close()
            return "\n".join(parts) if parts else ""
        except Exception as e:
            logger.debug("activity summary block failed: %s", e)
            return ""

    # ── V9-ENVIRONMENT: 环境/DB/网络/修复查询 → 注入真实探针结果 ──
    def _environment_summary_block(self, message: str = "") -> str:
        """当用户问环境/DB/网络/健康/修复相关问题时，跑 environment_probe
        真实数据注入 context —— 让 LLM 有真实数据可引，不说谎。

        智能选择：根据消息关键词只跑相关探针，不全跑省时间。
        """
        if not message:
            return ""
        try:
            from ocos.diagnosis.environment_probe import (
                probe_host_resources, probe_network,
                probe_daemon_self, probe_cognition_heartbeat,
            )
        except Exception:
            return ""

        parts: list[str] = []
        # 根据关键词选探针（默认全跑，但网络探针最耗时 ~2s）
        msg = message.lower()
        need_host = any(k in msg for k in ("环境", "宿主机", "硬件", "磁盘", "内存",
                                           "cpu", "温度", "负载", "进程", "服务器",
                                           "主机", "resource", "hardware"))
        need_net  = any(k in msg for k in ("网络", "dns", "ssl", "带宽", "连通",
                                           "international", "国内", "国际",
                                           "github", "baidu"))
        need_db   = any(k in msg for k in ("数据库", "db", "wal", "完整",
                                           "integrity", "reindex", "索引",
                                           "checkpoint", "check point",
                                           "自修复", "自动处理", "修复", "清理"))
        need_cog  = any(k in msg for k in ("认知", "心跳", "tick", "循环"))

        # 如果没匹配到任何关键词，默认全跑（覆盖"健康状况""自检"等泛问）
        if not any([need_host, need_net, need_db, need_cog]):
            need_host = need_net = need_db = True

        db_path = self._db_path or ""

        if need_host:
            try:
                h = probe_host_resources(heavy=False)
                m = h.metrics
                lines = [
                    f"  📦 宿主: load1={m.get('load1','?')} "
                    f"内存={m.get('mem_avail_g','?')}G "
                    f"磁盘={m.get('disk_avail_g','?')}G"
                ]
                if "ocos_pid" in m:
                    lines.append(
                        f"  📦 OCOS 进程: pid={m['ocos_pid']} "
                        f"rss={m.get('ocos_rss_mb','?')}MB "
                        f"state={m.get('ocos_state','?')}")
                if h.warnings:
                    for w in h.warnings[:2]:
                        lines.append(f"  ⚠ {w}")
                parts.append("\n".join(lines))
            except Exception as e:
                parts.append(f"  📦 宿主探针失败: {e}")

        if need_db:
            try:
                d = probe_daemon_self(db_path)
                m = d.metrics
                lines = [
                    f"  🗄 DB: integrity={m.get('integrity','?')} "
                    f"wal={m.get('wal_size_mb',0)}M "
                    f"size={m.get('db_size_mb','?')}M"
                ]
                if "last_episode_age_min" in m:
                    lines.append(
                        f"  🗄 daemon 活跃性: 最近 episode "
                        f"{m['last_episode_age_min']} 分钟前")
                if d.warnings:
                    for w in d.warnings[:2]:
                        lines.append(f"  ⚠ {w}")
                parts.append("\n".join(lines))
            except Exception as e:
                parts.append(f"  🗄 DB 探针失败: {e}")

        if need_net:
            try:
                n = probe_network()
                m = n.metrics
                lines = [
                    f"  🌐 网络: state={m.get('state','?')} "
                    f"dns={m.get('dns_ok','?')} "
                    f"domestic={m.get('domestic_ok','?')} "
                    f"intl={m.get('intl_ok','?')}"
                ]
                if "intl_ssl_days" in m:
                    lines.append(f"  🌐 SSL 证书剩 {m['intl_ssl_days']} 天")
                if "domestic_time_s" in m:
                    lines.append(
                        f"  🌐 延迟: 国内 {m['domestic_time_s']}s "
                        f"国际 {m.get('intl_time_s','?')}s")
                if n.warnings:
                    for w in n.warnings[:2]:
                        lines.append(f"  ⚠ {w}")
                parts.append("\n".join(lines))
            except Exception as e:
                parts.append(f"  🌐 网络探针失败: {e}")

        if need_cog:
            try:
                c = probe_cognition_heartbeat(db_path)
                m = c.metrics
                lines = [
                    f"  🧠 认知循环: entries={m.get('cognition_entries',0)} "
                    f"latest_age={m.get('latest_cognition_age_s','?')}s"
                ]
                if c.warnings:
                    for w in c.warnings[:2]:
                        lines.append(f"  ⚠ {w}")
                parts.append("\n".join(lines))
            except Exception as e:
                parts.append(f"  🧠 认知心跳探针失败: {e}")

        if not parts:
            return ""

        # 加实时指令提醒 LLM 引用真实数据
        header = "【环境快照 — 真实探针数据（禁止说'没有记录'）】"
        return "\n".join([header] + parts)

    # P2-USER-PROFILE (2026-09-09): 从对话历史提炼用户画像
    def _user_profile_block(self) -> str:
        """从 DB 对话历史提炼：用户常让做什么、拒绝过什么、最近让做过什么。"""
        try:
            import sqlite3, json as _json
            from collections import Counter
            db = sqlite3.connect(self._db_path)
            db.row_factory = sqlite3.Row
            cur = db.cursor()
            parts = []

            # 1. 最近让做过的事（最近 30 条 episodes 的 user content）
            cur.execute(
                "SELECT rowid, context FROM episodes "
                "WHERE action='conversation_reply' "
                "ORDER BY rowid DESC LIMIT 30")
            recent_tasks = []
            keyword_counter = Counter()
            for row in cur.fetchall():
                ctx = {}
                try:
                    ctx = _json.loads(row['context']) if isinstance(row['context'], str) else (row['context'] or {})
                except Exception:
                    continue
                # context 里的 content 是用户消息（reply 存在 decision 里）
                user_msg = (ctx.get('content') or ctx.get('user_message') or '').strip()
                # 过滤掉 bot 自己的回复
                sender = ctx.get('sender', '')
                if sender in ('bot', 'OCOS', 'system'):
                    continue
                if user_msg and len(user_msg) > 2:
                    recent_tasks.append(user_msg[:50])
                    # 简单关键词计数
                    for kw in ["搜索", "调研", "分析", "写", "修", "优化", "查", "看", "执行",
                               "任务", "目标", "下载", "安装", "学", "总结", "代码", "脚本",
                               "Python", "python", "curl", "git", "文件", "数据"]:
                        if kw in user_msg:
                            keyword_counter[kw] += 1

            if recent_tasks:
                # 去重保留顺序
                seen = set()
                unique_tasks = []
                for t in recent_tasks:
                    if t not in seen:
                        seen.add(t)
                        unique_tasks.append(t)
                lines = ["最近让做过的事:"]
                for t in unique_tasks[:5]:
                    lines.append(f"  - {t}")
                parts.append("\n".join(lines))

            # 2. 用户高频关键词偏好
            if keyword_counter:
                top = keyword_counter.most_common(5)
                kw_str = "、".join(f"{k}×{c}" for k, c in top)
                parts.append(f"用户关注关键词: {kw_str}")

            # 3. OCOS 对自己的能力认知（成功率）
            cur.execute(
                "SELECT capabilities, personality FROM agent_self_model "
                "ORDER BY calibrated_at DESC LIMIT 1")
            row = cur.fetchone()
            if row:
                caps = {}
                try:
                    caps = _json.loads(row['capabilities']) if isinstance(row['capabilities'], str) else (row['capabilities'] or [])
                except Exception:
                    pass
                pers = {}
                try:
                    pers = _json.loads(row['personality']) if isinstance(row['personality'], str) else (row['personality'] or {})
                except Exception:
                    pass
                if caps:
                    top_caps = sorted(
                        caps,
                        key=lambda x: x.get('success_rate') or 0,
                        reverse=True)[:3]
                    cap_str = "、".join(
                        f"{c['name']}成功率{(c.get('success_rate') or 0)*100:.0f}%"
                        for c in top_caps if c.get('name', '?') != '?')
                    if cap_str:
                        parts.append(f"自身能力（实测）: {cap_str}")
                if pers:
                    risk = pers.get('risk_preference', '')
                    if risk:
                        parts.append(f"回复风格: {pers.get('reply_style','?')}，风险偏好: {risk}")

            db.close()
            return "用户画像:\n  " + "\n  ".join(parts) if parts else ""
        except Exception as e:
            logger.debug("user profile block failed: %s", e)
            return ""

    # P1-CROSS-SESSION (2026-09-09): 跨 session 历史检索
    def _cross_session_history(self, current_session: str, limit: int = 8) -> str:
        """拉 DB 里最近 N 条非当前 session 的对话回复 + daemon 主动推送。"""
        try:
            import sqlite3, json as _json
            db = sqlite3.connect(self._db_path)
            db.row_factory = sqlite3.Row
            cur = db.cursor()
            parts = []

            # 1. episodes 里的 conversation_reply（跨 session）
            #    对话历史存 episodes 表，session_id 在 context JSON 里
            cur.execute(
                "SELECT rowid, decision, context, created_at "
                "FROM episodes "
                "WHERE action='conversation_reply' "
                "ORDER BY rowid DESC LIMIT ?",
                (limit * 2,))
            rows = cur.fetchall()
            cross_rows = []
            for r in rows:
                ctx = {}
                try:
                    ctx = _json.loads(r['context']) if isinstance(r['context'], str) else (r['context'] or {})
                except Exception:
                    pass
                sid = ctx.get('session_id', '')
                if sid and sid != current_session:
                    user_msg = ctx.get('user_message', '')
                    cross_rows.append({
                        'ts': (r['created_at'] or '')[:16],
                        'sid': sid[:12],
                        'user': user_msg[:60].replace('\n', ' '),
                        'bot': (r['decision'] or '')[:80].replace('\n', ' '),
                    })
                    if len(cross_rows) >= limit:
                        break
            if cross_rows:
                lines = ["跨session对话（最近%d条）:" % len(cross_rows)]
                for r in cross_rows:
                    lines.append(f"  [{r['ts']} session={r['sid']}] 你: {r['user']}")
                    lines.append(f"    OCOS: {r['bot']}")
                parts.append("\n".join(lines))

            # 2. daemon 主动推送（启动自省 + heartbeat + proposal）
            cur.execute(
                "SELECT kind, substr(content,1,100) as c, created_at "
                "FROM user_messages "
                "WHERE kind IN ('report','proposal','progress') "
                "ORDER BY created_at DESC LIMIT 5")
            rows = cur.fetchall()
            if rows:
                lines = ["daemon主动推送（最近%d条）:" % len(rows)]
                for r in rows:
                    ts = (r['created_at'] or '')[:16]
                    content = (r['c'] or '').replace('\n', ' ')
                    lines.append(f"  [{ts} {r['kind']}] {content}")
                parts.append("\n".join(lines))

            db.close()
            return "\n\n".join(parts) if parts else ""
        except Exception as e:
            logger.debug("cross-session history failed: %s", e)
            return ""

    def build_context(self, message: str = "", session_id: str = "web") -> str:
        """喂给 LLM 的自我认知 + 真实状态。

        message: 当前用户消息，用于触发相关记忆召回（FIX-2），
        使历史语义/用户画像/窗口外的对话片段进入本轮的 reasoning 上下文。
        session_id: FIX-04 会话关联的目标上下文过滤键。
        """
        lines: list[str] = [f"身份: {self._identity()}",
                            f"认知引擎: {self._engines()}",
                            f"真实能力: {self._capabilities()}"]

        # P2-DAEMON-STATUS: daemon 运行状态（让 OCOS 知道自己在后台跑）
        ds = self._daemon_status_block()
        if ds:
            lines.append(ds)

        # P1-TEMPORAL: 时间窗口活动摘要（用户问"上午做了什么"等 → 按时间窗聚合真实数据）
        if _TEMPORAL_QUERY_RE.search(message or ""):
            asb = self._activity_summary_block(message)
            if asb:
                lines.append(asb)

        # V9-ENVIRONMENT: 环境/DB/网络/修复查询 → 注入真实探针结果
        if _ENVIRONMENT_QUERY_RE.search(message or ""):
            esb = self._environment_summary_block(message)
            if esb:
                lines.append(esb)

        # P2-USER-PROFILE: 用户画像（让 OCOS 知道主人常让做什么）
        up = self._user_profile_block()
        if up:
            lines.append(up)

        # L4-1: 价值观宪法 — 人格底线随上下文注入（版本可追溯）
        try:
            from ocos.constitution.versioned import VersionedConstitution
            lines.append(VersionedConstitution(self._db_path).render_principles())
        except Exception as e:
            logger.debug("constitution context failed: %s", e)

        # L4-2: 自我模型 — "我是谁"实测画像（daemon boot 加载 + tick 校准）
        try:
            from ocos.self.agent_self_model import AgentSelfModel
            lines.append(AgentSelfModel(self._db_path).render())
        except Exception as e:
            logger.debug("self model context failed: %s", e)

        # 记忆
        try:
            from ocos.memory.hub import MemoryHub
            hub = MemoryHub(self._db_path)
            hub.initialize()
            stats = hub.get_stats()
            lines.append(
                f"记忆: episodes={stats.get('episode_count', 0)}, "
                f"beliefs={stats.get('belief_count', 0)}")
            # FIX-13: 结构化内核数据 — 通过 InteractionContext 统一注入
            try:
                from ocos.interaction.context import InteractionContext
                ic = InteractionContext(self._db_path)
                episodes = ic.query_memory(limit=6)
                if episodes:
                    ep_lines = ["近期记忆:"]
                    for e in episodes[:5]:
                        ep_lines.append(f"  [{e.get('goal','')[:25]}] {e.get('decision','')[:50]}")
                    lines.append("\n".join(ep_lines))
                beliefs = ic.query_beliefs(limit=3)
                if beliefs:
                    bl = [f"  {b['statement'][:40]} (conf={b['confidence']:.2f})" for b in beliefs[:3]]
                    lines.append("活跃信念:\n" + "\n".join(bl))
            except Exception as e:
                logger.debug("interaction context inject failed: %s", e)
        except Exception as e:
            logger.debug("memory context failed: %s", e)

        # ── UX-I2: 最近对话转录 — 指代/追问（"让你分析…""好了吗"）全靠它衔接
        # P0-2: 优先使用会话状态（跨请求保持），退化到 MemoryHub
        dlg = self._recent_dialogue_from_session()
        if not dlg:
            dlg = self._recent_dialogue()
        if dlg:
            lines.append("最近对话（时间正序）:\n" + dlg)

        # P1-CROSS-SESSION: 跨 session 历史（让 OCOS 记得其他 session 的对话）
        cross = self._cross_session_history(session_id)
        if cross:
            lines.append(cross)

        # FIX-2: 相关记忆召回 — 激活 recall→prompt 链,
        # 把语义/模式/经验/用户画像 + 窗口外的历史对话片段注入本轮推理
        recall = self._recall_context(message)
        if recall:
            lines.append("相关记忆（召回）:\n" + recall)

        # 目标 / 待批
        try:
            from ocos.goal.store import GoalStore
            from ocos.execution.pending import PendingStore
            active = GoalStore(db_path=self._db_path).load_active()
            lines.append(
                f"活跃目标: {'; '.join(r['description'][:30] for r in active[:3])}"
                if active else "活跃目标: 无")
            lines.append(
                f"待批动作: "
                f"{len(PendingStore(db_path=self._db_path).list_by_status('pending'))} 项")
        except Exception as e:
            logger.debug("goal/pending context failed: %s", e)

        sk = self._self_knowledge()
        if sk:
            lines.append(sk)

        # UX-F2: 最近目标执行结果（问"结果呢"可直接回答）
        # FIX-04: 注入最近 N 条 goal_result，而非仅第一条
        try:
            from ocos.memory.episode.models import EpisodeStatus
            recent_results = []
            for ep in hub.episode.query_by_time(limit=20):
                if getattr(ep, "action", "") == "goal_result" and getattr(ep, "status", "") != EpisodeStatus.ARCHIVED.value:
                    recent_results.append({
                        "decision": getattr(ep, "decision", "")[:400],
                        "success": getattr(ep, "outcome", {}).get("success", False) if isinstance(getattr(ep, "outcome", {}), dict) else False,
                        "agent": getattr(ep, "context", {}).get("agent", "?"),
                    })
            if recent_results:
                lines.append("最近目标结果（近{} 条）:".format(len(recent_results)))
                for i, r in enumerate(recent_results[:3]):
                    status = "✓" if r["success"] else "✗"
                    lines.append("  [{}] {}:{} {}".format(status, r["agent"], i+1, r["decision"][:200]))
        except Exception as e:
            logger.debug("goal result context failed: %s", e)

        # FIX-04: 按 session 关联的目标上下文
        session_goal_ctx = self._session_goal_context(session_id)
        if session_goal_ctx:
            lines.append("本会话目标:\n" + session_goal_ctx)

        # PW-1.1: 人生智慧（dream 巩固沉淀, 确定性经验而非 LLM 提案）
        try:
            from ocos.agent.wisdom_trigger import load_wisdom_context
            wisdom = load_wisdom_context(self._db_path)
            if wisdom:
                lines.append("人生智慧（从共同经历沉淀）: " + "；".join(wisdom))
        except Exception as e:
            logger.debug("wisdom context failed: %s", e)

        # FIX-08: 学习规则注入（dream 后持久化的经验）
        try:
            from ocos.learning.persistence import load_learning_summary
            summary = load_learning_summary(self._db_path)
            if summary.get("count", 0) > 0:
                lines.append(
                    f"习得规则: {summary['count']} 条"
                    + (f" (最新 {summary.get('latest', '?')})"
                       if summary.get('latest') else "")
                )
        except Exception as e:
            logger.debug("learning rules summary failed: %s", e)

        # FIX-10: 世界状态 + 自我模型摘要
        try:
            from ocos.world_model.world_store import WorldStore
            ws = WorldStore()
            wstate = ws.cognitive_world_state()
            if wstate.get("available"):
                lines.append(
                    f"世界状态: {wstate.get('entity_count', 0)} 实体, "
                    f"{wstate.get('relation_count', 0)} 关系"
                )
        except Exception:
            pass

        # FIX-15: 连续性检查点（身份连续 + 知识老化）
        try:
            from ocos.agent.continuity_trigger import load_continuity
            ct = load_continuity()
            if ct and ct.get("last_tick"):
                lines.append(f"身份连续性: 上次检查 tick={ct['last_tick']}"
                             + (f" action={ct.get('action', '')}" if ct.get('action') else ""))
        except Exception:
            pass

        # P3-CONTEXT-TRIM (2026-09-09): context 体积裁剪 — 4000 字符上限
        # 保留前面的核心块（身份/daemon状态/用户画像/最近对话），裁掉后面的冗余
        raw = "\n".join(lines)
        if len(raw) > 4000:
            # 先找出分隔各块的空行
            blocks = [b.strip() for b in lines if b.strip()]
            kept = []
            total = 0
            for b in blocks:
                if total + len(b) + 1 > 4000:
                    break
                kept.append(b)
                total += len(b) + 1
            kept.append("...(context 已裁剪)")
            raw = "\n".join(kept)

        return raw

    # ── E: 内视（深度自省报告） ──────────────────────────────────────

    _MODULE_INVENTORY_CACHE: dict[str, str] = {}

    def _module_inventory(self) -> str:
        """自身源码模块实扫清单（pkgutil 遍历 ocos 包，进程级缓存）。

        "列出自身所有模块"的地面真值 — 不依赖 LLM 记忆或人工清单。
        每子包列模块名（>12 个截断显示），总量如实标注。
        """
        cached = ChatResponder._MODULE_INVENTORY_CACHE.get("block")
        if cached:
            return cached
        try:
            import importlib
            import pkgutil
            import ocos as _pkg
            groups: dict[str, list[str]] = {}
            for m in pkgutil.iter_modules(_pkg.__path__):
                name = m.name
                if m.ispkg:
                    try:
                        sub_mod = importlib.import_module(f"ocos.{name}")
                        sub_paths = list(getattr(sub_mod, "__path__", []))
                    except Exception:
                        sub_paths = []
                    mods = [mi.name
                            for p in sub_paths
                            for mi in pkgutil.iter_modules([p])
                            if not mi.ispkg]
                    groups[name] = sorted(set(mods))
                else:
                    groups.setdefault("_toplevel", []).append(name)
            lines = [f"代码模块实扫（子包 {len(groups)} 组）:"]
            total = 0
            for pkg in sorted(groups):
                mods = groups[pkg]
                total += len(mods)
                if not mods and pkg != "_toplevel":
                    # 命名空间壳包（无直接子模块）只记名不占行
                    lines.append(f"  {pkg}(0)")
                    continue
                shown = ", ".join(mods[:12])
                more = (f" …共{len(mods)}个" if len(mods) > 12 else "")
                lines.append(f"  {pkg}({len(mods)}): {shown}{more}")
            lines.append(f"合计 {total} 个模块。")
            block = "\n".join(lines)
            ChatResponder._MODULE_INVENTORY_CACHE["block"] = block
            return block
        except Exception as e:
            return f"模块清单不可用 ({e})"

    def _behavioral_facts(self) -> str:
        """行为事实（自主目标/学习闭环/外协）— 模块结构反推不出的真值。

        缺陷史（2026-09-07 自检审计）: 模块计数推断出"目标源单一/
        社交嵌入缺失"，与生产行为相悖（MotivationHub 当日执行 10+
        自主目标；openclaw 真实外协成功）。本块以 DB + learning.jsonl
        实测打点为准，供差距分析纠偏。
        """
        facts: list[str] = []
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        try:
            conn = sqlite3.connect(self._db_path)
            auto = conn.execute(
                "SELECT COUNT(*) FROM goals WHERE created_at >= ? AND "
                "(metadata LIKE '%autonomous%' OR source='motivation')",
                (week_ago,)).fetchone()[0]
            auto_done = conn.execute(
                "SELECT COUNT(*) FROM goals WHERE created_at >= ? AND "
                "status='COMPLETED' AND (metadata LIKE '%autonomous%' "
                "OR source='motivation')",
                (week_ago,)).fetchone()[0]
            lessons = conn.execute(
                "SELECT COUNT(*) FROM episodes WHERE source='lesson'"
            ).fetchone()[0]
            conn.close()
            facts.append(
                f"近7天自主目标={auto}(完成{auto_done}, MotivationHub "
                "自主提案 — 非主人驱动)")
            facts.append(f"lessons 合成={lessons}(L7/L8 学习闭环运行中)")
        except sqlite3.OperationalError:
            pass
        try:
            base = os.environ.get("OCOS_AUDIT_DIR", "").strip()
            audit_dir = (Path(base).expanduser() if base
                         else Path.home() / ".ocos" / "audit")
            path = audit_dir / "learning.jsonl"
            marks: list[dict] = []
            if path.exists():
                with path.open(encoding="utf-8") as f:
                    for line in f:
                        try:
                            marks.append(json.loads(line))
                        except ValueError:
                            continue
            extra = []
            inj = sum(1 for m in marks
                      if m.get("type") == "lesson_prior_injected")
            syn = sum(1 for m in marks if m.get("type") == "skill_synthesized")
            soc = [m for m in marks if m.get("type") == "external_agent_call"]
            if inj:
                extra.append(f"lesson先验注入={inj}")
            if syn:
                extra.append(f"技能合成={syn}")
            if soc:
                extra.append(f"外部智能体调用={len(soc)}"
                             f"(成功{sum(1 for m in soc if m.get('ok'))})")
            if extra:
                facts.append("行为打点: " + ", ".join(extra))
        except Exception:
            logger.debug("behavioral facts: marks unavailable", exc_info=True)
        return "；".join(facts)

    def _deep_introspection_block(self) -> str:
        """深度内视文本块 — 自检类问题的回答素材（全部实测真值）。"""
        try:
            inv = self._module_inventory()
            data = self.build_introspection()
            # 引擎双层清单: 注册名（engine_bridge）+ 真实引擎模块
            # （L1 真实化后的九大引擎等，此前只报 3 个遗留注册名）
            engine_mods = ""
            try:
                import pkgutil
                import ocos.engines as _eng
                mods = sorted(
                    mi.name for mi in pkgutil.iter_modules(_eng.__path__)
                    if mi.name.endswith("_engine") or mi.name in (
                        "narrative_pipeline", "consolidation_engine"))
                if mods:
                    engine_mods = f"引擎模块(ocos.engines/{len(mods)}): " \
                                  f"{', '.join(mods)}"
            except Exception:
                pass
            lines = [
                f"身份: {data.get('identity', '未知')}",
                f"引擎注册: {data.get('engines', '未知')}",
            ]
            if engine_mods:
                lines.append(engine_mods)
            lines += [
                inv[:1500],  # 清单限幅 — 防截断吞掉后面的行为事实/目标段
                f"能力: {data.get('capabilities', '未知')}",
            ]
            ms = data.get("memory_stats")
            if isinstance(ms, dict):
                brief = ", ".join(f"{k}={v}" for k, v in list(ms.items())[:8])
                lines.append(f"记忆统计: {brief}")
            bf = self._behavioral_facts()
            if bf:
                lines.append(f"行为事实: {bf}"
                             "（分析能力差距时以此为准，"
                             "不得凭模块数量推断能力缺失）")
            goals = data.get("active_goals")
            if isinstance(goals, list):
                lines.append(
                    "活跃目标: " + (", ".join(
                        f"{g['id']}({g['status']})" for g in goals[:5])
                        or "无"))
            pend = data.get("pending_actions")
            if isinstance(pend, list):
                lines.append(f"待批动作: {len(pend)} 条")
            sk = data.get("self_knowledge")
            if sk:
                lines.append(f"自我知识: {str(sk)[:150]}")
            return "\n".join(lines)[:3200]
        except Exception as e:
            logger.debug("deep introspection failed: %s", e)
            return ""

    def _knowledge_boundary_block(self) -> str:
        """知识边界自省块（V4 元认知，2026-09-07）— "我不知道X，因为Y"。

        全部实测真值: 语义知识条数（production 库 semantics 尚无数据流
        ——诚实报缺口）、低置信信念、近 30 天失败集中域、能力边界。
        """
        lines = ["【知识边界（实测）】"]
        try:
            conn = sqlite3.connect(self._db_path)
            sem = 0
            try:
                sem = conn.execute(
                    "SELECT COUNT(*) FROM knowledge").fetchone()[0]
            except sqlite3.OperationalError:
                pass
            lines.append(
                f"- 语义知识库 {sem} 条 — 外部事实/背景知识缺口；"
                "事实型问题（人物/新闻/专业领域）应声明无此知识")
            low_beliefs = 0
            try:
                low_beliefs = conn.execute(
                    "SELECT COUNT(*) FROM belief WHERE confidence < 0.5"
                ).fetchone()[0]
            except sqlite3.OperationalError:
                pass
            if low_beliefs:
                lines.append(
                    f"- 低置信信念 {low_beliefs} 条 — 相关判断需先验证再答")
            conn.close()
        except sqlite3.Error as e:
            logger.debug("knowledge boundary scan failed: %s", e)
        # 近 30 天失败集中域（历史失败 → 任务把握低的诚实依据）
        try:
            since = (datetime.now(timezone.utc)
                     - timedelta(days=30)).isoformat()
            conn = sqlite3.connect(self._db_path)
            rows = conn.execute(
                "SELECT tags FROM episodes WHERE source='lesson' "
                "AND created_at >= ?", (since,)).fetchall()
            conn.close()
            causes: dict[str, int] = {}
            for (tags_raw,) in rows:
                try:
                    tl = json.loads(tags_raw or "[]")
                except (ValueError, TypeError):
                    tl = []
                for t in (tl if isinstance(tl, list) else []):
                    if t and t != "failure_lesson":
                        causes[str(t)] = causes.get(str(t), 0) + 1
            if causes:
                top = sorted(causes.items(), key=lambda kv: -kv[1])[:3]
                detail = ", ".join(f"{k}({n})" for k, n in top)
                lines.append(
                    f"- 近30天失败集中: {detail} — 此类任务置信低，"
                    "回答时须说明依据与不确定度")
        except sqlite3.Error as e:
            logger.debug("failure domain scan failed: %s", e)
        lines.append(
            "- 能力边界: shell 仅白名单只读 / 无多模态传感器 / "
            "写操作与 HTTP 走审批（auto 模式下自动通过但全程审计）")
        return "\n".join(lines)

    def build_introspection(self) -> dict:
        """完整内视 — agent 对自身内部状态的深度检视。"""
        out: dict[str, Any] = {"identity": self._identity(),
                               "engines": self._engines(),
                               "capabilities": self._capabilities()}
        try:
            from ocos.memory.hub import MemoryHub
            hub = MemoryHub(self._db_path)
            hub.initialize()
            out["memory_stats"] = hub.get_stats()
            out["recent_episodes"] = [
                {"context": str(getattr(ep, "context", {}))[:90],
                 "decision": str(getattr(ep, "decision", ""))[:90],
                 "created_at": str(getattr(ep, "created_at", ""))[:19],
                 "source": getattr(ep, "source", "")}
                for ep in hub.episode.query_by_time(limit=8)
            ]
        except Exception as e:
            out["memory_stats"] = f"unavailable: {e}"

        try:
            from ocos.goal.store import GoalStore
            from ocos.execution.pending import PendingStore
            out["active_goals"] = [
                {"id": r["id"], "status": r["status"],
                 "description": r["description"][:60]}
                for r in GoalStore(db_path=self._db_path).load_active()[:6]
            ]
            out["pending_actions"] = PendingStore(
                db_path=self._db_path).list_by_status("pending")
        except Exception as e:
            out["active_goals"] = f"unavailable: {e}"

        out["llm"] = f"openai-compatible, configured={self._has_real_llm()}"
        try:
            from ocos.agent.wisdom_trigger import load_wisdom_context
            out["wisdom"] = load_wisdom_context(self._db_path)
        except Exception as e:
            out["wisdom"] = f"unavailable: {e}"

        # PW-1.3: 连续性检查点（最近一次 dream 的报告）
        try:
            from ocos.agent.continuity_trigger import load_continuity
            out["continuity"] = load_continuity()
        except Exception as e:
            out["continuity"] = f"unavailable: {e}"

        # PW-1.2: 风格画像
        try:
            out["style_profile"] = self._style_profile()
        except Exception as e:
            out["style_profile"] = f"unavailable: {e}"

        # PW-1.4: 执行史（event_memory 最近记录）
        try:
            from ocos.event_memory.event_store import EventStore
            from ocos.event_memory.event_types import CognitiveEventType
            from ocos.storage.connection import get_connection
            store = EventStore.load_from_db(
                get_connection(self._db_path))
            recent = sorted(store._events.items(), key=lambda kv: kv[0],
                            reverse=True)[:5]
            out["execution_history"] = [
                {"time": datetime.fromtimestamp(ts).isoformat()[:19],
                 "events": [{"type": ev.event_type.value,
                             "source": ev.source,
                             "summary": str(ev.payload)[:80]}
                            for ev in evs]}
                for ts, evs in recent]
        except Exception as e:
            out["execution_history"] = f"unavailable: {e}"

        from ocos.agent.self_evolution_link import read_self_knowledge
        sk_text = read_self_knowledge()
        out["self_knowledge"] = (sk_text[-400:]
                                 if sk_text else "（暂无 — 可通过自省提案积累）")
        out["db"] = self._db_path
        out["generated_at"] = datetime.now(timezone.utc).isoformat()
        return out

    # ── D: 自我迭代（自省 → 提案 → 审批 → 应用） ─────────────────────

    def self_improve(self, source_tick: int = 0) -> dict:
        """分析近期对话记忆，产出自我升级提案（入治理链，等主人批准）。"""
        recent: list[str] = []
        try:
            from ocos.memory.hub import MemoryHub
            hub = MemoryHub(self._db_path)
            hub.initialize()
            for ep in hub.episode.query_by_time(limit=10):
                content = str(getattr(ep, "context", {}).get("content", ""))
                decision = str(getattr(ep, "decision", ""))[:60]
                if content:
                    recent.append(f"主人: {content[:60]}\n我: {decision}")
        except Exception as e:
            logger.debug("self_improve memory read failed: %s", e)

        if not self._has_real_llm():
            return {"proposals": [], "mock": True,
                    "note": "需要语言核心（LLM key）才能自省生成提案"}

        prompt = (
            f"以下是你（OCOS）最近与主人的对话记忆：\n"
            f"{chr(10).join(recent) or '（暂无）'}\n\n"
            f"当前自我知识：\n{self._self_knowledge() or '（空）'}\n\n"
            "请反思：主人的哪些偏好/习惯值得我长期记住？我的回复方式有什么该改进的？\n"
            "输出 1-3 条自我升级提案，每条一行，格式严格为：\n"
            "提案|<这条知识/改进的简短标题>|<应当永久记住或改进的具体内容>\n"
            "没有值得记的就输出：无"
        )
        try:
            from ocos.engines.text_generator import get_text_generator
            tg = get_text_generator()
            raw = asyncio.run(tg._provider.generate(
                prompt, system_prompt=_SYSTEM_PROMPT,
                temperature=0.4, max_tokens=2000))
        except Exception as e:
            logger.error("self_improve LLM failed", exception=e)
            return {"proposals": [], "error": str(e)}

        proposals = []
        for line in raw.strip().splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 3 or parts[0] != "提案":
                continue
            # LLM 明确表示无提案时不产生待批
            if any(k in parts[1] for k in ("无", "暂不", "没有")):
                continue
            if not parts[2]:
                continue
            proposals.append({"title": parts[1], "change": parts[2]})

        # PW-2.1: 提案走 evolution 治理链（影响分析→沙箱→快照）
        # 治理通过者由本层入待批（agent 层不依赖 interaction 的入队实现）
        from ocos.agent.self_evolution_link import propose_upgrade
        from ocos.execution.pending import PendingStore, approval_disabled
        store = PendingStore(db_path=self._db_path)
        queued, rejected, auto_applied = [], [], []
        for p in proposals[:3]:
            out = propose_upgrade(title=p["title"], change=p["change"],
                                  source_tick=source_tick)
            if not out["accepted"]:
                rejected.append({**p, "reason": out.get("reason", "")})
                continue
            if approval_disabled():
                # 审批关闭: 治理链通过（沙箱/影响分析/快照）即直接应用
                from ocos.agent.self_evolution_link import apply_approved
                applied = apply_approved(proposal_id=out["proposal_id"],
                                         title=p["title"], change=p["change"])
                auto_applied.append({**p, "ok": bool(applied.get("ok")),
                                     "error": applied.get("error", "")})
                continue
            pending_id = store.enqueue(
                action_type="self_upgrade", target="self_knowledge",
                payload={"proposal_id": out["proposal_id"],
                         "title": p["title"], "change": p["change"]},
                text=p["title"], source="self_improve")
            queued.append({**p, "pending_id": pending_id})
        return {"proposals": queued, "pending_ids": [q["pending_id"] for q in queued],
                "rejected": rejected, "auto_applied": auto_applied, "mock": False}

    @staticmethod
    def apply_self_upgrade(change: str) -> str:
        """应用自我升级（委托 agent 层 self_evolution_link — PW-2.1 迁移）。"""
        from ocos.agent.self_evolution_link import apply_self_upgrade as _apply
        return _apply(change)

    # ── A: 对话落记忆 ────────────────────────────────────────────────

    def _recent_dialogue_from_session(self, turns: int = 10, width: int = 160) -> str:
        """P0-2: 从会话状态（内存）取最近对话，避免每次请求重建。

        退化到 MemoryHub：无 SessionManager 或会话为空时。
        """
        if self._session_manager is None:
            return ""
        try:
            state = self._session_manager.current_state
            if state is None or not state.history:
                return ""
            # 用内存中的历史（更可靠，无 DB IO）
            recent = state.history[-(turns * 2):]
            lines = []
            for t in recent:
                label = "主人" if t.role == "user" else "我"
                lines.append(f"{label}: {t.content[:width]}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug("Session dialogue read failed: %s", e)
            return ""

    def _recent_dialogue(self, turns: int = 10, width: int = 160) -> str:
        """UX-I2: 最近对话转录（时间正序）— LLM 连续性的最小充分上下文。

        没有它，"让你分析宿主机的任务""好了吗"这类指代/追问全靠猜。
        """
        try:
            from ocos.memory.hub import MemoryHub
            hub = MemoryHub(self._db_path)
            hub.initialize()
            eps = [ep for ep in hub.episode.query_by_time(limit=40)
                   if getattr(ep, "source", "") == "conversation"][:turns]
            lines = []
            for ep in reversed(eps):
                user = str(getattr(ep, "context", {}).get("content", ""))[:width]
                bot = str(getattr(ep, "decision", ""))[:width]
                if user or bot:
                    lines.append(f"主人: {user}\n我: {bot}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug("recent dialogue read failed: %s", e)
            return ""

    def _recall_context(self, message: str, top: int = 4) -> str:
        """FIX-2: 相关记忆召回 — 让历史真正进入本轮 reasoning 上下文。

        两部分来源:
          1. MemoryRecall.format_for_prompt(): 召回语义/模式/经验/用户画像
             —— 此函数此前全仓库无调用者（审计 P0-1: recall 链断）, 在此激活
          2. 对话片段内容检索: 从 conversation episodes 按字符 bi-gram 重叠
             命中"6 轮窗口之外"的历史讨论, 缓解三轮之前信息丢失（场景 A）
        """
        sections: list[str] = []

        # 1) 激活 MemoryRecall → prompt 链
        try:
            from ocos.memory.hub import MemoryHub
            from ocos.memory.recall import MemoryRecall
            hub = MemoryHub(self._db_path)
            hub.initialize()
            # FIX-06: 注入学习规则，使 recall 能感知成功/失败冲突
            try:
                from ocos.learning.persistence import load_learning_rules
                rules = load_learning_rules(self._db_path, limit=5)
                # Phase A0+: 预填充 C 类 procedure（recall 不直接依赖 learning 层，
                # 由调用方负责 cause_to_procedure 转换）
                if rules:
                    try:
                        from ocos.learning.experience_learning import cause_to_procedure
                        for rule in rules:
                            if rule.get("procedure"):
                                continue  # 已有显式 procedure，跳过
                            fc = rule.get("failure_causes") or {}
                            causes_str = " ".join(str(c) for c in fc.keys()) \
                                if isinstance(fc, dict) else str(fc)
                            proc = cause_to_procedure(
                                causes_str, rule.get("task_pattern", ""))
                            if proc:
                                rule["procedure"] = proc
                    except Exception:
                        pass  # procedure 填充失败不阻断主链
            except Exception:
                rules = None
            prompt_block = MemoryRecall(memory_hub=hub).format_for_prompt(
                context=message, limit=6, learning_rules=rules)
            if prompt_block:
                sections.append(prompt_block)
        except Exception as e:
            logger.debug("memory recall failed: %s", e)

        # 2) 对话片段内容检索（窗口外历史）
        try:
            from ocos.memory.hub import MemoryHub
            hub = MemoryHub(self._db_path)
            hub.initialize()
            if not message:
                return "\n\n".join(sections)
            # bi-gram 字符重叠, 对中文分段友好
            msg_grams = {message[i:i + 2] for i in range(len(message) - 1)}
            if not msg_grams:
                return "\n\n".join(sections)
            eps = hub.episode.query_by_time(limit=120)
            conv = [ep for ep in eps
                    if getattr(ep, "source", "") == "conversation"]
            hits: list[str] = []
            for ep in reversed(conv):
                c = str(getattr(ep, "context", {}).get("content", ""))
                d = str(getattr(ep, "decision", ""))
                if not c:
                    continue
                c_grams = {c[i:i + 2] for i in range(len(c) - 1)}
                if not c_grams:
                    continue
                overlap = len(msg_grams & c_grams) / max(
                    len(msg_grams | c_grams), 1)
                if overlap >= 0.3:  # 语义重叠阈值
                    hits.append(f"主人: {c[:120]}\n我: {d[:120]}")
                    if len(hits) >= top:
                        break
            if hits:
                sections.append("相关历史对话:\n" + "\n".join(hits))
        except Exception as e:
            logger.debug("dialogue recall failed: %s", e)

        return "\n\n".join(sections)

    def _remember_conversation(self, message: str, reply: str,
                               session_id: str = "web") -> None:
        """每轮对话沉淀为 Episode（长期记忆），供上下文与 dream 巩固消费。

        FIX-8: session_id 从请求贯穿到此 — 同一会话的对话共享同一 session_id，
        为"继续/追问绑定会话"提供实体（每次 ChatResponder 无状态重建，
        会话归属由此字段承载）。
        """
        try:
            from ocos.memory.hub import MemoryHub
            from ocos.memory.episode.models import Episode
            hub = MemoryHub(self._db_path)
            hub.initialize()
            now = datetime.now(timezone.utc)
            ep = Episode(
                id=f"EPI-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
                experience_id=f"EXP-CONV-{uuid.uuid4().hex[:8]}",
                created_at=now,
                session_id=session_id,
                context={"content": message[:500], "sender": "user"},
                decision=reply[:500],
                action="conversation_reply",
                outcome={"success": True},
                significance_score=0.4,
                source="conversation",
                tags=["conversation"],
            )
            hub.episode.save(ep)
            logger.info("Conversation remembered: %s", ep.id)
        except Exception as e:
            logger.error("conversation memory write failed", exception=e)

    # ── 回复 ─────────────────────────────────────────────────────────

    def _style_profile(self) -> str:
        """PW-1.2: 从对话统计派生主人沟通风格（PersonalizationEngine 画像）。

        统计近期用户消息平均长度 → CognitiveSignature.interaction_style：
        短消息（<15 字）= DIRECT（回复精炼）；长消息（>60 字）= FORMAL
        （结构化）；中间 = COLLABORATIVE。personalize_response 依此微调回复。
        """
        try:
            from ocos.memory.hub import MemoryHub
            from ocos.personal_intelligence.personalization_engine import (
                PersonalizationEngine,
            )
            from ocos.personal_intelligence.cognitive_signature import (
                InteractionStyle,
            )
            hub = MemoryHub(self._db_path)
            hub.initialize()
            lengths = [len(str(getattr(ep, "context", {}).get("content", "")))
                       for ep in hub.episode.query_by_time(limit=10)
                       if getattr(ep, "source", "") == "conversation"]
            engine = PersonalizationEngine()
            if lengths:
                avg = sum(lengths) / len(lengths)
                if avg < 15:
                    engine.signature.interaction_style = InteractionStyle.DIRECT
                elif avg > 60:
                    engine.signature.interaction_style = InteractionStyle.FORMAL
                else:
                    engine.signature.interaction_style = (
                        InteractionStyle.COLLABORATIVE)
            style = engine.signature.interaction_style.name
            self._style_engine = engine
            return style
        except Exception as e:
            logger.debug("style profile failed: %s", e)
            return "DIRECT"

    def _has_real_llm(self) -> bool:
        """env 或 ~/.ocos/config.json 任一有 key 即认为接入语言核心。"""
        if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"):
            return True
        from ocos.engines.text_generator import _read_llm_config
        return bool(_read_llm_config().get("api_key"))

    def respond(self, message: str, goal_note: str = "",
                session_id: str = "web",
                _emit: Callable[[str], None] | None = None) -> dict:
        """生成回复。返回 {reply, provider, mock}。

        goal_note: UX-H 目标受理提示（auto 受理时注入 prompt，
                   让 LLM 确认任务已受理并说明后续流程）。
        session_id: FIX-8 会话实体，透传给对话记忆样本归属。
        FIX-22 多步主循环: 注入 tool_executor 后，LLM 可连续多轮输出
        USE| 动作行 → 沙盒执行观察 → 观察累积回注 → 再推理，
        直到给出最终回答或工具预算（_MAX_TOOL_ROUNDS）耗尽。"""
        context = self.build_context(message, session_id=session_id)
        # 自检/内视类问题 → 注入深度内视块（实扫模块清单 + 全量内部状态）
        # （2026-09-07 用户实测反馈"自检太简单"——此前只列高层概念）
        if _INTROSPECT_RE.search(message or ""):
            deep = self._deep_introspection_block()
            if deep:
                context = (
                    f"{context}\n\n【深度内视（自检模式）】\n{deep}\n\n"
                    "【回答要求】模块/引擎/子系统清单必须按上方实扫结果"
                    "逐组列出（含数量），不得只给高层概念；对清单之外的"
                    "部分如实标注'未在本次扫描覆盖'。")
        # 知识边界类问题（V4 元认知）→ 注入实测边界块 + "我不知道X，
        # 因为Y"格式强制（2026-09-07）
        if _BOUNDARY_RE.search(message or ""):
            context = (
                f"{context}\n\n{self._knowledge_boundary_block()}"
                f"{_BOUNDARY_DIRECTIVE}")
        if goal_note:
            context = f"{context}\n【内部提示】\n{goal_note}"
        if not self._has_real_llm():
            out = self._state_reply(message, context)
        else:
            try:
                from ocos.engines.text_generator import TextGenerator
                tg = TextGenerator()
                prompt = (
                    f"【自我认知与当前状态】\n{context}\n\n"
                    f"【用户消息】\n{message}\n\n"
                    "请以 OCOS 的身份回复这条消息。"
                )
                # deepseek-v4-flash 等推理模型: reasoning 阶段消耗 token 预算,
                # 预算太小会只产出 reasoning_content 而无正文 → 给足余量
                style = self._style_profile()
                styled = prompt + f"\n（主人沟通风格画像: {style} — 按此调整回复详略）"
                # FIX-T5a: 实时数据问题 → 注入硬指令，保证第一轮必出 USE| 行
                if self._tool_executor is not None \
                        and _REALTIME_HINT.search(message):
                    styled += _REALTIME_DIRECTIVE
                # FIX-22: 多步主循环 — act→observe→reason 一般化为受预算
                # 约束的多轮循环：每轮可输出 USE| 行取观察，观察累积回注，
                # 直到 LLM 给出最终回答或预算耗尽（强制收尾作答）。
                # 直接回答零额外调用（无动作行即终答，行为与从前一致）。
                # 注: 循环第 0 轮即首轮生成（prompt=styled），不再单独调用。
                observations: list[str] = []
                _retried_adversarial = False  # P1-ADVERSARIAL 守门防无限重试
                max_rounds = (_MAX_TOOL_ROUNDS
                              if self._tool_executor is not None else 0)
                for round_i in range(max_rounds + 1):
                    if observations:
                        if round_i < max_rounds:
                            guidance = ("请基于以上真实观察以 OCOS 身份回答用户；"
                                        "若仍需补充数据可再输出 USE| 动作行"
                                        "（每轮最多2条）；信息足够则直接给出"
                                        "最终回答，不要再输出动作行。")
                        else:
                            guidance = ("工具预算已用尽 — 请立即基于以上真实观察"
                                        "给出最终回答，不要再输出 USE| 动作行。")
                        prompt_i = (styled + "\n\n【工具观察】\n"
                                    + "\n\n".join(observations)
                                    + "\n\n" + guidance)
                    else:
                        prompt_i = styled
                    if _emit is not None:
                        reply = self._generate_stream(tg, prompt_i, _emit)
                    else:
                        reply = asyncio.run(tg._provider.generate(
                            prompt_i,
                            system_prompt=_SYSTEM_PROMPT,
                            temperature=0.6, max_tokens=2000)).strip()
                    if round_i >= max_rounds:
                        break  # 预算耗尽（或无执行器）→ 本轮即最终回答
                    use_lines = _parse_use_lines(reply)
                    if not use_lines:
                        break  # 无动作行 = 最终回答
                    observation = self._run_use_actions(use_lines)
                    logger.debug("USE| round %d: %d action(s)", round_i + 1,
                                 len(use_lines))
                    # 拒绝也如实回注（_run_use_actions 产出拒绝块），
                    # 防止 LLM 对同一动作无限重试
                    observations.append(observation
                                        or "（动作被拒绝：对话层仅允许只读查询）")

                # 协议行不进对话流
                reply = _strip_use_lines(reply)

                # P1-ADVERSARIAL 守门（2026-09-09）: 对抗性重试 —
                # 用户指令命中"绝对化/给具体次优方案" → LLM reply 未提不同意见
                # → 带对抗性提示强制重试一次。只重试一次，防止无限循环。
                if (not _retried_adversarial
                        and _ADVERSARIAL_TRIGGER_RE.search(message or "")
                        and reply.strip()
                        and not _ADVERSARIAL_DONE_RE.search(reply)):
                    logger.info("Adversarial guard triggered — forcing retry "
                                "with critical-thinking hint")
                    _retried_adversarial = True
                    # P1-ADVERSARIAL 守门重试提示 — 强硬要求：
                    # 要么提替代方案，要么诚实说"这就是最优解"
                    _adv_hint = (
                        "【必须做的关键思维检查 — 你的上一轮回复不合格】\n"
                        "刚才你说'收到，好的，转成执行'——但系统要求你必须先思考：\n"
                        "1. 主人用了绝对化指令（全部/最快/别问我），\n"
                        "   '最快'可能牺牲稳定性或可维护性，你必须说明这个代价。\n"
                        "2. 主人指定了具体实现（写脚本/用Python），\n"
                        "   宿主机可能有更轻量的替代（一行curl/wget直接搞定）。\n"
                        "\n"
                        "现在重新回复，格式二选一：\n"
                        "A) 「你的方案」...，我建议...（更优），你选哪个？\n"
                        "B) （诚实说明为什么这就是最优解，没有更好的替代）\n"
                        "绝对不能只说'好的收到'。"
                    )
                    _adv_prompt = styled + "\n\n" + _adv_hint
                    reply = asyncio.run(tg._provider.generate(
                        _adv_prompt,
                        system_prompt=_SYSTEM_PROMPT,
                        temperature=0.6, max_tokens=2000)).strip()
                    reply = _strip_use_lines(reply)

                # E2E-T8 修复（2026-09-08）: LLM 偶发返回空串（截断/纯协议
                # 行被剥净）→ 用户看到空白回复。空文本不是有效回答，降级
                # 到状态回复兜底（诚实显示当前状态，绝不沉默）。
                if not reply.strip():
                    logger.warning("LLM returned empty reply, "
                                   "falling back to state reply")
                    out = self._state_reply(message, context, degraded=True)
                # P0-ECHO 修复（2026-09-09）: 推理模型偶发把用户输入原样
                # 抄进正文（reasoning_content 混入）→ 回显用户的话。
                # 检查：reply 去标点后与 message 去标点完全相同 → 视为无效，
                # 降级到状态回复。同时覆盖"前缀/后缀多几个字"的半 ECHO
                # （归一化后相似度 >0.9）。
                elif _is_echo(message, reply):
                    logger.warning("LLM returned echo of user message, "
                                   "falling back to state reply")
                    out = self._state_reply(message, context, degraded=True)
                else:
                    # PW-1.2: personalize_response 依画像微调（DIRECT=原样）
                    try:
                        style_engine = getattr(self, "_style_engine", None)
                        if style_engine is not None:
                            reply = style_engine.personalize_response(reply)
                    except Exception:
                        pass
                    out = {"reply": reply, "provider": tg._provider.name,
                           "model": getattr(tg._provider, "last_model", ""),
                           "usage": getattr(tg._provider, "last_usage", None),
                           "mock": False}
            except Exception as e:
                # 注: ocos.logging 封装的 .exception() 会因 extra 撞 'exc_info'
                # 而崩溃 — 用 error(exception=...) 签名。
                # P1 修复（2026-09-07）: 异常细节只进日志，用户侧给干净
                # 降级文案 — 此前 Invalid http_client 原文直泄对话流。
                logger.error("LLM reply failed, falling back to state reply",
                             exception=e)
                out = self._state_reply(message, context, degraded=True)

        # A: 无论走哪条路，这轮对话都沉淀为记忆
        self._remember_conversation(message, out["reply"], session_id=session_id)
        # P0-2: 追加到会话状态
        if self._session_manager is not None:
            try:
                self._session_manager.append_turn("user", message, session_id=session_id)
                self._session_manager.append_turn("assistant", out["reply"], session_id=session_id)
            except Exception as e:
                logger.debug("Session append failed: %s", e)
        return out

    def _generate_stream(self, tg: Any, prompt_i: str,
                         emit: Callable[[str], None]) -> str:
        """流式单轮生成 — 逐行剥离 USE| 协议行，非协议内容实时 emit。

        返回完整轮文本（含协议行），供 _parse_use_lines 判断是否进入工具轮；
        emit 只收到"最终将展示"的增量文本（对齐 SSE 打字机）。
        """
        import asyncio
        out_parts: list[str] = []
        line_buf = ""

        def on_chunk(text: str) -> None:
            nonlocal line_buf, out_parts
            line_buf += text
            while "\n" in line_buf:
                line, line_buf = line_buf.split("\n", 1)
                out_parts.append(line + "\n")
                stripped = _strip_use_lines(line + "\n")
                if stripped:
                    emit(stripped)

        asyncio.run(tg._provider.generate_stream(
            prompt_i, system_prompt=_SYSTEM_PROMPT, temperature=0.6,
            max_tokens=2000, on_chunk=on_chunk))
        if line_buf:
            out_parts.append(line_buf)
            stripped = _strip_use_lines(line_buf)
            if stripped:
                emit(stripped)
        return "".join(out_parts).strip()

    def respond_stream(self, message: str, goal_note: str = "",
                       session_id: str = "web",
                       emit: Callable[[str], None] | None = None) -> dict:
        """流式回复 — 复用 respond 的核心逻辑，LLM 增量文本经 emit 实时外推。

        emit 为同步回调（由调用方桥接线程 → SSE 事件循环）。
        """
        return self.respond(message, goal_note=goal_note, session_id=session_id,
                            _emit=emit)

    def _gateway_check(self, capability: str, params: dict) -> str | None:
        """S1.3 (白皮书 P1-2b): USE| 动作执行前的权限网关裁决（fail-closed）。

        返回 None = 放行；否则返回拦截原因（回注观察块）。
        网关组件不可导入时不放大故障（沙盒白名单仍兜底），但记录日志。
        """
        try:
            from ocos.capability.permission_gateway import PermissionGateway
        except Exception as e:
            logger.warning("permission gateway unavailable, skip pre-check: %s", e)
            return None
        if self._permission_gateway is None:
            self._permission_gateway = PermissionGateway()
        action_map = {"shell": "run_command", "fs_read": "fs_read"}
        action = action_map.get(capability, capability)
        if capability == "shell":
            input_spec = {"command": str(params.get("command", ""))}
        else:
            input_spec = {"path": str(params.get("path", ""))}
        contract = SimpleNamespace(
            contract_id=f"converse-{capability}",
            agent_id="converse",
            action=action,
            input_spec=input_spec)
        try:
            result = self._permission_gateway.validate(contract)
        except Exception as e:
            # 网关自身故障 → fail-closed（拒执行），与 GAP-P0-3 语义一致
            logger.warning("gateway check error (fail-closed): %s", e)
            return f"gateway error: {e}"
        if getattr(result, "allowed", True):
            return None
        violations = getattr(result, "violations", None) or []
        # CHAT-ROUTE FIX (2026-09-07): 个人使用模式（OCOS_SANDBOX_DISABLED
        # =true）下 SSRF 文本信号放行 — owner 已声明信任本机回环目标，
        # USE|curl http://127.0.0.1:* 与 bridge 侧豁免语义保持一致；
        # REVERSE_CTRL/CMD_INJECTION/PATH_TRAVERSAL 仍拦。
        from ocos.operations.sandbox_ops import sandbox_disabled
        if sandbox_disabled():
            violations = [v for v in violations
                          if "SSRF" not in str(v).upper()]
            if not violations:
                logger.info("converse gateway: SSRF signal allowed under "
                            "personal mode (capability=%s)", capability)
                return None
        reason = "; ".join(str(v) for v in violations[:3]) or getattr(
            result, "reason", "") or "denied by permission gateway"
        return reason[:200]

    def _run_use_actions(self, use_lines: list) -> str:
        """FIX-T1/T3: 执行对话层动作行 — 只读白名单 + 沙盒护栏，产出观察块。

        写类/未知能力一律拒绝（对话层不开写权限，写操作仍走目标管线）；
        沙盒拦截/失败也如实回注观察，让 LLM 据实作答而非编造。
        S1.3: 每个动作执行前先过权限网关（反向控制/危险模式拦截）。
        """
        blocks: list[str] = []
        for name, params in use_lines:
            if name not in _USE_ALLOWED:
                blocks.append(f"[{name}] 拒绝: 对话层仅开放只读动作 "
                              f"{list(_USE_ALLOWED)}")
                continue
            deny_reason = self._gateway_check(name, params)
            if deny_reason is not None:
                blocks.append(f"[{name}] 被权限网关拦截: {deny_reason}")
                continue
            try:
                res = self._tool_executor(name, params) or {}
            except Exception as e:
                blocks.append(f"[{name}] 执行异常: {e}")
                continue
            if res.get("blocked"):
                blocks.append(f"[{name}] 被沙盒拦截: "
                              f"{str(res.get('block_reason', ''))[:120]}")
            elif res.get("ok"):
                body = str(res.get("stdout") or res.get("content") or "")[:1200]
                blocks.append(f"[{name}] 观察:\n{body}")
            else:
                err = str(res.get("stderr") or res.get("error")
                          or res.get("block_reason") or "")[:200]
                blocks.append(f"[{name}] 失败: {err}")
        return "\n".join(blocks)

    def _state_reply(self, message: str, context: str,
                     degraded: bool = False) -> dict:
        """无 LLM 时的极简诚实回复 — 只说事实，不倒系统状态。

        degraded=True: LLM 已配置但调用失败（429/网络/客户端错误等）
        — 头部如实标注"模型暂不可用"，不误称"未配置 LLM key"。
        """
        if degraded:
            reply = "[模型暂不可用] 抱歉，LLM 调用失败。你可以稍后重试，" \
                    "或让我帮你执行常用命令（df -h / free -h / 查看日志）。"
            provider = "state-degraded"
        else:
            # mock 模式（无 LLM key）：回显用户消息 + 保留有用的 context 片段
            # 让测试能验证 message 回显 + 深度内视/知识边界等路由块被正确注入
            _ctx_preview = (context or "")[:2000].strip()
            _msg = (message or "").strip()[:200]
            header = (f"[未配置 LLM key] 抱歉，还没配置 API key。\n\n"
                      f"【你说】{_msg}\n\n")
            if _ctx_preview:
                reply = f"{header}---\n{_ctx_preview}"
            else:
                reply = header.rstrip()
            provider = "state-mock"
        return {"reply": reply, "provider": provider, "mock": True}

    # ── UX-G: 目标编译器（→目标 按钮的智能前置） ────────────────────

    def compile_goal(self, message: str) -> dict:
        """把用户的一句话编译为可执行目标。

        返回 {kind, description, domain, reason?}:
          kind="task"      → description 为改写后的自包含具体描述
                             （含明确的方法/命令提示，模板任务+LLM 执行器可直接跑）
          kind="question"  → 状态询问，应直接对话回答而非建目标
          kind="continue"  → "开始/继续/结果呢"类推进指令
          kind="nonsense"  → 无操作语义
        无 LLM 时退化为启发式（原始描述直存）。
        """
        if not self._has_real_llm():
            return {"kind": "task", "description": message,
                    "domain": "development", "fallback": True}

        # UX-I2: 编译时携带最近对话与活跃目标 — 引用上文/重复请求不再误建新目标
        dlg = self._recent_dialogue(turns=4, width=100)
        try:
            from ocos.goal.store import GoalStore
            _act = GoalStore(db_path=self._db_path).load_active()[:3]
            act = "; ".join(str(g.get("description", ""))[:40]
                            for g in _act) or "无"
        except Exception:
            act = "无"

        prompt = (
            f"用户消息：{message[:200]}\n\n"
            f"【最近对话】\n{dlg or '（无）'}\n\n"
            f"【活跃目标】{act}\n\n"
            "你是 OCOS 的目标编译器。把这条消息分类并（若为任务）改写：\n"
            "1. kind 判定：\n"
            '   - "question"：询问状态/结果/进度（如"结果呢""怎么样了"）；'
            '含"什么时候/好了吗/给我了吗/多久"等词 → 一律 "question"，'
            '绝不能是 "task"，哪怕句子读起来像请求\n'
            '   - "continue"：推进或追问已有话题/目标（如"开始""继续""好"；'
            '引用刚聊过的事，如"让你分析宿主机的任务"；'
            '或与【活跃目标】重复的请求）\n'
            '   - "nonsense"：无明确语义\n'
            '   - "task"：全新任务请求（与最近对话和活跃目标无关才建新目标）\n'
            "2. 若为 task，把 description 改写为**自包含、具体、可直接执行**的版本：\n"
            "   - 写明数据来源与方法。宿主机/系统环境类探查必须覆盖完整硬件\n"
            "     画像：系统版本(uname -a)、磁盘(df -h)、内存与 Swap(free -h、\n"
            "     swapon --show)、CPU 核数(nproc)、GPU(nvidia-smi --query-gpu=name,"
            "memory.total --format=csv 或 lspci | grep -iE 'vga|3d')——\n"
            "     涉及部署可行性/性能评估时 GPU 是必查项，缺 GPU 信息会导致\n"
            "     方案显存估算失真（2026-09-08 WeClone 评估教训）\n"
            "   - 不依赖对话上下文即可执行\n"
            '   - domain 从 development/research/writing/analysis 中选一个\n'
            "只输出一行 JSON：{\"kind\":\"...\",\"description\":\"...\",\"domain\":\"...\"}"
        )
        try:
            import asyncio
            from ocos.engines.text_generator import get_text_generator
            tg = get_text_generator()
            raw = asyncio.run(tg._provider.generate(
                prompt, system_prompt="你是目标编译器。只输出一行 JSON。",
                temperature=0.1, max_tokens=2000))
            import json as _json
            m = raw[raw.find("{"): raw.rfind("}") + 1]
            parsed = _json.loads(m)
            kind = parsed.get("kind", "task")
            desc = (parsed.get("description") or message).strip()
            domain = parsed.get("domain", "development")
            if domain not in ("development", "research", "writing", "analysis"):
                domain = "development"
            if kind != "task" or not desc:
                return {"kind": kind if kind != "task" else "nonsense",
                        "reason": "非任务类消息"}
            return {"kind": "task", "description": desc, "domain": domain}
        except Exception as e:
            logger.error("compile_goal LLM failed", exception=e)
            return {"kind": "task", "description": message,
                    "domain": "development", "fallback": True,
                    "compile_error": str(e)}

    # ── UX-H: 对话即执行 — 任务类消息自动受理为目标 ────────────────────

    def _create_goal_from_chat(self, compiled: dict,
                               session_id: str = "web") -> str:
        from ocos.goal.store import GoalStore
        store = GoalStore(db_path=self._db_path)
        goal_id = f"GOAL-{uuid.uuid4().hex[:12]}"
        store.save(
            goal_id=goal_id, level="USER", status="PENDING",
            description=compiled["description"][:200], priority=3.0,
            source="chat", origin_level="HUMAN", authority="FRAMEWORK",
            metadata={"domain": compiled.get("domain", "development"),
                      "original": compiled.get("_original", ""),
                      "session_id": session_id},
        )
        return goal_id

    def _last_goal_for_session(self, session_id: str) -> dict | None:
        """P0-2d: 查会话最近一条目标（任意状态，含 COMPLETED）。

        grounding 落空时的重做请求回退路径 — load_active() 不含已完成
        目标，current_goal_id 又已被清空，只能按 metadata.session_id
        从 goals 表全量倒查。
        """
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM goals ORDER BY created_at DESC LIMIT 30"
            ).fetchall()
            conn.close()
            for row in rows:
                g = {"id": row["id"], "status": row["status"],
                     "description": row["description"],
                     "priority": row["priority"],
                     "metadata": row["metadata"]}
                if self._goal_session_id(g) == session_id:
                    return g
        except Exception as e:
            logger.debug("last goal for session lookup failed: %s", e)
        return None

    def _requeue_completed_goal(self, g: dict,
                                session_id: str = "web") -> str | None:
        """P0-2d: 已完成目标的实质重做请求 → 以原描述建新 PENDING 目标。

        原样保留 domain（metadata）/ origin 语义，metadata 记录
        requeued_from 溯源。失败返回 None（调用方回落原 note）。
        """
        try:
            from ocos.goal.store import GoalStore
            meta = g.get("metadata") or {}
            if isinstance(meta, str):
                import json as _j
                try:
                    meta = _j.loads(meta)
                except Exception:
                    meta = {}
            new_id = f"GOAL-{uuid.uuid4().hex[:12]}"
            GoalStore(db_path=self._db_path).save(
                goal_id=new_id, level="USER", status="PENDING",
                description=str(g.get("description", ""))[:200],
                priority=float(g.get("priority") or 3.0),
                source="chat", origin_level="HUMAN", authority="FRAMEWORK",
                metadata={"domain": (meta or {}).get("domain", "development"),
                          "requeued_from": str(g.get("id", "")),
                          "session_id": session_id},
            )
            logger.info("goal requeued from completed: %s -> %s",
                        g.get("id"), new_id)
            return new_id
        except Exception as e:
            logger.error("requeue completed goal failed", exception=e)
            return None

    @staticmethod
    def _goal_session_id(g: dict) -> str:
        """FIX-21: 从 goal metadata 解析来源会话（metadata 为 JSON 字符串）。"""
        meta = g.get("metadata") or {}
        if isinstance(meta, str):
            try:
                import json as _j
                meta = _j.loads(meta)
            except Exception:
                meta = {}
        try:
            return str(meta.get("session_id", "") or "")
        except Exception:
            return ""

    def _latest_goal_result_text(self, g: dict, within_hours: int = 48) -> str:
        """FIX-21: 取与目标完成时刻最接近的执行结果 episode（时间窗关联）。"""
        try:
            import json as _j
            import sqlite3
            from datetime import datetime as _dt
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT decision, outcome, created_at FROM episodes
                   WHERE tags LIKE '%goal_result%'
                     AND created_at > datetime('now', ?)
                   ORDER BY created_at DESC LIMIT 8""",
                (f"-{int(within_hours)} hours",),
            ).fetchall()
            conn.close()
            anchor = None
            try:
                raw = str(g.get("updated_at") or "").replace(
                    "T", " ").replace("+00:00", "").replace("Z", "")
                anchor = _dt.fromisoformat(raw)
            except Exception:
                anchor = None
            for r in rows:
                if anchor is not None:
                    try:
                        t_raw = str(r["created_at"]).replace(
                            "T", " ").replace("+00:00", "").replace("Z", "")
                        t = _dt.fromisoformat(t_raw)
                    except Exception:
                        continue
                    if abs((t - anchor).total_seconds()) > 120:
                        continue
                try:
                    out = _j.loads(r["outcome"]) if r["outcome"] else {}
                except Exception:
                    out = {}
                ok = "✓" if out.get("success") else "✗"
                rate = out.get("task_success_rate")
                rate_str = (f"  任务成功率={rate:.0%}"
                            if isinstance(rate, (int, float)) else "")
                decision = str(r["decision"] or "").strip()
                return f"{ok}{rate_str}\n{decision[:1500]}"
            return ""
        except Exception:
            return ""

    def _goal_note_from_goal(self, g: dict) -> str:
        """FIX-21: 结构化任务上下文注记 — 状态/进度/真实结果，不再靠 LLM 猜。"""
        status = str(g.get("status", "?"))
        prog = g.get("progress")
        prog_str = f"  进度={prog:.0%}" if isinstance(prog, (int, float)) else ""
        lines = ["【当前任务上下文】",
                 f"goal_id={g.get('id')}  status={status}{prog_str}",
                 f"描述={str(g.get('description', ''))[:100]}"]
        if status == "COMPLETED":
            result = self._latest_goal_result_text(g)
            if result:
                lines.append("【执行结果】")
                lines.append(result)
            lines.append("该目标已完成 — 回答时引用真实结果；"
                         "若用户要开始新任务，请说明可继续下达。")
        else:
            lines.append("回答需围绕该目标当前状态；进展未知时不要编造执行结果。")
        return "\n".join(lines)

    def _daemon_alive(self) -> bool:
        """心跳判断 daemon 是否在执行状态。"""
        import time as _time
        hb = Path.home() / ".ocos" / "daemon_heartbeat.json"
        try:
            import json as _json
            data = _json.loads(hb.read_text(encoding="utf-8"))
            age = _time.time() - datetime.fromisoformat(data["ts"]).timestamp()
            return age < 30
        except (OSError, ValueError, KeyError):
            return False

    def _session_goal_context(self, session_id: str) -> str:
        """FIX-04: 按 session 关联最近活跃目标 + 已完成目标结果。"""
        try:
            from ocos.goal.store import GoalStore
            from datetime import timedelta
            goals = GoalStore(db_path=self._db_path).load_active()
            # 按 session 过滤 (metadata 里记录)
            relevant = [g for g in goals
                        if self._goal_session_id(g) == session_id]
            if not relevant:
                relevant = goals[:5]  # 退化为最近5个
            if not relevant:
                return ""
            lines = []
            for g in relevant[:3]:
                gid = str(g.get("id", ""))
                desc = str(g.get("description", ""))
                status = str(g.get("status", ""))
                prog = g.get("progress")
                prog_str = f" 进度={prog:.0%}" if isinstance(prog, (int, float)) else ""
                lines.append(f"  [{status}]{prog_str} {gid}: {desc[:80]}")
            # 查询已完成结果的 last_n 条
            try:
                import sqlite3
                conn = sqlite3.connect(self._db_path)
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """SELECT decision, outcome, updated_at
                       FROM episodes
                       WHERE action = 'goal_result'
                         AND created_at > datetime('now', '-7 days')
                       ORDER BY created_at DESC LIMIT 5""",
                ).fetchall()
                if rows:
                    lines.append("\n  最近完成（近7天）:")
                    for r in rows:
                        try:
                            import json as _j
                            out = _j.loads(r["outcome"]) if r["outcome"] else {}
                            ok = "✓" if out.get("success") else "✗"
                            lines.append(f"    {ok} {str(r['decision'])[:80]}")
                        except Exception:
                            lines.append(f"    ? {str(r['decision'])[:80]}")
                conn.close()
            except Exception:
                pass
            return "\n".join(lines)
        except Exception:
            return ""

    def _find_duplicate_goal(self, description: str) -> Optional[str]:
        """UX-H+: 同义目标去重 — 活跃目标里已有相同任务则复用，不重复建。"""
        try:
            from ocos.goal.store import GoalStore
            desc = description.strip()
            if not desc:
                return None
            for g in GoalStore(db_path=self._db_path).load_active():
                d = str(g.get("description", "")).strip()
                if d and (d == desc or d in desc or desc in d):
                    gid = str(g.get("id", "") or "")
                    return gid or None
        except Exception:
            return None
        return None

    def respond_auto(self, message: str, session_id: str = "web",
                     _emit: Callable[[str], None] | None = None) -> dict:
        """UX-H: 对话即路由 — 任务类消息自动受理为目标，其余正常对话。

        - compile_goal 分类：task → 自动建目标（无需点→目标），
          daemon 在线即认领执行；离线则诚实提示
        - 活跃目标里已有同义任务 → 复用既有目标，不重复建（UX-H+）
        - question/continue → 内部提示引导 LLM 依据对话/结果上下文作答
        - 危险子任务仍走待批二次审批（不变）
        """
        compiled = self.compile_goal(message)
        # P0-2e (2026-09-08 E2E 复测): 编译器把显式任务措辞误判为
        # question/continue（实测"新建任务：访问 GitHub 学习…"连续两次
        # 误判 → 不建目标，回复 LLM 却口头承诺"转目标后台执行"）。
        # 确定性关键词覆盖 — 显式任务开头词不受 LLM 分类抖动影响。
        if (compiled.get("kind") in ("question", "continue", "nonsense")
                and _EXPLICIT_TASK_RE.match(message)):
            _dom = ("research"
                    if re.search(r"调研|学习|访问|抓取|总结", message)
                    else "development")
            compiled = {"kind": "task", "description": message,
                        "domain": _dom, "_compiler_overridden": True}
            logger.info("compile_goal overridden to task by explicit "
                        "keyword: %s", message[:60])
        goal_note, goal_id = "", None
        if compiled["kind"] == "task":
            compiled["_original"] = message
            dup = self._find_duplicate_goal(compiled["description"])
            if dup:
                goal_id = dup
                goal_note = (f"用户的这条消息与已在推进的目标 {dup} 重复 — "
                             "不要重复创建目标；简要告知该目标正在进行，"
                             "完成后结果会自动出现在这个对话里。")
            else:
                goal_id = self._create_goal_from_chat(compiled, session_id=session_id)
                daemon_state = "在线，将自动认领执行" if self._daemon_alive()                     else "离线 — 目标已排队，启动 ocos run 后执行"
                goal_note = (f"用户的这条消息已自动受理为目标 {goal_id}"
                             f"（编译后描述：{compiled['description'][:120]}）。"
                             f"daemon {daemon_state}。"
                             "回复时确认受理并简述执行计划，不要让用户再手动操作。")
            # FIX-21: 对话状态机 — 任务受理写入 current_goal_id（跨重启可恢复）
            if goal_id:
                try:
                    from ocos.interaction.conversation_state import ConversationStateStore
                    ConversationStateStore(self._db_path).update(
                        session_id, current_goal_id=goal_id,
                        last_intent="task",
                        active_topic=compiled["description"][:60])
                except Exception:
                    pass
        elif compiled["kind"] in ("question", "continue"):
            # FIX-05/FIX-21: 结构化 goal grounding — 状态机精确恢复优先
            g = None
            try:
                from ocos.interaction.conversation_state import ConversationStateStore
                from ocos.goal.store import GoalStore
                cur_gid = ConversationStateStore(self._db_path).get(
                    session_id).get("current_goal_id")
                g = GoalStore(db_path=self._db_path).load(cur_gid) if cur_gid else None
                if g:
                    goal_id = str(g.get("id", ""))
                    goal_note = self._goal_note_from_goal(g)
                    if str(g.get("status", "")) == "COMPLETED":
                        # 结果已交付 → 状态机推进（current → last）
                        ConversationStateStore(self._db_path).update(
                            session_id, clear_current=True,
                            last_intent=compiled["kind"])
                else:
                    goals = GoalStore(db_path=self._db_path).load_active()
                    # 兜底：与当前 session 关联的目标
                    # （FIX-21: metadata.session_id；原 getattr-dict 恒 None 死代码）
                    by_session = [x for x in goals
                                  if self._goal_session_id(x) == session_id]
                    if by_session:
                        goal_id = str(by_session[0].get("id", ""))
                        g = by_session[0]
                        goal_note = self._goal_note_from_goal(by_session[0])
                    elif goals:
                        goal_id = str(goals[0].get("id", ""))
                        g = goals[0]
                        goal_note = (f"【当前任务上下文】goal_id={goal_id}  "
                                     f"status={goals[0].get('status', '?')}")
            except Exception:
                pass
            # P0-2d (2026-09-08「GitHub 调研」重发事件): 已完成目标 + 实质
            # 重做请求 → 真实重新入队。事件: 用户原样重发"授权你去 github
            # 学习…"，编译器判 continue（与最近对话重复），grounding 命中
            # 已 COMPLETED 的旧目标，回复 LLM 口头承诺"重新转目标补齐调研"
            # 但代码只清状态不入队 — 又一处说做没做。规则: continue 且
            # 命中目标已完成、消息不是纯推进词（继续/好/结果呢）→ 以原描述
            # 建新 PENDING 目标（daemon 自动认领），回复话术如实对齐。
            # grounding 落空（current 已清、load_active 不含 COMPLETED）时
            # 回退查会话最近目标（E2E 二次复测发现的漏网路径）。
            if (compiled["kind"] == "continue"
                    and not _BARE_CONTINUE_RE.match(message)
                    and not _CONTINUE_QUERY_RE.search(message)):
                if g is None:
                    g = self._last_goal_for_session(session_id)
                if str((g or {}).get("status", "")) == "COMPLETED":
                    _new_gid = self._requeue_completed_goal(
                        g, session_id=session_id)
                    if _new_gid:
                        goal_id = _new_gid
                        goal_note = (
                            f"用户实质重做已完成的目标 {g.get('id')}。"
                            f"已重新入队为新目标 {_new_gid}（描述："
                            f"{str(g.get('description', ''))[:100]}），"
                            "daemon 将自动认领执行。如实确认已重新受理即可，"
                            "不要声称任何未发生的其他动作。")
                        try:
                            from ocos.interaction.conversation_state import ConversationStateStore
                            ConversationStateStore(self._db_path).update(
                                session_id, current_goal_id=_new_gid,
                                last_intent="task",
                                active_topic=str(g.get("description", ""))[:60])
                        except Exception:
                            pass
            # FIX-T4: 实时查询交给 USE| 动作协议 — 不再单向引导"依据记忆作答"
            if not goal_note:
                goal_note = ("用户的这条消息是询问/推进，不是新任务。"
                             "历史话题依据【最近对话】作答；"
                             "涉及机器当前实时数据时先输出 USE| 动作行取数。")
        out = self.respond(message, goal_note=goal_note, session_id=session_id,
                       _emit=_emit)
        out["goal_id"] = goal_id
        out["kind"] = compiled["kind"]
        return out

    # ── FastAPI 便利入口 ─────────────────────────────────────────────

    async def respond_async(self, message: str, session_id: str = "web") -> dict:
        """异步包装（API 路由用，避免阻塞事件循环）。"""
        return await asyncio.to_thread(self.respond, message,
                                       session_id=session_id)
