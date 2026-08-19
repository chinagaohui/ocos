"""OCOS CLI — organ 命令实现（S4：OpenTale 写作器官驱动）。

从 ocos 入口驱动 OpenTale：goal/意图 → Organ API action → 轮询/事件/确认。
契约基准：docs/runtime/OPENTALE_ORGAN_API_CONTRACT_20260818.md。
"""

from __future__ import annotations

from ocos.opentale_bridge.organ_client import OrganClient, OrganClientError


def cmd_organ_generate(args, session) -> int:
    """ocos organ generate "大纲" --title 书名 [--character 林澈] ..."""
    client = OrganClient(base_url=args.base_url)
    roles: dict[str, str] = {}
    genders: dict[str, str] = {}
    for r in args.role:
        if "=" in r:
            name, role = r.split("=", 1)
            roles[name.strip()] = role.strip()
    for g in getattr(args, "gender", []) or []:
        if "=" in g:
            name, gender = g.split("=", 1)
            genders[name.strip()] = gender.strip()
    try:
        resp = client.generate(
            title=args.title, content=args.content, genre=args.genre,
            chapters=args.chapters, target_words=args.target_words,
            characters=list(args.character), roles=roles, genders=genders,
            world=list(args.world),
        )
    except OrganClientError as e:
        print(f"Organ 调用失败: {e}")
        return 1
    print(f"已提交生成任务: {resp['task_id']}")
    print(f"轮询: {resp['poll']}")
    if args.wait:
        return _wait_and_report(client, resp["task_id"], session)
    return 0


def cmd_organ_resume(args, session) -> int:
    client = OrganClient(base_url=args.base_url)
    try:
        resp = client.resume(args.project, args.instruction)
    except OrganClientError as e:
        print(f"Organ 调用失败: {e}")
        return 1
    print(f"已提交续写任务: {resp['task_id']}")
    if args.wait:
        return _wait_and_report(client, resp["task_id"], session)
    return 0


def cmd_organ_rewrite(args, session) -> int:
    client = OrganClient(base_url=args.base_url)
    try:
        resp = client.rewrite(args.project, args.chapter, args.instruction)
    except OrganClientError as e:
        print(f"Organ 调用失败: {e}")
        return 1
    print(f"已提交重写任务: {resp['task_id']}（完成后进入 waiting_confirm）")
    if args.wait:
        return _wait_and_report(client, resp["task_id"], session)
    return 0


def cmd_organ_verify(args, session) -> int:
    client = OrganClient(base_url=args.base_url)
    try:
        resp = client.verify(args.project)
    except OrganClientError as e:
        print(f"Organ 调用失败: {e}")
        return 1
    print(f"已提交校验任务: {resp['task_id']}")
    if args.wait:
        return _wait_and_report(client, resp["task_id"], session)
    return 0


def cmd_organ_status(args, session) -> int:
    client = OrganClient(base_url=args.base_url)
    try:
        s = client.status()
    except OrganClientError as e:
        print(f"Organ 调用失败: {e}")
        return 1
    print("OpenTale 器官状态:")
    print(f"  LLM 启用 : {s.get('llm_enabled')}")
    print(f"  进行中任务: {s.get('tasks', {}).get('pending', 0)} / {s.get('tasks', {}).get('active', 0)}")
    print(f"  草稿总数: {s.get('drafts', {}).get('total', 0)}")
    print(f"  项目数  : {s.get('projects', 0)}")
    return 0


def cmd_organ_projects(args, session) -> int:
    client = OrganClient(base_url=args.base_url)
    try:
        items = client.projects()
    except OrganClientError as e:
        print(f"Organ 调用失败: {e}")
        return 1
    print(f"OpenTale 项目（{len(items)} 个）:")
    for p in items[:20]:
        print(f"  · {p.get('title', '?')}（{p.get('genre', '?')}）{p.get('chapters', '?')}章")
    return 0


def cmd_organ_task(args, session) -> int:
    client = OrganClient(base_url=args.base_url)
    try:
        t = client.task(args.task_id)
        if args.events:
            evs = client.events(args.task_id).get("events", [])
            print(f"任务 {args.task_id} 事件（{len(evs)} 条）:")
            for e in evs:
                print(f"  seq{e['seq']} {e['type']} {e.get('ts', '')}")
            return 0
    except OrganClientError as e:
        print(f"Organ 调用失败: {e}")
        return 1
    print(f"任务 {args.task_id}:")
    print(f"  类型   : {t.get('type')}")
    print(f"  项目   : {t.get('project')}")
    print(f"  状态   : {t.get('status')}")
    print(f"  进度   : {t.get('progress', {}).get('step')}/{t.get('progress', {}).get('total')} {t.get('progress', {}).get('label', '')}")
    if t.get("result"):
        print(f"  结果   : {t['result'][:200]}")
    if t.get("error"):
        print(f"  错误   : {t['error'][:300]}")
    return 0


def cmd_organ_accept(args, session) -> int:
    """采纳草稿（写入项目）。高风险——打印确认提示。"""
    client = OrganClient(base_url=args.base_url)
    try:
        resp = client.accept(args.task_id)
    except OrganClientError as e:
        print(f"Organ 调用失败: {e}")
        return 1
    print(f"已采纳草稿 → 任务 {resp.get('task_id')} {resp.get('status')}")
    if resp.get("written"):
        print(f"已写入: {resp['written'].get('path')}")
    return 0


def cmd_organ_reject(args, session) -> int:
    client = OrganClient(base_url=args.base_url)
    try:
        resp = client.reject(args.task_id)
    except OrganClientError as e:
        print(f"Organ 调用失败: {e}")
        return 1
    print(f"已拒绝草稿 → 任务 {resp.get('task_id')} {resp.get('status')}")
    return 0


def _wait_and_report(client: OrganClient, task_id: str, session) -> int:
    """轮询至终态并输出结果（含事件流摘要）。"""
    from ocos.opentale_bridge.organ_client import OrganTaskTimeout

    print(f"轮询任务 {task_id}（间隔 {client.poll_interval_seconds}s，"
          f"超时 {client.task_timeout_seconds / 60:.0f} 分钟）...")
    try:
        t = client.wait(task_id)
        evs = client.events(task_id).get("events", [])
    except OrganTaskTimeout as e:
        print(f"⏳ {e}")
        return 1
    except OrganClientError as e:
        print(f"轮询失败: {e}")
        return 1
    status = t.get("status")
    if status == "completed":
        print(f"✅ 完成: {t.get('result', '')[:200]}")
    elif status == "waiting_confirm":
        d = t.get("draft", {})
        print(f"⏸ 草稿待确认: 项目={d.get('project')} 章={d.get('chapter')} v{d.get('version')}")
        print(f"   采纳: ocos organ accept {task_id}   |   拒绝: ocos organ reject {task_id}")
    elif status == "failed":
        print(f"❌ 失败: {t.get('error', '')[:400]}")
    else:
        print(f"任务终态: {status}")
    if evs:
        types = [e["type"] for e in evs]
        print(f"事件流: {types}")
    return 0 if status == "completed" else 1
