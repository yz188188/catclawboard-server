# CatClawBoard Server

## 语言要求
- 始终使用中文回复和交流

## 项目概述
CatClawBoard 是一个 A 股数据看板系统，包含后端 API 服务和前端 Web 应用。

## 技术栈
- **后端**: Python + FastAPI + SQLAlchemy + MySQL
- **前端**: Next.js 16 + TypeScript + Ant Design + SWR
- **认证**: JWT (Bearer Token, 24 小时过期)
- **数据库**: MySQL (utf8mb4)

## 项目结构

### 后端 (`catclawboard-server`)
```
app/
├── auth/           # 认证模块 (登录、用户管理)
│   ├── models.py       # User 模型 (含 role, password_plain)
│   ├── schemas.py      # Pydantic 请求/响应模型
│   ├── dependencies.py # 密码/JWT/权限依赖
│   └── router.py       # /auth/* 路由
├── features/       # 业务功能模块
│   ├── ztdb/           # 涨停反包
│   ├── mighty/         # 强势反包
│   ├── jjztdt/         # 竞价一字
│   ├── jjbvol/         # 竞价爆量
│   └── effect/         # 赚钱效应
├── config.py       # 配置 (环境变量)
├── database.py     # 数据库连接
└── main.py         # 应用入口 (含管理员初始化)
```

### 前端 (`catclawboard-web`)
```
src/
├── app/
│   ├── login/          # 登录页
│   └── (dashboard)/    # 需认证的页面 (AuthGuard)
│       ├── ztdb/
│       ├── jjztdt/
│       ├── jjbvol/
│       ├── effect/
│       └── users/      # 用户管理 (仅管理员)
├── components/
│   ├── Sidebar.tsx     # 侧边栏 (按角色显示菜单)
│   ├── AuthGuard.tsx   # 认证守卫
│   └── DateNavigator.tsx
├── lib/
│   ├── api.ts          # API 请求封装
│   └── auth.ts         # Token/角色管理
└── types/index.ts      # 类型定义
```

## 角色系统
- `admin`: 管理员，可管理用户（查看/创建/删除）
- `user`: 普通用户，仅可查看数据
- 管理员账号在服务启动时自动创建，可通过 `.env` 配置

## 开发命令
- 后端启动: `uvicorn app.main:app --reload --port 8080`
- 前端启动: `cd ../catclawboard-web && npm run dev`
- 前端构建: `cd ../catclawboard-web && npm run build`

## 注意事项
- 前端项目在 `../catclawboard-web`，与本仓库同级目录
- 日期格式统一使用 `YYYYMMDD` (VARCHAR(8))
- 错误信息使用中文
- 所有数据接口需要 Bearer Token 认证
