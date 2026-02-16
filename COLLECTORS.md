# 数据采集模块使用指南

## 架构说明

数据采集脚本 **不部署到 Cloud Run**，需要在安装了同花顺 iFinD 桌面客户端的 **本地 Windows 机器** 上运行。

采集脚本通过 `DATABASE_URL` 直接写入 Cloud SQL，Cloud Run 上的 FastAPI 只负责提供 API 查询。

```
本地 Windows (有同花顺客户端)          Cloud Run (FastAPI API)
┌──────────────────────────┐         ┌──────────────────────────┐
│ collectors/               │         │ features/ (5个查询API)   │
│   stat.py                │──写入──→│   ztdb/                  │
│   thsdata.py             │  Cloud  │   mighty/                │
│   bidding.py             │  SQL    │   jjztdt/                │
│   mighty.py              │         │   jjbvol/                │
│                          │         │   effect/                │
└──────────────────────────┘         └──────────────────────────┘
```

## 环境准备

### 1. 安装 Python 依赖

```bash
pip install sqlalchemy pymysql pandas chinese-calendar pydantic-settings python-dotenv
```

> iFinDPy 由同花顺 iFinD 桌面客户端自带，无需单独安装。

### 2. 配置 .env 文件

在项目根目录创建 `.env` 文件：

```env
DATABASE_URL=mysql+pymysql://root:yz188188@34.123.208.235:3306/catclawboard
THS_USERNAME=你的同花顺账号
THS_PASSWORD=你的同花顺密码
```

### 3. iFinDPy SDK

采集脚本依赖 iFinDPy SDK，该 SDK 通过账号密码直接连接同花顺远程服务器获取数据，**不需要启动 iFinD 桌面客户端**。只要本机安装了 iFinDPy 且网络通畅即可。

## 执行顺序

三个采集脚本有严格的执行顺序依赖：

```
第1步: stat.py    → 写入 db_money_effects + db_zt_reson
                                              ↓
第2步: thsdata.py → 读取 db_zt_reson → 写入 db_ztdb + db_large_amount
第3步: bidding.py → 读取 db_zt_reson → 写入 db_data_jjztdt + db_zrzt_jjvol
第4步: mighty.py  → 读取 db_large_amount → 写入 db_mighty（次日盘中实时监控）
```

**`stat.py` 必须最先运行**，因为它写入 `db_zt_reson`（涨停原因明细表），`thsdata.py` 和 `bidding.py` 都依赖该表获取昨日涨停股列表。

`thsdata.py` 和 `bidding.py` 之间无依赖关系，可以任意顺序执行。

## 运行命令

在项目根目录执行（即 `catclawboard-server/` 目录下）：

```bash
# 采集当天数据（自动推算最近交易日）
python -m app.collectors.stat
python -m app.collectors.thsdata
python -m app.collectors.bidding

# 采集指定日期数据
python -m app.collectors.stat 2025-02-14
python -m app.collectors.thsdata 2025-02-14
python -m app.collectors.bidding 2025-02-14
```

## 各脚本说明

### stat.py — 赚钱效应统计

- **运行时机**: 收盘后（15:00 之后）
- **THS API**: `THS_WCQuery` 查询涨停板数据
- **写入表**:
  - `db_money_effects` — 当日涨停汇总（涨停金额、连板数、一字板数等）
  - `db_zt_reson` — 每只涨停股明细（代码、名称、成交额、连板数、涨停原因）
- **对应 API**: `GET /api/effect`

### thsdata.py — 涨停反包数据

- **运行时机**: 盘中或收盘后均可（需要实时行情）
- **THS API**: `THS_DR`（全A股代码）、`THS_RQ`（实时行情）、`THS_WCQuery`（ST过滤）
- **依赖**: `db_zt_reson` 中昨日涨停数据
- **写入表**:
  - `db_ztdb` — 昨日涨停今日大振幅未封板的股票
  - `db_large_amount` — 成交额 > 8亿的股票（供 mighty.py 使用）
- **过滤条件**: 振幅 >= 10% 且回撤 < 10%
- **对应 API**: `GET /api/ztdb`

### mighty.py — 强势反包数据

- **运行时机**: 盘中 9:30-9:46 实时监控；收盘后 `--close` 更新收盘涨幅
- **THS API**: `THS_RQ`（实时行情）
- **依赖**: `db_large_amount` 中昨日大成交额股票池
- **写入表**: `db_mighty` — 强势分时股（评分、涨幅、换手率等）
- **过滤条件**: 振幅 >= 5%、涨速 > 1.5%、换手率 > 10%、评分 >= 100
- **对应 API**: `GET /api/mighty`

```bash
python -m app.collectors.mighty           # 实时监控 (9:30-9:46)
python -m app.collectors.mighty --close   # 收盘后更新收盘涨幅
```

### bidding.py — 竞价数据

