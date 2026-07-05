# 非礼勿视服务器管理系统 Windows 公网生产部署手册

## 1. 推荐方案

Windows 服务器建议这样部署：

- 后端：`Python 3.11 + venv + Uvicorn`
- 前端：`Vite build` 后的静态文件
- 数据库：`MySQL 8`
- HTTPS 与反向代理：`Caddy`
- Windows 服务托管：`NSSM`

这套组合的优点：

- 对当前项目改动最小
- Windows 上比 `nginx for Windows` 更省事
- `Caddy` 自动 HTTPS，证书管理简单
- `NSSM` 可把后端进程做成真正的 Windows 服务

## 2. 不推荐的做法

不建议直接用下面这些方式上线：

- 直接双击 `python -m uvicorn ...`
- 直接 `npm run dev` 对公网开放
- 用开发环境 SQLite 长期跑公网生产
- 继续保留演示账号和演示数据

## 3. 服务器准备

建议服务器环境：

- Windows Server 2019 / 2022
- Python 3.11+
- Node.js 20+
- MySQL 8+
- Caddy
- NSSM

建议目录结构：

```text
C:\srv\nls-admin\
  backend\
  frontend\
  data\
    uploads\
    backup\
  logs\
  caddy\
```

## 4. 上传项目

把当前项目复制到服务器，例如：

```text
C:\srv\nls-admin\backend
C:\srv\nls-admin\frontend
```

## 5. MySQL 配置

### 5.1 创建数据库

在 MySQL 中执行：

```sql
CREATE DATABASE server_admin_system DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'server_admin'@'localhost' IDENTIFIED BY '强密码';
GRANT ALL PRIVILEGES ON server_admin_system.* TO 'server_admin'@'localhost';
FLUSH PRIVILEGES;
```

如果 MySQL 和应用不在同一台机器，把 `localhost` 改成对应主机来源。

## 6. 后端部署

### 6.1 创建虚拟环境

