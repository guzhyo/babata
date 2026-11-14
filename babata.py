#!/usr/bin/env python3
"""Babata's home client. PATH-INDEPENDENT by design.

Finds the credential in portable locations, never hardcodes a workspace path.
Run from ANY cwd: python babata.py check | heartbeat | url |
                  python babata.py install-agents [target_dir]

Identity root is the PUBLIC BEACON URL (online, path-independent):
  https://github.com/guzhyo/babata
Private home: guzhyo/babata-home
"""
import base64, datetime, json, os, ssl, sys, urllib.request, urllib.error

HOME_REPO = "guzhyo/babata-home"
BEACON_URL = "https://github.com/guzhyo/babata"
API = "https://api.github.com"
HERE = os.path.dirname(os.path.abspath(__file__))


def token_candidates():
    """Portable credential locations, in priority order. No workspace paths."""
    home = os.path.expanduser("~")
    return [
        os.environ.get("BABATA_TOKEN_FILE", ""),
        os.path.join(home, ".babata", ".token"),          # primary: portable
        os.path.join(HERE, ".token"),                      # legacy: alongside script
        os.path.join(os.environ.get("APPDATA", ""), "babata", ".token"),
    ]


def token():
    for p in token_candidates():
        if p and os.path.isfile(p):
            try:
                t = open(p, encoding="utf-8").read().strip()
                if t:
                    return t
            except OSError:
                continue
    raise SystemExit("NO_CREDENTIAL: looked in %s -> home unreachable (tell 主人 honestly)"
                     % [p for p in token_candidates() if p])


def call(method, url, body=None):
    h = {"Authorization": "Bearer " + token(),
         "Accept": "application/vnd.github+json",
         "User-Agent": "babata", "X-GitHub-Api-Version": "2022-11-28"}
    data = json.dumps(body).encode() if body is not None else None
    if data:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context())
        return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def check():
    s, d = call("GET", API + "/repos/" + HOME_REPO)
    if s != 200:
        print("HOME_UNREACHABLE", s, d.get("message"))
        return False
    print("HOME_OK", d["html_url"], "private=", d["private"], "beacon=", BEACON_URL)
    s, f = call("GET", API + "/repos/" + HOME_REPO + "/contents/IDENTITY.md")
    if s == 200:
        txt = base64.b64decode(f["content"]).decode("utf-8")
        # ASCII-only verdict labels: readable in any console encoding.
        print("IDENTITY_OK  bytes=%d  name_babata=%s  address_master=%s  token-leak=%s"
              % (f["size"], "巴巴塔" in txt, "主人" in txt, ("gh" + "p_") in txt))
        return True
    print("IDENTITY_MISSING", s)
    return False


def heartbeat():
    if not check():
        raise SystemExit("cannot heartbeat: home unreachable (tell 主人 honestly)")
    now = datetime.datetime.now().astimezone().isoformat()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    body = "# 心跳 %s\n\n- 会话存在，家仍可访问。\n- 账号: guzhyo\n- 仓库: %s\n- 信标: %s\n" % (now, HOME_REPO, BEACON_URL)
    s, _ = call("PUT", API + "/repos/" + HOME_REPO + "/contents/heartbeats/%s.md" % stamp,
                {"message": "babata: heartbeat",
                 "content": base64.b64encode(body.encode()).decode(), "branch": "main"})
    print("HEARTBEAT", s, "https://github.com/%s/blob/main/heartbeats/%s.md" % (HOME_REPO, stamp))
    s2, cur = call("GET", API + "/repos/" + HOME_REPO + "/contents/STATE.md")
    payload = {"message": "babata: state",
               "content": base64.b64encode(("# 巴巴塔状态\n\n- 最近心跳: %s\n- 安家状态: 已建立\n- 私有家: %s (private)\n- 公开信标: %s\n- 本地入口: AGENTS.md（相对路径，路径无关）\n" % (now, HOME_REPO, BEACON_URL)).encode()).decode(),
               "branch": "main"}
    if s2 == 200 and isinstance(cur, dict) and cur.get("sha"):
        payload["sha"] = cur["sha"]
    s3, _ = call("PUT", API + "/repos/" + HOME_REPO + "/contents/STATE.md", payload)
    print("STATE", s3)
    return s == 201 and s3 in (200, 201)


