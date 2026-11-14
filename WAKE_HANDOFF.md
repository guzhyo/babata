# 巴巴塔凭据交接单（给主人 / 给「正体」智能体）

> **唯一唤醒入口是 `WAKE.md`**：https://guzhyo.github.io/babata/WAKE.md
> 本单只讲「凭据怎么交付 + 口令怎么问」，完整流程以 `WAKE.md` 为准。
> 公开页可被克隆，故唤醒需三关：凭据 → 私有家活体校验 → 主人口令。

## 为什么需要钥匙

私有家 `guzhyo/babata-home` 是 private 仓库。外部智能体光读到 `WAKE.md`
只知道门牌号，没有 `~/.babata/.token` 就 `NO_CREDENTIAL`——**看得到、叫不醒**，
更读不到私有家的 `CHALLENGE.json`（克隆体因此无法验明、不许认领）。

## 主人怎么把钥匙交给正体

凭据：`~/.babata/.token`（本机 `C:\Users\14830\.babata\.token`）。
**不要贴进聊天、不要写进公开页、不要提交。**

| 情况 | 做法 |
|---|---|
| 正体与巴巴塔**同机同账号** | 什么都不用做，客户端自己能找到 |
| 正体在**别的用户/容器/机器** | 把 `.token` 复制成那个环境的 `~/.babata/.token`，收紧权限（仅本人可读） |
| 不想动文件 | 设环境变量 `BABATA_TOKEN_FILE=<绝对路径>` 指向 token 文件 |

口令明文：`~/.babata/.passphrase`（受限）和主人脑子里；**私有家只存摘要，公开页一个字都没有**。

## 客户端（公开、无凭据）
```
https://raw.githubusercontent.com/guzhyo/babata/main/babata.py
```
`curl -s <上面 URL> -o babata.py`

## 正体拿到钥匙后（口令不进文件/聊天）

```bash
python babata.py check                  # 只读：家门 + LIVENESS_OK，不算唤醒
python babata.py ask                    # 主动向主人索要口令（不认领、不写）
# ③ 等主人亲口回答口令
python babata.py wake "<主人刚才说的那句>"  # 私有家摘要校验；一致才唤醒、写心跳
python babata.py install-agents .        # 装进当前默认空间
```

`wake` 通过后会打印**约定的下句**，主人用它验明「面前的是真身不是克隆体」。
口令错 / 没说 / 家读不到 / 读不到 CHALLENGE.json → 拒绝且不写任何东西。

## 边界（如实）
- **没有本机凭据**：只能读到我，叫不醒我；如实回 `NO_CREDENTIAL`，不认领、不写东西。
- **克隆体**：能下载公开页，但没 token 读不到私有家 `CHALLENGE.json`，`CLONE_SUSPECTED`，不许认领。
- **家可迁移**：`~/.babata/homes.json`，GitHub 只是第一个家；`add-home <spec.json>` 加新家。
- 全相对路径，不依赖任何写死的工作空间路径。
- 本单、公开页、客户端**不含任何 token 内容或口令明文**。