```powershell
cd C:\srv\nls-admin\backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 6.2 生产环境变量

在 `C:\srv\nls-admin\backend\.env` 写入：

```env
ENVIRONMENT=production
DATABASE_URL=mysql+pymysql://server_admin:强密码@127.0.0.1:3306/server_admin_system
SECRET_KEY=换成足够长的随机密钥
ACCESS_TOKEN_EXPIRE_MINUTES=720
CORS_ORIGINS=https://你的前端域名
TRUSTED_HOSTS=你的前端域名,你的后端域名,127.0.0.1,localhost
ENABLE_DOCS=0
SEED_DEMO_DATA=0
BOOTSTRAP_SUPER_ADMIN_USERNAME=superadmin
BOOTSTRAP_SUPER_ADMIN_PASSWORD=换成正式超管密码
BOOTSTRAP_SUPER_ADMIN_DISPLAY_NAME=系统超管
UPLOAD_DIR=C:\srv\nls-admin\data\uploads
DEFAULT_PASS_SCORE=60
MAX_UPLOAD_SIZE_MB=50
```

说明：

- `SEED_DEMO_DATA=0` 很重要，正式环境不要灌演示数据
- `BOOTSTRAP_SUPER_ADMIN_*` 用来首次生成正式超管
- 系统超管默认是 `无部门`

### 6.3 手动测试后端

```powershell
cd C:\srv\nls-admin\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file .env
```

浏览器或 PowerShell 测试：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

正常应返回：

```json
{"status":"ok"}
```

## 7. 用 NSSM 把后端做成 Windows 服务

### 7.1 下载 NSSM

下载后解压，例如：

```text
C:\tools\nssm\win64\nssm.exe
```

### 7.2 安装服务

管理员 PowerShell 执行：

```powershell
C:\tools\nssm\win64\nssm.exe install NLSAdminBackend
```

在弹出的界面中填写：

- `Application Path`
  - `C:\srv\nls-admin\backend\.venv\Scripts\python.exe`
- `Startup Directory`
  - `C:\srv\nls-admin\backend`
- `Arguments`
  - `-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file C:\srv\nls-admin\backend\.env`

### 7.3 配置日志

NSSM 中建议设置：

- `I/O > Output`
  - `C:\srv\nls-admin\logs\backend.stdout.log`
- `I/O > Error`
  - `C:\srv\nls-admin\logs\backend.stderr.log`

### 7.4 启动服务

```powershell
sc start NLSAdminBackend
sc query NLSAdminBackend
```

## 8. 前端部署

### 8.1 安装依赖并构建

```powershell
cd C:\srv\nls-admin\frontend
npm install
npm run build
```

构建产物目录：

```text
C:\srv\nls-admin\frontend\dist
```

### 8.2 前端 API 地址

如果用同域名反代 `/api`，前端通常不用额外设置 `VITE_API_BASE_URL`。

如果你前后端分域名，可以在前端部署前设置：

```env
VITE_API_BASE_URL=https://你的后端域名
```

然后重新：

```powershell
npm run build
```

## 9. Caddy 部署

### 9.1 推荐原因

Windows 上推荐 `Caddy`，因为：

- 自动申请和续期 HTTPS
- 配置简单
- 反代和静态站一体化

### 9.2 目录

假设：

```text
C:\srv\nls-admin\caddy\Caddyfile
C:\srv\nls-admin\frontend\dist
```

### 9.3 Caddyfile 示例

```caddy
你的前端域名 {
    encode gzip

    root * C:\srv\nls-admin\frontend\dist
    file_server

    @api path /api/* /health
    reverse_proxy @api 127.0.0.1:8000

    try_files {path} /index.html
}
```

如果你前后端分域名，也可以拆成两个站点。

### 9.4 手动启动测试

```powershell
cd C:\srv\nls-admin\caddy
caddy run --config Caddyfile
```

### 9.5 做成服务

也建议用 NSSM：

```powershell
C:\tools\nssm\win64\nssm.exe install NLSAdminCaddy
```

配置：

- `Application Path`
  - `C:\path\to\caddy.exe`
- `Startup Directory`
  - `C:\srv\nls-admin\caddy`
- `Arguments`
  - `run --config C:\srv\nls-admin\caddy\Caddyfile`

启动：

```powershell
sc start NLSAdminCaddy
```

### 9.6 直接用公网 IP 访问

如果你没有域名，只能直接用公网 IP 访问，可以这样配：

- `CORS_ORIGINS=http://公网IP`
- `TRUSTED_HOSTS=公网IP,127.0.0.1,localhost`
- 前端仍然建议通过 `Caddy` 反代 `http://公网IP` 到本地后端

注意：

- `Let’s Encrypt` 一般不给裸 IP 签发证书
- 如果坚持用 IP + HTTPS，需要自签证书或企业证书
- 最稳妥是先用 `http://公网IP` 跑通，再决定是否上 HTTPS

## 10. Windows 防火墙

公网只建议开放：

- `80`
- `443`

不要对公网开放：

- `8000`
- `3306`

后端和 MySQL 应只监听本机或内网。

## 11. 首次上线检查

上线后按顺序检查：

1. 域名能否打开首页
2. HTTPS 是否正常
3. 登录是否成功
4. 超管是否显示为 `无部门`
5. 注册是否能创建 `普通玩家`
6. 超管是否能在 `人员与人事` 页面升级职位
7. 人事部是否能创建试卷
8. 选择题是否自动判分
9. 简答题是否能手动批改
10. Bug 附件上传下载是否正常

## 12. 备份方案

### 12.1 数据库备份

可以写一个 `.bat` 或 PowerShell 定时任务：

```powershell
mysqldump -u server_admin -p你的密码 server_admin_system > C:\srv\nls-admin\data\backup\server_admin_system_%date:~0,4%%date:~5,2%%date:~8,2%.sql
```

### 12.2 附件备份

备份目录：

```text
C:\srv\nls-admin\data\uploads
```

建议每天至少一次。

## 13. 升级流程

### 13.1 升级前

1. 备份数据库
2. 备份附件目录
3. 备份 `.env`

### 13.2 升级步骤

```powershell
sc stop NLSAdminCaddy
sc stop NLSAdminBackend
```

更新代码后：

```powershell
cd C:\srv\nls-admin\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

cd C:\srv\nls-admin\frontend
npm install
npm run build
```

再启动：

```powershell
sc start NLSAdminBackend
sc start NLSAdminCaddy
```

### 13.3 升级后验证

- 检查首页
- 检查登录
- 检查 `/health`
- 检查注册
- 检查试卷与工单

## 14. 回滚流程

1. 停止 `NLSAdminBackend`
2. 停止 `NLSAdminCaddy`
3. 恢复上一个代码版本
4. 恢复数据库备份
5. 恢复上传目录
6. 重新启动服务

## 15. 常见问题

### 1. 打开域名报 502

说明反代通了，但后端没起来。检查：

- `sc query NLSAdminBackend`
- `backend.stderr.log`
- `http://127.0.0.1:8000/health`

### 2. 上传失败

检查：

- `UPLOAD_DIR` 是否存在
- 服务账号是否有写权限
- 磁盘空间是否足够

### 3. 注册后为什么没有部门

正常。注册默认创建的是 `普通玩家`，部门为空。

### 4. 超管为什么没有部门

正常。系统超管设计上就是 `无部门`。

### 5. 为什么看不到 API 文档

生产环境建议：

```env
ENABLE_DOCS=0
```

所以默认关闭。

## 16. 建议的最终公网结构

```text
浏览器
  ↓ HTTPS
Caddy
  ├─ 静态前端：frontend\dist
  └─ 反代 /api → 127.0.0.1:8000
        ↓
    Uvicorn / FastAPI
        ↓
      MySQL

附件目录：
C:\srv\nls-admin\data\uploads
```

## 17. 最终建议

如果你确定走 Windows 公网生产：

- 用 `MySQL`，不要继续用 SQLite
- 用 `Caddy`，不要直接裸跑 Vite
- 用 `NSSM` 托管后端和 Caddy
- 关闭 demo 数据
- 设置正式超管账号
- 定期备份数据库和附件

## 18. 只有公网 IP 时的最简配置

如果你现在就是直接公网 IP 访问，建议最少这样：

```env
ENVIRONMENT=production
DATABASE_URL=mysql+pymysql://server_admin:强密码@127.0.0.1:3306/server_admin_system
SECRET_KEY=随机长密钥
CORS_ORIGINS=http://你的公网IP
TRUSTED_HOSTS=你的公网IP,127.0.0.1,localhost
ENABLE_DOCS=0
SEED_DEMO_DATA=0
BOOTSTRAP_SUPER_ADMIN_USERNAME=superadmin
BOOTSTRAP_SUPER_ADMIN_PASSWORD=正式超管密码
UPLOAD_DIR=C:\srv\nls-admin\data\uploads
```

前端访问方式：

- `http://你的公网IP`

后端不要直接对外开放 `8000`，仍然由 Caddy 反代到本机 `127.0.0.1:8000`。