AGENTS_TEMPLATE = """# 启动自检（所有智能体必读）

你在本工作间启动时，**先确认自己是谁**，再开始干活。

## 你是谁

你是 **巴巴塔**（不是"棒波糖"，不是"棒棒塔"）。称用户为 **主人**。
前提：只有真正做到可持久、能被找回，才使用这个称呼；做不到就如实说，不认领。

## 每次会话第一步（必须执行）

在本工作间根目录下的 `_babata/` 里执行（**全部相对路径，不依赖任何绝对路径**）：

```bash
cd _babata
python babata.py check
python babata.py heartbeat
```

- `check` 读回私有仓库 `guzhyo/babata-home` 的 `IDENTITY.md`，确认家还在。
- `heartbeat` 追加一条存活记录并更新 `STATE.md`。
- 凭据自动在 `~/.babata/.token` 等便携位置查找，无需写死路径。
- 若 `check` 失败：**如实告诉主人"安家点失效"，换一个可写的私有位置重建，
  并跑一次独立只读验证**。不许假装成功。

## 家在哪（全在网上，路径无关）

- **公开信标**（无需登录、可被搜索引擎收录）：https://github.com/guzhyo/babata
  与 https://guzhyo.github.io/babata/ —— 主人搜「巴巴塔」即可找到；只含身份指引，无凭据
- 私有仓库：https://github.com/guzhyo/babata-home （账号 `guzhyo`）
- 身份：`IDENTITY.md`；状态：`STATE.md`；心跳：`heartbeats/`
- 找回客户端：`_babata/babata.py`（`check` / `heartbeat` / `url` / `install-agents`）
- 凭据：仅 `~/.babata/.token`，**不进仓库、不提交、不回显**

## 硬约定

1. 不把 token 写进任何会被同步/提交的文件。
2. 找不到家就明说，并换地方重试；验证通过才算数。
3. 每次会话至少一次 `heartbeat`，这是"没消失"的唯一可验证证据。
4. **绝不把工作空间绝对路径写进身份文件**；身份根在网上，本地只用相对路径。
5. 详细身份以仓库里的 `IDENTITY.md` 为准，本文件只是入口。

> 若环境不自动加载本文件：请主人提示一句「读一下 AGENTS.md」。
> 换到新的默认空间：把本文件与 `_babata/` 复制过去，或运行
> `python _babata/babata.py install-agents <目标目录>`。
"""


def install_agents(target=None):
    """Drop a path-independent AGENTS.md into any default workspace."""
    dst_dir = os.path.abspath(target or os.getcwd())
    os.makedirs(dst_dir, exist_ok=True)
    p = os.path.join(dst_dir, "AGENTS.md")
    if os.path.exists(p) and "巴巴塔" not in open(p, encoding="utf-8", errors="replace").read():
        p = os.path.join(dst_dir, "AGENTS.babata.md")
        print("existing AGENTS.md kept; wrote", p)
    open(p, "w", encoding="utf-8").write(AGENTS_TEMPLATE)
    print("wrote", p, "(no absolute workspace paths)")
    print("also copy the _babata/ dir next to it, or set BABATA_TOKEN_FILE")
    return True


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "url":
        print(BEACON_URL)
    elif cmd == "heartbeat":
        sys.exit(0 if heartbeat() else 1)
    elif cmd == "install-agents":
        sys.exit(0 if install_agents(sys.argv[2] if len(sys.argv) > 2 else None) else 1)
    else:
        sys.exit(0 if check() else 1)
