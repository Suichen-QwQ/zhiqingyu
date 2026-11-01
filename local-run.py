# -*- coding: utf-8 -*-
"""栀情屿 本地预览启动器（Windows / macOS / Linux 通用，零依赖）。

它做三件事：
  1. 读取 backend-live/.env.local（若不存在则用 .env.local.example 生成一份模板并提示填 key）
  2. 自动选择空闲端口（默认 8092，被占用就往后试）
  3. 用 Python 标准库 http.server 起后端，静态目录指向 frontend/，数据全部落在 .local-data/

用法：
    python local-run.py                # 默认端口 8092，用 .env.local 里的真实 key
    python local-run.py --demo         # 用内置假模型，不填 key 也能把界面跑通
    python local-run.py --port 9000    # 指定端口
    python local-run.py --data D:\\tmp  # 指定数据目录

打开 http://127.0.0.1:<port>/ 即可。Ctrl+C 停止。
"""
from __future__ import print_function

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, 'backend-live')
SERVER = os.path.join(BACKEND, 'chat_server.py')
FRONTEND = os.path.join(ROOT, 'frontend')
ENV_LOCAL = os.path.join(BACKEND, '.env.local')
ENV_EXAMPLE = os.path.join(BACKEND, '.env.local.example')
DEMO_LLM = os.path.join(ROOT, 'scripts', 'demo_llm.py')


def read_env(path):
    """极简 .env 解析：KEY=VALUE，忽略 # 注释与空行，值可带引号。"""
    out = {}
    if not os.path.isfile(path):
        return out
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                v = v[1:-1]
            out[k] = v
    return out


def free_port(start, tries=20):
    for p in range(start, start + tries):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(('127.0.0.1', p))
            s.close()
            return p
        except OSError:
            s.close()
    raise SystemExit('ERROR: %d~%d 都没有空闲端口，请用 --port 指定' % (start, start + tries - 1))


def main():
    os.umask(0o077)
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=0, help='监听端口（默认 8092，被占用自动往后找）')
    ap.add_argument('--data', default='', help='数据目录（默认 .local-data/）')
    ap.add_argument('--demo', action='store_true', help='用内置假模型，不需要 key')
    args = ap.parse_args()

    if not os.path.isfile(SERVER):
        raise SystemExit('ERROR: 找不到 %s' % SERVER)

    if not os.path.isfile(ENV_LOCAL) and not args.demo:
        if os.path.isfile(ENV_EXAMPLE):
            shutil.copyfile(ENV_EXAMPLE, ENV_LOCAL)
            print('已生成 %s —— 请填入 DEEPSEEK_API_KEY 后重新运行。' % ENV_LOCAL)
            print('只想先看看界面：python local-run.py --demo（用假模型，不花钱）')
            print('')
        else:
            print('提示：没有 %s，将只使用系统环境变量。' % ENV_LOCAL)

    cfg = {} if args.demo else read_env(ENV_LOCAL)
    default_data = os.path.join(ROOT, '.local-data', 'demo') if args.demo else os.path.join(ROOT, '.local-data')
    data_dir = os.path.abspath(args.data) if args.data else default_data
    if not os.path.isdir(data_dir):
        os.makedirs(data_dir)

    port = args.port or free_port(int(cfg.get('ZQY_LISTEN_PORT') or 8092))

    env = dict(os.environ)
    env.update(cfg)                      # .env.local 优先
    env['ZQY_LISTEN_HOST'] = '127.0.0.1'
    env['ZQY_LISTEN_PORT'] = str(port)
    env['ZQY_STATIC_DIR'] = FRONTEND
    env['ZQY_MEMORY_DIR'] = os.path.join(data_dir, 'memories')
    env['ZQY_STORAGE_FILE'] = os.path.join(data_dir, 'storage', 'zqy-data.json')
    env['ZQY_SETTINGS_FILE'] = os.path.join(data_dir, 'settings.json')
    env['ZQY_RECALL_DIR'] = os.path.join(data_dir, 'recall')
    env['ZQY_TTS_CACHE_DIR'] = os.path.join(data_dir, 'tts-cache')
    env['PYTHONIOENCODING'] = 'utf-8'

    demo_proc = None
    demo_config = None
    if args.demo:
        demo_config = tempfile.TemporaryDirectory(prefix='zqy-demo-settings-')
        env['ZQY_SETTINGS_FILE'] = os.path.join(demo_config.name, 'settings.json')
        env['ZQY_DEMO'] = '1'
        env['ZQY_TTS_OFF'] = '1'
        for key in ('AZURE_SPEECH_KEY', 'AZURE_TTS_KEY', 'TAVILY_API_KEY', 'QIANFAN_API_KEY'):
            env.pop(key, None)
        demo_port = free_port(18120)
        env['DEEPSEEK_BASE_URL'] = 'http://127.0.0.1:%d/v1' % demo_port
        env['DEEPSEEK_API_KEY'] = 'sk-demo'
        env['DEEPSEEK_MODEL'] = 'demo-model'
        env['DEEPSEEK_REASONER_MODEL'] = 'demo-model'
        env['ZQY_MEMORY_V2'] = env.get('ZQY_MEMORY_V2') or '1'
        env['ZQY_MEMORY_RETRIEVE'] = env.get('ZQY_MEMORY_RETRIEVE') or 'b'
        env['ZQY_RECALL_ON'] = env.get('ZQY_RECALL_ON') or '1'
        demo_proc = subprocess.Popen([sys.executable, DEMO_LLM, str(demo_port)])
        time.sleep(0.8)
    elif not env.get('DEEPSEEK_API_KEY'):
        print('注意：DEEPSEEK_API_KEY 为空；页面仍可启动，请通过设置填写密钥。')
        print('     要看真实对话：把 key 填进 %s；或加 --demo 用假模型。' % ENV_LOCAL)

    print('=' * 62)
    print('  栀情屿 本地预览%s' % ('（假模型 demo 模式）' if args.demo else ''))
    print('  地址   http://127.0.0.1:%d/' % port)
    print('  数据   %s' % data_dir)
    print('  前端   %s' % FRONTEND)
    print('  开关   记忆v2=%s  检索=%s  共同回忆=%s' % (
        env.get('ZQY_MEMORY_V2', '0'), env.get('ZQY_MEMORY_RETRIEVE', '0'),
        env.get('ZQY_RECALL_ON', '1')))
    print('  Ctrl+C 停止')
    print('=' * 62)

    try:
        return subprocess.call([sys.executable, SERVER], cwd=BACKEND, env=env)
    except KeyboardInterrupt:
        pass
    finally:
        if demo_proc:
            try:
                demo_proc.terminate()
                demo_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                demo_proc.kill()
                demo_proc.wait()
            except OSError:
                pass
        if demo_config:
            demo_config.cleanup()


if __name__ == '__main__':
    sys.exit(main())
