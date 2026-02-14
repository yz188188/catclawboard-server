# Windows 数据采集环境搭建指南

从零开始在 Windows 虚拟机上搭建 CatClawBoard 数据采集环境的完整步骤。

---

## 前提条件

- Windows 10 1809+ 或 Windows Server 2019+
- 可访问外网（需连接 Cloud SQL 和 GitHub）
- 同花顺 iFinD 终端账号（付费机构版）

---

## 第 1 步：安装 Git for Windows

1. 下载：https://git-scm.com/downloads/win
2. 运行安装程序，全部选默认选项，一路 Next
3. 安装完成后打开 **PowerShell**，验证：

```powershell
git --version
# 应输出: git version 2.x.x
```

---

## 第 2 步：安装 Python

1. 下载 Python 3.11（推荐）：https://www.python.org/downloads/
2. 安装时 **勾选 "Add Python to PATH"**
3. 验证：

```powershell
python --version
# 应输出: Python 3.11.x

pip --version
# 应输出: pip 24.x.x
```

---

## 第 3 步：安装 Claude Code（可选，推荐）

Claude Code 可以在 Windows 上辅助调试采集脚本。

```powershell
irm https://claude.ai/install.ps1 | iex
```

安装完成后输入 `claude` 启动，按提示登录 Anthropic 账号。

---

## 第 4 步：克隆项目

```powershell
cd C:\Users\你的用户名\Desktop
git clone https://github.com/yz188188/catclawboard-server.git
cd catclawboard-server
```

---

## 第 5 步：安装 Python 依赖

```powershell
pip install sqlalchemy pymysql pandas chinese-calendar pydantic-settings python-dotenv
```

> iFinDPy 由同花顺 iFinD 桌面客户端自带，安装客户端后自动可用，无需 pip 安装。

---

## 第 6 步：安装同花顺 iFinD 客户端

1. 联系同花顺获取 iFinD 终端安装包（需机构授权）
2. 安装并登录 iFinD 客户端
3. 验证 iFinDPy SDK 可用：

```powershell
python -c "from iFinDPy import THS_iFinDLogin; print('iFinDPy OK')"
# 应输出: iFinDPy OK
```

如果报 `ModuleNotFoundError`，说明 Python 环境与 iFinD 客户端不匹配。检查：
- iFinD 客户端是否安装了 Python 插件
- Python 版本是否与 iFinD 支持的版本一致（通常为 3.8 - 3.11）
- 尝试将 iFinD 安装目录下的 `iFinDPy` 文件夹复制到 Python 的 `site-packages` 目录

---

## 第 7 步：配置环境变量

在项目根目录创建 `.env` 文件：

```powershell
cd C:\Users\你的用户名\Desktop\catclawboard-server
notepad .env
```

写入以下内容：

```env
DATABASE_URL=mysql+pymysql://root:yz188188@34.123.208.235:3306/catclawboard
THS_USERNAME=你的同花顺账号
THS_PASSWORD=你的同花顺密码
```

保存并关闭。

---

## 第 8 步：验证数据库连接

```powershell
python -c "from app.database import engine; conn = engine.connect(); print('DB connected'); conn.close()"
```

如果连接超时，检查：
- 虚拟机是否能访问外网
- 防火墙是否放行 3306 端口
- Cloud SQL 授权网络是否包含当前 IP（当前设置为 `0.0.0.0/0` 允许所有）

---

## 第 9 步：运行数据采集

确保同花顺 iFinD 客户端已启动并登录，然后在项目根目录依次执行：

```powershell
# 第1步：采集涨停数据（收盘后 15:00 之后运行）
python -m app.collectors.stat

# 第2步：采集涨停反包数据（盘中或收盘后）
python -m app.collectors.thsdata

# 第3步：采集竞价数据（集合竞价 9:15-9:25 运行）
python -m app.collectors.bidding
```

也可以指定日期采集历史数据：

```powershell
python -m app.collectors.stat 2025-02-14
python -m app.collectors.thsdata 2025-02-14
python -m app.collectors.bidding 2025-02-14
```

> **注意**：`stat.py` 必须最先运行，`thsdata.py` 和 `bidding.py` 依赖它写入的 `db_zt_reson` 表。

---

## 第 10 步：配置定时任务（可选）

使用 Windows 任务计划程序自动执行采集：

### 创建批处理脚本

在项目目录创建 `collect.bat`：

```bat
@echo off
cd /d C:\Users\你的用户名\Desktop\catclawboard-server

echo [%date% %time%] 开始采集 stat...
python -m app.collectors.stat
echo [%date% %time%] stat 完成

echo [%date% %time%] 开始采集 thsdata...
python -m app.collectors.thsdata
echo [%date% %time%] thsdata 完成

echo [%date% %time%] 采集完毕
```

竞价采集单独一个 `collect_bidding.bat`：

```bat
@echo off
cd /d C:\Users\你的用户名\Desktop\catclawboard-server

echo [%date% %time%] 开始采集 bidding...
python -m app.collectors.bidding
echo [%date% %time%] bidding 完成
```

### 配置任务计划程序

1. 打开 **任务计划程序**（搜索 "Task Scheduler"）
2. 点击 **创建基本任务**

| 任务名称 | 触发器 | 操作 |
|---------|--------|------|
| CatClaw 收盘采集 | 每天 15:30 | 运行 `collect.bat` |
| CatClaw 竞价采集 | 每天 9:20 | 运行 `collect_bidding.bat` |

> 注意：非交易日（周末、节假日）脚本会自动跳过，无需手动判断。

---

## 验证采集结果

采集完成后，通过 API 验证数据是否写入成功：

```powershell
# 先登录获取 token
$response = Invoke-RestMethod -Uri "https://catclawboard-server-765296137507.us-central1.run.app/auth/login" -Method POST -ContentType "application/json" -Body '{"username":"testuser","password":"test123456"}'
$token = $response.access_token

# 查询今日数据（替换日期）
$headers = @{ Authorization = "Bearer $token" }
Invoke-RestMethod -Uri "https://catclawboard-server-765296137507.us-central1.run.app/api/effect?date=20250214" -Headers $headers
```

---

## 常见问题

### iFinDPy 导入失败
- 确认 iFinD 客户端已安装并启动
- 确认 Python 版本与 iFinD 支持版本一致
- 将 iFinD 安装目录加入 `PYTHONPATH` 环境变量

### 采集脚本报 "iFinDPy not available"
- iFinD 客户端未启动，或未登录
- 当前 Python 环境找不到 iFinDPy 模块

### 数据库连接超时
- 检查网络是否能 ping 通 `34.123.208.235`
- 检查防火墙是否阻止 3306 端口出站
- 在 PowerShell 中测试：`Test-NetConnection 34.123.208.235 -Port 3306`

### "警告: db_zt_reson 中无数据"
- `stat.py` 未先运行，或该日期无涨停股票
- 先运行 `python -m app.collectors.stat` 再运行其他脚本

### Python 版本冲突
- 如果系统有多个 Python 版本，使用 `py -3.11` 替代 `python`
- 或创建虚拟环境：`python -m venv venv && venv\Scripts\activate`
