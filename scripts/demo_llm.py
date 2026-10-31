# -*- coding: utf-8 -*-
"""本地预览用的「假模型」服务（OpenAI 兼容，零依赖）。

它不联网、不花钱，只为了让 local-run.py --demo 能把整条链路跑通：
聊天、记忆抽取、共同回忆整理、上下文面板都能看到效果。

用法（一般不用手动跑，local-run.py --demo 会自动拉起）：
    python scripts/demo_llm.py 18120
"""
import hashlib
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 18120

# 演示回复：结尾带 ⟦表情|情绪|主题⟧ 标记，和后端要求的格式一致
REPLY = (u'我在呢。听起来今天挺满的，先喘口气也没关系。'
         u'要是想说的话，我就在这儿听着。⟦微笑|平静偏暖|此刻的心情⟧')

# 演示用的「事实抽取」：直接把用户这句话（去掉指令前缀）当成事实，方便本地看效果
SUMMARY = u'这段时间整体是稳的：月初有点忙，情绪起伏集中在月中，睡得偏晚；周末去看了海，回来睡得踏实多了。'
TITLE = u'{"title":"今天的碎碎念"}'
PERSONA = u'{"name":"小屿","desc":"一个安静的倾听者，话不多但总在。","rules":"语气轻缓，多用短句；先接住情绪再聊事情，不急着给建议。"}'

STRIP = [u'帮我记一下：', u'帮我记一下', u'记一下：', u'记一下', u'帮我记：', u'帮我记',
         u'记下来：', u'记下来', u'记住：', u'记住', u'别忘了：', u'别忘了', u'备忘：', u'备忘']
CATS = [(u'我妈', 'relation'), (u'我爸', 'relation'), (u'喜欢', 'pref'), (u'讨厌', 'pref'),
        (u'叫', 'identity'), (u'在广州', 'identity'), (u'考试', 'plan'), (u'打算', 'plan')]


def guess_fact(usr):
    t = (usr or u'').strip().split('\n')[0].strip()
    for p in STRIP:
        if t.startswith(p):
            t = t[len(p):].strip()
            break
    t = t.strip(u'。！？!?，,、 ')
    return t[:60] or u'用户说了点什么'


def guess_cat(fact):
    for kw, cat in CATS:
        if kw in fact:
            return cat
    return 'event'


LOCK = threading.Lock()
COUNT = {'n': 0}


class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        raw = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(n).decode('utf-8', 'replace')
        try:
            payload = json.loads(raw or '{}')
        except ValueError:
            payload = {}
        msgs = payload.get('messages') or []
        sys_txt = ''
        usr_txt = ''
        for m in msgs:
            if m.get('role') == 'system' and not sys_txt:
                sys_txt = m.get('content') or ''
            if m.get('role') == 'user':
                usr_txt = m.get('content') or ''
        blob = (sys_txt + '\n' + usr_txt)
        with LOCK:
            COUNT['n'] += 1

        # 按 system 里的独特标记判断这一轮是「聊天 / 管记忆 / 抽事实 / 起标题 / 生成人设 / 写回忆」
        if u'你是记忆库管理员' in blob:
            fact = guess_fact(usr_txt)
            content = json.dumps({'forget': [], 'update': [],
                                  'add': [{'fact': fact, 'cat': guess_cat(fact), 'imp': 3}]},
                                 ensure_ascii=False)
        elif u'你是记忆助理' in blob:
            content = json.dumps({'fact': guess_fact(usr_txt)}, ensure_ascii=False)
        elif u'你是人设设计师' in blob:
            content = PERSONA
        elif u'小标题' in blob:
            content = TITLE
        elif u'情绪陪伴者' in blob and u'现在要' in blob:
            content = SUMMARY
        else:
            content = REPLY
            # 仅当用户主动询问记忆、且本轮确实有编号记忆时演示引用；不是实际模型推理。
            question = usr_txt.split('\n', 1)[0]
            memory = re.search(r'(?m)^\[1\] [^\n]+', usr_txt)
            if memory and u'仅当回复明确使用上述某条记忆' in usr_txt and any(
                    word in question for word in (u'记得', u'记忆', u'记住')):
                line = memory.group(0)[4:].strip()
                content = u'演示：这条记忆记录写着“%s”。[1]⟦微笑|平静偏暖|此刻的心情⟧' % line

        if payload.get('stream'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'close')
            self.end_headers()
            for i in range(0, len(content), 10):
                ev = {'choices': [{'delta': {'content': content[i:i + 10]}}]}
                self.wfile.write(('data: ' + json.dumps(ev, ensure_ascii=False) + '\n\n').encode('utf-8'))
                self.wfile.flush()
            self.wfile.write(b'data: [DONE]\n\n')
            self.wfile.flush()
            return

        self._json({
            'id': 'demo-' + hashlib.md5(raw.encode('utf-8')).hexdigest()[:8],
            'object': 'chat.completion',
            'choices': [{'index': 0, 'finish_reason': 'stop',
                         'message': {'role': 'assistant', 'content': content}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30},
        })

    def do_GET(self):
        if self.path.rstrip('/').endswith('models'):
            self._json({'data': [{'id': 'demo-model', 'object': 'model'}]})
            return
        self._json({'ok': True, 'calls': COUNT['n']})


if __name__ == '__main__':
    sys.stderr.write('demo LLM (fake) listening on 127.0.0.1:%d\n' % PORT)
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
