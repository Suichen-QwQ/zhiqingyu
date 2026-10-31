# 栀情屿 ZhiQingYu

面向日常交流的聊天应用，支持对话、记忆、日记、表情、语音及模型配置。

## 快速体验

需要 Python 3。运行内置演示模型，不需要 API 密钥：

```sh
python local-run.py --demo
```

打开终端提示的本地地址，通常为 http://127.0.0.1:8092/。Windows 也可运行 `scripts/start-local-demo.bat`。

使用真实模型时，运行 `python local-run.py`，按提示在 `backend-live/.env.local` 中填写自己的 API 密钥，再重新启动。配置文件和本地数据不会提交到 Git。

## 项目结构

- `frontend/`、`backend-live/`：当前的前后端实现。
- `prototype-frontend/`、`prototype-backend/`：Vue 和 FastAPI 原型。
- `scripts/`：本地启动和依赖安装脚本。

不要将 API 密钥、用户数据、数据库或运行环境文件提交到公开仓库。

## 部署安全

本服务面向单用户使用。公网部署必须在反向代理前启用身份验证和 HTTPS；后端默认只监听本机。`backend-live/nginx-zhiqingyu.conf` 示例要求使用 `/etc/nginx/zhiqingyu.htpasswd`，部署前请使用 `htpasswd` 创建密码文件，配置 HTTPS，再检查并重载 nginx。不要将后端端口直接暴露到公网。

模型连接测试仅在地址与已保存配置一致时复用该地址的密钥；测试新地址时须输入对应密钥。

云端同步使用版本校验，检测到其他设备修改或网络失败时会停止覆盖，保留本机内容并提示先导出备份。确认备份后，可刷新页面读取云端版本。切换到新的模型服务地址时，请同时填写该服务对应的密钥。

反向代理部署须设置 `ZQY_ALLOWED_HOSTS=你的域名`，并设置 `ZQY_TRUST_PROXY=1`（仅接受回环地址代理提供的协议头）。直接本地运行默认仅接受 localhost、127.0.0.1 和 ::1。多个域名用逗号分隔。

未同步内容按标签页独立保存，刷新原标签页会优先恢复其待同步快照；JSON 备份的 `pending_tabs` 字段同时保留其他标签页尚未同步的快照。
