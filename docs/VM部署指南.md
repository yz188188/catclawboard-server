# GCE Windows VM 部署指南

本指南说明如何在 Google Compute Engine (GCE) Windows VM 上部署 iFinD 客户端 + scheduler.py，实现 24/7 全自动数据采集。

## 目标架构

```
GCE Windows VM (24/7 常开)              Cloud Run
├── iFinD 客户端 (SuperCommand.exe)     ├── FastAPI API
├── scheduler.py 常驻进程 ──写入──→ Cloud SQL ←──读取── features/
```

VM 只负责数据采集写入，API 查询由 Cloud Run 提供，两者通过 Cloud SQL 解耦。

---

## 一、创建 GCE Windows VM

### 推荐配置

| 项目 | 推荐值 | 说明 |
|------|--------|------|
| 机型 | e2-small (2 vCPU, 2GB) | 采集任务对计算要求不高，够用 |
| 磁盘 | 50GB SSD | Windows + iFinD + Python 约占 30GB |
| 区域 | us-central1 | 与 Cloud SQL 同区域，减少网络延迟 |
| 镜像 | Windows Server 2022 Datacenter | 稳定，支持长期运行 |
| 费用 | 约 $35/月 | 含 Windows 许可 |

### 创建步骤

1. 进入 [GCE 控制台](https://console.cloud.google.com/compute/instances)
2. 点击 **创建实例**
3. 名称：`catclaw-collector`（或自定义）
4. 区域：`us-central1-a`
5. 机器类型：`e2-small`
6. 启动磁盘 → **更改** → 操作系统 `Windows Server`，版本 `Windows Server 2022 Datacenter`，大小 `50GB`
7. 防火墙：**无需**勾选 HTTP/HTTPS（VM 只需出站访问 Cloud SQL，不提供入站服务）
8. 点击 **创建**

---

## 二、通过 RDP 连接 VM

1. VM 创建完成后，在 GCE 控制台点击实例名
2. 点击 **设置 Windows 密码**，输入用户名（如 `admin`），系统会生成密码，**记下密码**
3. 在本地电脑打开 **远程桌面连接**（`mstsc`）
4. 输入 VM 的外部 IP 地址，点击连接
5. 输入刚才的用户名和密码登录

> 首次连接后建议修改为自己的密码。

---

## 三、安装环境

以下操作均在 VM 的 RDP 远程桌面中进行。

### 3.1 安装 Python 3.11

1. 打开 Edge 浏览器，下载 [Python 3.11](https://www.python.org/downloads/release/python-3110/)（Windows installer 64-bit）
2. 安装时 **勾选** "Add Python to PATH"
3. 打开 PowerShell 验证：

```powershell
python --version
# 应输出 Python 3.11.x
```

### 3.2 安装 Git 并克隆项目

1. 下载安装 [Git for Windows](https://git-scm.com/download/win)
2. 克隆项目：

```powershell
cd C:\Users\admin\Desktop
git clone https://github.com/<your-org>/catclawboard-server.git
cd catclawboard-server
```

### 3.3 安装 Python 依赖

```powershell
pip install -r requirements.txt
```

> 如果没有 `requirements.txt`，手动安装：
> ```powershell
> pip install sqlalchemy pymysql pandas chinese-calendar pydantic-settings python-dotenv
> ```

### 3.4 安装 iFinD 客户端

1. 将 iFinD 安装包（`THSDataInterface_Windows`）复制到 VM（可通过 RDP 剪贴板拖拽，或从网盘下载）
2. 安装到 `D:\THSDataInterface_Windows\`
3. 注册 iFinDPy 到 Python：

```powershell
cd D:\THSDataInterface_Windows\bin
python x64\installiFinDPy.py
```

4. 验证安装：

```powershell
python -c "import iFinDPy; print('iFinDPy OK')"
```

### 3.5 配置 .env

在项目根目录创建 `.env` 文件：

```powershell
cd C:\Users\admin\Desktop\catclawboard-server
```

`.env` 内容：

```env
DATABASE_URL=mysql+pymysql://root:yz188188@34.123.208.235:3306/catclawboard
THS_USERNAME=你的同花顺账号
THS_PASSWORD=你的同花顺密码
```

---

## 四、启动服务

### 4.1 启动 iFinD 客户端

双击 `D:\THSDataInterface_Windows\SuperCommand.exe`，等待客户端启动并登录完成。

> iFinD 客户端需要保持在前台运行，**不要关闭窗口**。

### 4.2 启动 scheduler.py

打开一个新的 PowerShell 窗口：

```powershell
cd C:\Users\admin\Desktop\catclawboard-server
python -m app.collectors.scheduler
```

调度器会自动在交易日的指定时间执行采集任务：

| 时间 | 任务 | 说明 |
|------|------|------|
| 9:26 | bidding | 竞价数据，单次 |
| 9:30 – 9:40 | thsdata | 涨停反包，连续循环 |
| 15:05 | stat | 涨停统计，单次 |

非交易日自动跳过。启动后无需任何手动操作。

### 4.3 （可选）用 NSSM 注册为 Windows 服务

如果希望 scheduler.py 在 VM 重启后自动启动，可以用 [NSSM](https://nssm.cc/) 注册为 Windows 服务：

```powershell
# 下载 nssm 后
nssm install CatClawScheduler "C:\Program Files\Python311\python.exe" "-m app.collectors.scheduler"
nssm set CatClawScheduler AppDirectory "C:\Users\admin\Desktop\catclawboard-server"
nssm start CatClawScheduler
```

> 注意：即使注册为服务，iFinD 客户端仍需手动启动（它是 GUI 程序，无法作为服务运行）。

---

## 五、运维要点

### 日常运行

- VM 24/7 常开，scheduler.py 持续运行，**正常情况下无需每天操作**
- 调度器会自动在交易日执行采集，非交易日跳过

### 定期检查

建议每周通过 RDP 检查一次：

1. iFinD 客户端是否仍在运行且已登录
2. scheduler.py 终端窗口是否有报错日志
3. 数据库中最新数据日期是否正确

### VM 重启后的恢复

如果 VM 因维护或故障重启，需要手动恢复：

1. 通过 RDP 连接 VM
2. 启动 iFinD 客户端并登录
3. 启动 scheduler.py（如已用 NSSM 注册则自动启动，但仍需手动启动 iFinD）

### 费用控制

| 项目 | 月费用（估算） |
|------|---------------|
| e2-small VM（含 Windows 许可） | ~$25 |
| 50GB SSD 磁盘 | ~$8 |
| 网络出站流量 | ~$2 |
| **合计** | **~$35/月** |

> 采集任务对 CPU 和内存的占用很低，e2-small 足以胜任。

---

## 六、故障排查

### scheduler.py 异常退出

查看 PowerShell 窗口中的错误日志。常见原因：
- iFinD 客户端未启动 → 重新打开 SuperCommand.exe
- 网络问题导致 Cloud SQL 连接失败 → 检查 VM 的网络出站规则

### iFinD 客户端掉线

iFinD 有时会自动断开登录：
- 重新打开 SuperCommand.exe 并登录
- 重启 scheduler.py

### Cloud SQL 连接超时

确保 Cloud SQL 实例的授权网络中包含 VM 的外部 IP。当前配置为 `0.0.0.0/0`（允许所有 IP），如果后续改为白名单模式，需要添加 VM 的 IP。
