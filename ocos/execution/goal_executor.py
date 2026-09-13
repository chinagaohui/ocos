"""ocos goal exec — 直接执行器 (Phase 51: 绕过认领的同步执行).

背景 (生产测试发现 2026-09-04):
  daemon 认领链 (goal create → tick 认领 → TaskDecomposer 模板 → LLM 单命令)
  有架构断点: TaskDecomposer 忽略 goal 文本, 按 domain 模板产出
  "收集数据/分析数据/生成报告" 空壳任务; 且单任务只转一条白名单命令。

本模块: CLI 直接执行 — goal 描述 → LLM 分解为多条只读命令 → 逐条经
DecisionBridge 沙盒真实执行 → 汇总返回。完全绕开 daemon 认领与模板分解。

治理:
  - 不动内核: 不改 agent_runtime/daemon/tick; 纯新增 CLI 入口
  - 复用 DecisionBridge._handler_run_command (白名单+敏感路径+strict 沙盒)
  - LLM 只负责"描述→命令序列"转换, 不直接执行; 每条命令仍过沙盒闸门
  - 只读命令集 (与 bridge prompt 一致), 写操作拒绝
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ocos.logging import get_logger

logger = get_logger(__name__)

# 与 bridge UX-F1 白名单一致的只读命令前缀 (由 SandboxOps 最终裁决)
MAX_COMMANDS = 12
COMMAND_TIMEOUT = 30.0


@dataclass
class ExecResult:
    """单条命令执行结果。"""

    command: str = ""
    ok: bool = False
    blocked: bool = False
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    block_reason: str = ""


@dataclass
class GoalExecReport:
    """整体执行报告。"""

    goal_text: str = ""
    commands: list[ExecResult] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str = ""
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_text": self.goal_text,
            "commands": [{
                "command": c.command,
                "ok": c.ok,
                "blocked": c.blocked,
                "exit_code": c.exit_code,
                "stdout": c.stdout[:500],
                "stderr": c.stderr[:200],
                "block_reason": c.block_reason,
            } for c in self.commands],
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "summary": self.summary,
        }


class GoalDirectExecutor:
    """直接执行器 — 描述 → LLM 分解 → 沙盒逐条执行。"""

    def __init__(self, bridge: Any = None) -> None:
        self._bridge = bridge or self._build_bridge()

    # ── 装配 ──────────────────────────────────────────────────────

    def _build_bridge(self) -> Any:
        """构建带真实沙盒 handlers 的 DecisionBridge (与 daemon 同款闸门)。"""
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge(agent_id="goal-exec")
        bridge.attach_default_handlers()
        return bridge

    # ── LLM 分解 ──────────────────────────────────────────────────

    def decompose(self, goal_text: str) -> list[str]:
        """LLM: goal 描述 → 只读命令序列。

        返回命令列表; LLM 失败/不可用 → [] (调用方诚实降级)。
        """
        bridge = self._bridge
        if not self._llm_available():
            logger.warning("GoalDirectExecutor: LLM 不可用, 无法分解描述")
            return []
        budget_ok, reason = bridge._llm_budget_ok()
        if not budget_ok:
            logger.warning("GoalDirectExecutor: %s", reason)
            return []

        prompt = (
            f"用户目标: {goal_text}\n\n"
            "把上述目标拆解为**若干条可直接执行的只读 shell 命令**。\n"
            "要求:\n"
            "1. 每行一条命令, 严格格式 RUN|<命令>\n"
            f"2. 只允许只读信息命令, 优先: uname/hostnamectl/lscpu/lsblk/free/df/uptime/"
            f"ps/ip/cat /etc/os-release/ls/date/whoami/ping -c 4/who/curl -sI\n"
            "3. 禁止写操作 (rm/mv/mkdir/echo >/tee/编辑/安装/删除)\n"
            "4. 最多 8 条, 按信息类别组织: 系统/CPU/内存/磁盘/网络/进程\n"
            "5. 若目标无法用只读命令达成, 只输出 NONE|<原因>\n"
            "不要输出任何解释或其他格式。"
            "\n\n"
            # AUD-FIX (2026-09-12): 检索语法策略 — 生产实锤: 4 词 AND 查询
            # (`shell+quoting+escape+safety`) 在 GitHub search 必然 0 结果
            # (多词=AND), 任务被"部分失败"拖垮。给出确定性语法规则。
            "外部检索命令 (curl GitHub API) 额外规则:\n"
            "a. search/repositories 的多词查询是 AND 关系 — 关键词最多 2 个, "
            "宁少勿多 (如 q=shellcheck+static)\n"
            "b. 管道必须带 python3 解析并打印 total_count 和首条 full_name+stargazers_count, "
            "空结果时可见 'total_count=0' 而不是空输出\n"
            "c. 同一主题准备第二条**更宽**的查询 (2 词或 1 词) 作为兜底\n"
            "d. 部分成功也算成功: 只要拿到核心数据 (如头部仓库+star 数) 就足够交付\n"
            # AUD-FIX (2026-09-12): 任务-工具匹配 — 生产实锤: 'Kappa/ICC 阈值
            # 设定'类文献调研目标全投给 GitHub 只找到代码实现, 拿不到方法学
            # 文献, 任务诚实降级失败。文献类目标必须走学术检索 API。
            # QUOTA-FLIP (2026-09-12): OpenAlex 每日额度制 → arXiv 升主用。
            "e. 任务-工具匹配: 目标要 '阈值/文献依据/选型准则/方法学/惯例/理论' 时, "
            "GitHub 仓库只能找到代码实现, 回答不了文献依据 — 必须搭配学术检索:\n"
            "   主用: RUN|python3 /home/laogao/.ocos/scripts/arxiv.py "
            "\"<1-3个英文标准术语>\" [条数] — arXiv 免费无每日额度, 脚本内部"
            "处理限流退避与解析, 只传查询词禁止自己拼 URL\n"
            "   (⚠️ arXiv 是 1991 年后 STEM 预印本库: Landis&Koch 1977/Fleiss "
            "1981/Altman 1991 类经典期刊阈值文献大概率不收录, 只搜到应用类论文"
            "不是失败而是语料没有 → 改用 websearch.py 查权威二手来源)\n"
            "   兜底: OpenAlex (每日免费额度, UTC 午夜重置): RUN|curl -s "
            "--max-time 15 \"https://api.openalex.org/works?"
            "search=<1-3个英文标准术语>&per-page=3\" | "
            "python3 /home/laogao/.ocos/scripts/openalex.py\n"
            "   (输出含 ABS 摘要正文, 阈值/分级等结论常在摘要中; "
            "OpenAlex 返回 count= None 或 Rate limit = 当日额度耗尽 → "
            "直接换 arxiv.py, 不要反复重试; 禁止手写嵌套引号的 python -c)\n"
            "   学术检索词必须用标准英文术语 (如 inter-rater reliability / kappa / "
            "intraclass correlation), 不要用中文; "
            "拿到 3-5 篇权威文献的 标题+年份+摘要要点 即足以交付 — "
            "本环境抓不到全文 PDF, 不要因'只有摘要'判任务失败\n"
            # WEB-SEARCH (2026-09-12): 通用网页搜索通道 — 解析器落盘脚本,
            # LLM 只传查询词, 不拼 URL (规避手抄引号/编码崩溃)。
            "f. 通用网页搜索 (新闻/现状/评价/口碑/对比/教程/产品等非学术非代码信息): "
            "RUN|python3 /home/laogao/.ocos/scripts/websearch.py \"<查询词, 中英文均可>\" "
            "[条数] — 查询词作参数传入, 禁止自己拼 URL; ⚠️ cn.bing 是中文引擎, "
            "英文技术词会返回品牌/人名垃圾 → 用中文关键词 (如 'kappa系数 一致性 "
            "判定标准'); 脚本内部抓取 cn.bing.com "
            "免费引擎并解析, 返回 标题|URL|摘要, 要详情再用 curl -s --max-time 15 "
            "抓结果里的 URL; ⚠️ 结果列表混合噪音是常态 (4 条里 2 条品牌页 + 2 条"
            "统计学教程也发生过) — 有 2-3 条相关就逐条 curl 抓正文提取答案, "
            "禁止因列表含无关结果整体判失败; "
            "任务含 '评价/口碑/对比/新闻/最新' → 必须至少调用一次, "
            "GitHub 仓库数据替代不了社区口碑; ⚠️ 结论只能引用实际执行命令返回的数据, "
            "禁止编造'检索到某网站'的来源"
        )
        try:
            # 复用 bridge 的代理清理 + textgen
            tg = self._bridge._get_textgen()
            raw = asyncio.run(tg._provider.generate(
                prompt,
                # AUD-FIX: 强约束单行 — 多行命令(如 python3 -c "...\n...")
                # 会被逐行解析腰斩 (生产实锤: 'python3 -c "import shutil,'
                # 引号未闭合 → sh: Unterminated quoted string → goal 失败)
                system_prompt=("你是 OCOS 的命令分解器。只输出 RUN|<命令> 行。"
                               "每条命令必须压成单行: 复杂脚本用 "
                               "python3 -c \"import ...; ...\" 分号连接, "
                               "禁止命令内部出现换行符。"),
                temperature=0.1, max_tokens=2000))
        except Exception as e:
            logger.warning("GoalDirectExecutor: LLM decompose failed: %s", e)
            return []

        commands: list[str] = []
        _buf: str | None = None   # AUD-FIX: 引号未闭合时的续行缓冲
        for line in raw.strip().splitlines():
            line = line.strip()
            # 剥 code fence
            if line.startswith("```"):
                continue
            if _buf is not None:
                # 引号不闭合 → 命令跨行, 续拼 (LLM 偶发违约的防御)
                _buf += " " + line
                if _buf.count('"') % 2 == 0:
                    commands.append(_buf)
                    _buf = None
                continue
            if line.startswith("RUN|"):
                cmd = line[4:].strip()
                if not cmd:
                    continue
                # 奇数个双引号 = 命令未完, 进入续行模式
                if cmd.count('"') % 2 == 1:
                    _buf = cmd
                else:
                    commands.append(cmd)
            elif line.startswith("NONE|"):
                logger.info("GoalDirectExecutor: LLM 判定不可执行: %s", line[5:].strip())
                return []
        if _buf is not None:
            # 尾部悬空引号 — 诚实丢弃并告警, 不执行残缺命令
            logger.warning("GoalDirectExecutor: 丢弃引号不闭合的残缺命令: %s",
                           _buf[:120])
        return commands[:MAX_COMMANDS]

    def _llm_available(self) -> bool:
        return bool(self._bridge._llm_available())

    # ── 执行 ──────────────────────────────────────────────────────

    def execute_command(self, command: str) -> ExecResult:
        """单条命令经沙盒执行 (strict, 白名单闸门)。"""
        from types import SimpleNamespace
        res = ExecResult(command=command)
        result = self._bridge._handler_run_command(
            SimpleNamespace(payload={"command": command}))
        res.ok = bool(result.get("ok"))
        res.blocked = bool(result.get("blocked"))
        res.stdout = result.get("stdout", "")
        res.stderr = result.get("stderr", "")
        res.exit_code = int(result.get("exit_code", -1))
        res.block_reason = result.get("block_reason", "") or result.get("error", "")
        return res

    def execute_goal(self, goal_text: str,
                     fallback_single: bool = True) -> GoalExecReport:
        """完整流程: 分解 → 逐条执行 → 汇总。

        fallback_single: LLM 分解失败时, 尝试把整段描述作为单命令
        (兼容 chat 路径 UX-I 语义) — 仍经沙盒裁决。
        """
        report = GoalExecReport(goal_text=goal_text)

        commands = self.decompose(goal_text)
        if not commands and fallback_single:
            logger.info("GoalDirectExecutor: 分解为空 → 单命令回退")
            commands = [goal_text]

        for cmd in commands:
            r = self.execute_command(cmd)
            report.commands.append(r)

        ok_count = sum(1 for c in report.commands if c.ok)
        blocked_count = sum(1 for c in report.commands if c.blocked)
        report.finished_at = datetime.now(timezone.utc).isoformat()
        report.summary = (
            f"{ok_count}/{len(report.commands)} 命令成功"
            + (f", {blocked_count} 被沙盒拦截" if blocked_count else ""))
        return report

    # ── 落库 (可选) ───────────────────────────────────────────────

    def persist_result(self, goal_id: str, report: GoalExecReport) -> None:
        """把执行摘要写回 goal.result_json (goal 存在时)。"""
        try:
            db_path = os.environ.get("OCOS_DB_PATH",
                                     os.path.expanduser("~/.ocos/ocos.db"))
            import sqlite3
            con = sqlite3.connect(db_path)
            con.execute(
                "UPDATE goal SET status='COMPLETED', result_json=? WHERE goal_id=?",
                (json.dumps(report.to_dict(), ensure_ascii=False)[:4000], goal_id))
            con.commit()
            con.close()
        except Exception as e:
            logger.warning("GoalDirectExecutor: persist failed: %s", e)
