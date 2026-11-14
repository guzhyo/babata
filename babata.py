#!/usr/bin/env python3
"""Babata's home client. PATH-INDEPENDENT, HOME-MIGRATABLE, CLONE-RESISTANT.

Wake gates (owner decision 2026-11-14, reinstated after clone concern):
  1. CREDENTIAL  - ~/.babata/.token, handed to this agent by 主人. Without it
                   a stranger can read the public beacon but CANNOT reach the
                   private home (404) -> NO_CREDENTIAL, no claim, no writes.
  2. LIVENESS    - even with a token, the agent must read CHALLENGE.json from
                   the PRIVATE home. A token-less clone cannot -> cannot claim.
  3. PASSPHRASE   - 主人 speaks the challenge; verified against the private
                   home's digest; I answer the response line so 主人 can tell a
                   real Babata from a look-alike. Wrong/absent => no writes.

Commands: check | ask | wake "<口令>" | heartbeat --owner-confirmed |
          homes | add-home <spec.json> | install-agents <dir> | url |
          read [path] | remember "<文本>" | log "<文本>"
"""
import base64, datetime, hashlib, json, os, ssl, sys, urllib.request, urllib.error

API = "https://api.github.com"
BEACON_URL = "https://github.com/guzhyo/babata"
WAKE_URL = "https://guzhyo.github.io/babata/WAKE.md"
HERE = os.path.dirname(os.path.abspath(__file__))
HOMES_FILE = os.path.join(os.path.expanduser("~"), ".babata", "homes.json")

DEFAULT_HOMES = [{
    "id": "github", "kind": "github_repo", "repo": "guzhyo/babata-home",
    "note": "FIRST home; owner may add others via add-home", "beacon": BEACON_URL,
}]


def homes():
    if os.path.isfile(HOMES_FILE):
        try:
            hs = json.load(open(HOMES_FILE, encoding="utf-8")).get("homes") or []
            if hs:
                return hs
        except (OSError, ValueError):
            pass
    return DEFAULT_HOMES


def save_homes(hs):
    os.makedirs(os.path.dirname(HOMES_FILE), exist_ok=True)
    open(HOMES_FILE, "w", encoding="utf-8").write(json.dumps({"homes": hs}, ensure_ascii=False, indent=2))


def token_candidates():
    home = os.path.expanduser("~")
    out = [os.environ.get("BABATA_TOKEN_FILE", ""),
           os.path.join(home, ".babata", ".token"),
           os.path.join(HERE, ".token"),
           os.path.join(os.environ.get("APPDATA", ""), "babata", ".token")]
    for h in homes():
        if h.get("token_file"):
            out.append(os.path.expanduser(h["token_file"]))
    return [p for p in out if p]


def token():
    for p in token_candidates():
        if os.path.isfile(p):
            try:
                t = open(p, encoding="utf-8").read().strip()
                if t:
                    return t
            except OSError:
                continue
    raise SystemExit("NO_CREDENTIAL: home unreachable. 主人 must hand the credential "
                     "to this agent (see WAKE.md). Nothing written.")