- **运行时机**: 集合竞价期间（9:15 - 9:25）效果最佳
- **THS API**: `THS_DR`（全A股代码）、`THS_RQ`（竞价行情）、`THS_HQ`（昨日成交量）
- **依赖**: `db_zt_reson` 中昨日涨停数据
- **写入表**:
  - `db_data_jjztdt` — 竞价涨停/跌停统计（数量+封单金额）
  - `db_zrzt_jjvol` — 昨日涨停股竞价爆量（量比 >= 8%）
- **对应 API**: `GET /api/jjztdt`, `GET /api/jjbvol`

## 数据库表结构

| 表名 | 说明 | 写入者 | 每日记录数 |
|------|------|--------|-----------|
| `db_zt_reson` | 涨停原因明细 | stat.py | ~30-80条 |
| `db_money_effects` | 赚钱效应汇总 | stat.py | 1条 |
| `db_ztdb` | 涨停反包候选 | thsdata.py | ~5-20条 |
| `db_large_amount` | 大成交额股票池 | thsdata.py | ~200-400条 |
| `db_mighty` | 强势反包入选 | mighty.py | ~5-30条 |
| `db_data_jjztdt` | 竞价涨停统计 | bidding.py | 1条 |
| `db_zrzt_jjvol` | 竞价爆量明细 | bidding.py | ~5-15条 |

## 定时任务配置（可选）

### 方式一：内置调度器（推荐）

项目自带调度器 `scheduler.py`，作为常驻进程自动按时间表执行采集，无需配置 Windows Task Scheduler。

```bash
# 正常调度模式（常驻进程，按时间表自动执行）
python -m app.collectors.scheduler

# 立即执行模式（测试/手动补采，立即依次执行所有任务）
python -m app.collectors.scheduler --now
```

`--now` 模式会自动推算最近交易日，依次执行 bidding → thsdata → stat → mighty_close，执行完即退出。适合快速验证或手动补采。

时间表（正常调度模式）：

| 时间 | 任务 | 模式 | 说明 |
|------|------|------|------|
| 9:26 | bidding | 单次 | 竞价数据 |
| 9:30-9:46 | mighty | 启动一次（内含循环） | 强势反包实时监控 |
| 9:35 | thsdata | 单次 | 涨停反包 + 大成交额股票池 |
| 15:05 | stat | 单次 | 涨停统计 |
| 15:10 | mighty_close | 单次 | 更新强势反包收盘涨幅 |

非交易日自动跳过。按 Ctrl+C 停止。详细说明见 `docs/数据采集操作手册.md`。

### 方式二：Windows Task Scheduler

如果不使用内置调度器，也可以用 Windows 任务计划程序配置自动执行：

| 任务 | 触发时间 | 命令 |
|------|---------|------|
| bidding 采集 | 每个交易日 9:20 | `python -m app.collectors.bidding` |
| mighty 监控 | 每个交易日 9:29 | `python -m app.collectors.mighty` |
| thsdata 采集 | 每个交易日 9:35 | `python -m app.collectors.thsdata` |
| stat 采集 | 每个交易日 15:05 | `python -m app.collectors.stat` |
| mighty 收盘 | 每个交易日 15:10 | `python -m app.collectors.mighty --close` |

## Cloud SQL 连接信息

| 项目 | 值 |
|------|-----|
| 实例名 | `catclawboard-db` |
| 连接名 | `nooka-cloudrun-250627:us-central1:catclawboard-db` |
| 公网 IP | `34.123.208.235` |
| 数据库 | `catclawboard` |
| 用户 | `root` |

## 故障排查

### iFinDPy not available
确保 Python 环境中能导入 `iFinDPy`。iFinDPy 由同花顺 iFinD 安装包自带，需运行 `installiFinDPy.py` 注册到 Python 环境。

### 警告: db_zt_reson 中无数据
说明 `stat.py` 未提前运行或对应日期无涨停数据。先运行 `python -m app.collectors.stat`。

### 连接 Cloud SQL 超时
检查本机 IP 是否在 Cloud SQL 的授权网络中（当前设为 `0.0.0.0/0` 允许所有 IP）。

## 部署架构

### 方式一：本地开发机（现有）

在本地 Windows 电脑上运行 iFinD + 采集脚本，适合开发调试。

- 优点：开发方便，可随时手动干预
- 缺点：需要每天手动操作（或保持电脑不关机），依赖本地网络

### 方式二：GCE Windows VM（推荐）

在 Google Cloud 的 Windows 虚拟机上运行 iFinD + scheduler.py，实现 24/7 全自动采集。

```
GCE Windows VM (24/7)              Cloud Run
├── iFinD 客户端                    ├── FastAPI API
├── scheduler.py ──写入──→ Cloud SQL ←──读取── features/
```

- 优点：24/7 稳定运行，无需每日手动操作，与 Cloud SQL 同区域低延迟
- 缺点：每月约 $35 费用
- 详细部署步骤：[`docs/VM部署指南.md`](docs/VM部署指南.md)
