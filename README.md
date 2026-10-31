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