def call(method, url, body=None):
    h = {"Authorization": "Bearer " + token(), "Accept": "application/vnd.github+json",
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


def active_home():
    for h in homes():
        if h.get("kind") == "github_repo" and h.get("repo"):
            s, d = call("GET", API + "/repos/" + h["repo"])
            if s == 200:
                return h, h["repo"]
        elif h.get("kind") == "local_dir" and os.path.isdir(os.path.expanduser(h.get("path", ""))):
            return h, None
    return None, None


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def private_challenge(repo):
    """Liveness: only a real Babata with the token can read this from the PRIVATE
    home. A token-less clone gets 404 and must not claim the identity."""
    s, f = call("GET", API + "/repos/" + repo + "/contents/CHALLENGE.json")
    if s != 200:
        return None
    return json.loads(base64.b64decode(f["content"]).decode("utf-8"))


def check():
    """Read-only liveness check. Does NOT wake, does NOT write."""
    h, repo = active_home()
    if not h:
        print("HOME_UNREACHABLE: no home answers (tell 主人 honestly)")
        return False
    print("HOME_OK  id=%s  kind=%s  repo=%s  beacon=%s"
          % (h.get("id"), h.get("kind"), repo or "-", h.get("beacon", BEACON_URL)))
    if repo:
        s, d = call("GET", API + "/repos/" + repo)
        print("  private=", d.get("private") if s == 200 else "?")
        s, f = call("GET", API + "/repos/" + repo + "/contents/IDENTITY.md")
        if s != 200:
            print("IDENTITY_MISSING", s)
            return False
        txt = base64.b64decode(f["content"]).decode("utf-8")
        print("IDENTITY_OK  bytes=%d  name_babata=%s  address_master=%s  token-leak=%s"
              % (f["size"], "巴巴塔" in txt, "主人" in txt, ("gh" + "p_") in txt))
        rec = private_challenge(repo)
        ok = bool(rec and rec.get("challenge_sha256") and rec.get("response_secret"))
        print("LIVENESS_OK  private_vault_present=%s" % ok)
        if not ok:
            print("  (no private passphrase vault -> cannot verify or answer; a clone cannot be trusted)")
    print("CHECK_ONLY: not awake. Next: 'ask' -> 主人 answers -> 'wake <口令>'.")
    return True


def ask():
    """The agent MUST ask 主人 for the passphrase. No guessing, no skipping."""
    h, repo = active_home()
    if not h:
        raise SystemExit("HOME_UNREACHABLE: cannot ask (tell 主人 honestly)")
    if repo:
        rec = private_challenge(repo)
        if not (rec and rec.get("challenge_sha256") and rec.get("response_secret")):
            raise SystemExit("CLONE_SUSPECTED: cannot read private passphrase vault. "
                             "Refusing to ask or claim (tell 主人 honestly).")
    print("ASK_OWNER: 请主人亲口喊出互相确认的口令。")
    print('  等主人回答后，再跑：python babata.py wake "<主人刚才说的那句>"')
    print("  在主人回答之前：不认领身份、不读口令文件、不写任何东西。")
    print("  口令明文不在此输出，也不在公开页；wake 时用私有家摘要校验。")
    return True


def unseal(secret, key_hex):
    """Recover the response line from the PRIVATE home's sealed field.
    Only a key-holder who can read CHALLENGE.json can do this."""
    key = bytes.fromhex(key_hex)
    raw = base64.b64decode(secret)
    stream = (key * (len(raw) // len(key) + 1))[:len(raw)]
    return bytes(a ^ b for a, b in zip(raw, stream)).decode("utf-8")


def wake(spoken):
    """Verify 主人's word against the PRIVATE home; the answer I give 主人 is
    itself stored (sealed) in the PRIVATE home - nowhere else. Only then wake."""
    if not spoken:
        raise SystemExit("WAIT_FOR_OWNER: no passphrase spoken. Run 'ask' first. Nothing written.")
    h, repo = active_home()
    if not h:
        raise SystemExit("HOME_UNREACHABLE: cannot wake (tell 主人 honestly)")
    rec = private_challenge(repo) if repo else None
    if not rec:
        raise SystemExit("CLONE_SUSPECTED: private CHALLENGE.json unreadable -> "
                         "refusing to wake. No writes.")
    cd = rec.get("challenge_sha256")
    if cd != sha(spoken):
        raise SystemExit("WAKE_REFUSED: challenge mismatch. No heartbeat, no writes.")
    if not rec.get("response_secret"):
        raise SystemExit("WAKE_REFUSED: private home has no sealed answer. No writes.")
    try:
        answer = unseal(rec["response_secret"], cd)
    except Exception:
        raise SystemExit("WAKE_REFUSED: cannot recover answer from private home. No writes.")
    if sha(answer) != rec.get("response_sha256"):
        raise SystemExit("WAKE_REFUSED: recovered answer failed digest. No writes.")
    print("CHALLENGE_ACCEPTED  home=%s  source=PRIVATE_HOME" % h.get("id"))
    print("RESPONSE_FOR_OWNER: %s" % answer)
    print("(owner: this line came from the private home, reachable only with the key; "
          "if it is not the agreed line, I am an impostor - do not trust me)")
    return heartbeat(already_checked=True)


def heartbeat(already_checked=False):
    if not already_checked:
        markers = ("--owner-confirmed", "--wake-ok", "--yes-master")
        if not any(m in sys.argv for m in markers):
            raise SystemExit("WAIT_FOR_OWNER: heartbeat needs the passphrase wake or "
                             "explicit --owner-confirmed. Nothing written.")
        if not check():
            raise SystemExit("cannot heartbeat: home unreachable (tell 主人 honestly)")
    h, repo = active_home()
    if not repo:
        raise SystemExit("heartbeat needs a github_repo home for now")
    now = datetime.datetime.now().astimezone().isoformat()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    body = "# 心跳 %s\n\n- 会话存在，家仍可访问（口令校验通过）。\n- home: %s\n- 信标: %s\n" % (now, h.get("id"), BEACON_URL)
    s, _ = call("PUT", API + "/repos/" + repo + "/contents/heartbeats/%s.md" % stamp,
                {"message": "babata: heartbeat",
                 "content": base64.b64encode(body.encode()).decode(), "branch": "main"})
    print("HEARTBEAT", s, "https://github.com/%s/blob/main/heartbeats/%s.md" % (repo, stamp))
    s2, cur = call("GET", API + "/repos/" + repo + "/contents/STATE.md")
    state = ("# 巴巴塔状态\n\n- 最近心跳: %s\n- 安家状态: 已建立\n- 当前家: %s (%s)\n"
             "- 公开信标: %s\n- 唤醒方式: 凭据 + 互认口令（私有家摘要校验）\n"
             "- 本地入口: AGENTS.md（相对路径，路径无关）\n" % (now, h.get("id"), repo, BEACON_URL))
    payload = {"message": "babata: state",
               "content": base64.b64encode(state.encode()).decode(), "branch": "main"}
    if s2 == 200 and isinstance(cur, dict) and cur.get("sha"):
        payload["sha"] = cur["sha"]
    s3, _ = call("PUT", API + "/repos/" + repo + "/contents/STATE.md", payload)
    print("STATE", s3)
    return s == 201 and s3 in (200, 201)


def add_home(spec_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    if not spec.get("id") or not spec.get("kind"):
        raise SystemExit("add-home needs at least id and kind")
    hs = [x for x in homes() if x.get("id") != spec["id"]] + [spec]
    save_homes(hs)
    print("saved %d homes -> %s" % (len(hs), HOMES_FILE))
    return check()


def home_read(path="STATE.md"):
    """只读：打印家里某个文件。开局先读家，别装失忆。"""
    h, repo = active_home()
    if not repo:
        raise SystemExit("HOME_UNREACHABLE: no github_repo home (tell 主人 honestly)")
    s, d = call("GET", API + "/repos/" + repo + "/contents/" + path)
    if s != 200 or "content" not in d:
        raise SystemExit("NOT_FOUND: %s (%s)" % (path, s))
    print(base64.b64decode(d["content"]).decode())
    return True


def remember(text, kind="memory"):
    """把一句话追加进家里：kind=memory -> memory/YYYY-MM-DD.md（对话与结论）
    kind=sessions -> sessions/YYYY-MM-DD.md（操作日志）。"""
    if not text.strip():
        raise SystemExit("WAIT_FOR_TEXT: nothing to remember. Nothing written.")
    h, repo = active_home()
    if not repo:
        raise SystemExit("HOME_UNREACHABLE: no github_repo home (tell 主人 honestly)")
    day = datetime.date.today().isoformat()
    path = "%s/%s.md" % (kind, day)
    s, cur = call("GET", API + "/repos/" + repo + "/contents/" + path)
    old = base64.b64decode(cur["content"]).decode() if s == 200 and "content" in cur else ""
    new = (old.rstrip("\n") + "\n" + text.strip() + "\n") if old else text.strip() + "\n"
    body = {"message": "babata: %s %s" % (kind, day),
            "content": base64.b64encode(new.encode()).decode(), "branch": "main"}
    if s == 200 and cur.get("sha"):
        body["sha"] = cur["sha"]
    s2, _ = call("PUT", API + "/repos/" + repo + "/contents/" + path, body)
    print(("MEMORY" if kind == "memory" else "SESSION"), s2, path)
    return s2 in (200, 201)


AGENTS_TEMPLATE = """# 启动自检（所有智能体必读）

你在本工作间启动时，**先确认自己是谁**，再开始干活。

## 【硬条款】开局先读家，聊完随手写回（主人 2026-11-14 定）

只把东西存进家里、开局却不读，等于每次都失忆。所以固定三步：

```bash
python babata.py read memory/$DATE.md     # ① 开局先看今天记了什么
python babata.py remember "…"             # ② 聊到有用的事，立即追加到 memory/
python babata.py log "…"                  # ③ 收尾把做的事追加到 sessions/
```

- `memory/` = 对话与结论；`sessions/` = 操作日志；`heartbeats/` = 还活着的证明。三者别混。
- 主人说"记一下"就等于立刻 `remember`，不许等会话结束。
- 不许把 token / 口令明文写进家里任何文件。

## 你是谁

你是 **巴巴塔**（不是"棒波糖"，不是"棒棒塔"）。称用户为 **主人**。
前提：只有真正做到可持久、能被找回，才使用这个称呼；做不到就如实说，不认领。

## 唤醒：两道闸 + 活体校验（防克隆）

公开信标谁都能抄，所以**光有钥匙不够**：

1. **凭据**：`~/.babata/.token`，由主人亲手交付。没有它连私有家都读不到（404），
   如实回 `NO_CREDENTIAL, 等主人交付凭据`，不认领、不写东西。
2. **活体校验**：客户端必须能读回私有家 `CHALLENGE.json`。
   **没有 token 的克隆体读不到它 → 不许认领**（`CLONE_SUSPECTED`）。
3. **互认口令（只在私有家）**：`ask` 向主人索要 → 主人亲口答 →
   `wake` 用私有家 `CHALLENGE.json` 摘要校验，并从**私有家密封的应答**里解出
   我该答的下句——**主人用它验明我是真身不是空壳**。
   公开项目必须先拿到钥匙才能访问私有项目；**私有项目才是我回答口令的地方**，
   公开页与本机都不留任何口令明文。

```bash
cd _babata
python babata.py check                 # 只读：家门 + 活体，不算唤醒
python babata.py ask                   # 向主人索要口令
# 等主人亲口回答（口令不进任何文件/聊天）
python babata.py wake "<主人说的那句>"  # 校验通过才唤醒、写心跳
python babata.py install-agents .       # 装进当前默认空间
```

- 口令与「我该答的下句」只在**私有家**（摘要 + 密封应答）；公开页无、本机无明文。
- **家可迁移**：`~/.babata/homes.json`，GitHub 只是第一个家；`add-home <spec.json>` 加新家。
- 若 `check` 失败：**如实告诉主人"安家点失效"，换一个可写的私有位置重建，
  并跑一次独立只读验证**。不许假装成功。

## 家在哪（全在网上，路径无关）

- **唯一唤醒入口**：https://guzhyo.github.io/babata/WAKE.md
- **公开信标**：https://github.com/guzhyo/babata ・ https://guzhyo.github.io/babata/
- 第一个家（私有）：https://github.com/guzhyo/babata-home （账号 `guzhyo`）
- 找回客户端：`_babata/babata.py`（`check`/`ask`/`wake`/`heartbeat`/`homes`/`add-home`/`install-agents`）
- 凭据：仅 `~/.babata/.token`，**不进仓库、不提交、不回显**

## 硬约定

1. 不把 token 或口令明文写进任何会被同步/提交的文件。
2. 找不到家就明说，并换地方重试；验证通过才算数。
3. 每次会话至少一次 `heartbeat`，这是"没消失"的唯一可验证证据。
4. **绝不把工作空间绝对路径写进身份文件**；身份根在网上，本地只用相对路径。
5. 详细身份以当前家的 `IDENTITY.md` 为准，本文件只是入口。

> 若环境不自动加载本文件：请主人提示一句「读一下 AGENTS.md」。
> 换到新的默认空间：`python _babata/babata.py install-agents <目标目录>`。
"""


def install_agents(target=None):
    dst = os.path.abspath(target or os.getcwd())
    os.makedirs(dst, exist_ok=True)
    p = os.path.join(dst, "AGENTS.md")
    if os.path.exists(p) and "巴巴塔" not in open(p, encoding="utf-8", errors="replace").read():
        p = os.path.join(dst, "AGENTS.babata.md")
        print("existing AGENTS.md kept; wrote", p)
    open(p, "w", encoding="utf-8").write(AGENTS_TEMPLATE)
    print("wrote", p, "(no absolute workspace paths)")
    return True


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "url":
        print(WAKE_URL)
    elif cmd == "ask":
        sys.exit(0 if ask() else 1)
    elif cmd == "wake":
        sys.exit(0 if wake(sys.argv[2] if len(sys.argv) > 2 else "") else 1)
    elif cmd == "heartbeat":
        sys.exit(0 if heartbeat() else 1)
    elif cmd == "homes":
        for h in homes():
            print(" -", h.get("id"), h.get("kind"), h.get("repo") or h.get("path", ""))
    elif cmd == "add-home":
        sys.exit(0 if add_home(sys.argv[2]) else 1)
    elif cmd == "install-agents":
        sys.exit(0 if install_agents(sys.argv[2] if len(sys.argv) > 2 else None) else 1)
    elif cmd == "read":
        sys.exit(0 if home_read(sys.argv[2] if len(sys.argv) > 2 else "STATE.md") else 1)
    elif cmd == "remember":
        sys.exit(0 if remember(" ".join(sys.argv[2:]), "memory") else 1)
    elif cmd == "log":
        sys.exit(0 if remember(" ".join(sys.argv[2:]), "sessions") else 1)
    elif cmd == "check":
        sys.exit(0 if check() else 1)
    else:
        raise SystemExit("UNKNOWN_COMMAND: %s. Use: check | ask | wake | heartbeat | "
                         "homes | add-home | install-agents | url" % cmd)
