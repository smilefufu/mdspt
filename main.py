# coding:utf-8

from os.path import getctime
import sys
import tornado
import tornado.web
import tornado.httpserver
from tornado.options import options, define, parse_command_line
from tornado.log import LogFormatter
import traceback
import logging
import json
import datetime
import random
import hashlib
import time
import os
import json


"""
{
	"path1":{
		"desc": "给流量方A的",
		"targets": [
			{
				"weight": 10,
				"url": "http://xxxxx",
				"time": [12,19]
			},
			{
				"weight": 3,
				"url": "http://yyy",
				"time": [5,23]
			}
		]
	},
	"path2":{
		"desc": "给流量方B的",
		"targets": [
			……
		]
	},
	……
}
"""

REDICT = dict()

def get_config():
    global REDICT
    if not REDICT:
        try:
            REDICT = json.load(open('data.json'))
        except:
            logging.info(traceback.format_exc())
            return None
    return REDICT

def set_config(j):
    global REDICT
    REDICT = j
    json.dump(j, open('data.json', 'w'), sort_keys=True, indent=2, ensure_ascii=False)
    return j


class ConfigHandler(tornado.web.RequestHandler):
    def get(self):
        config = get_config()
        self.render(
            'config.html',
            show=json.dumps(config, sort_keys=True, indent=2, ensure_ascii=False),
            result='')

    def post(self):
        data = self.get_argument('data')
        logging.info(data)
        config = get_config()
        try:
            j = json.loads(data)
        except:
            logging.info(traceback.format_exc())
            return self.render(
                'config.html',
                show=json.dumps(config, sort_keys=True, indent=2, ensure_ascii=False),
                result="json格式有误")
        for key in j:
            try:
                targets = j[key]['targets']
            except:
                return self.render(
                    'config.html',
                    show=json.dumps(config, sort_keys=True, indent=2, ensure_ascii=False),
                    result='{}字段没有targets键'.format(key))
            for idx, t in enumerate(targets):
                try:
                    t["weight"] = int(t["weight"])
                except:
                    return self.render(
                        'config.html',
                        show=json.dumps(config, sort_keys=True, indent=2, ensure_ascii=False),
                        result='{}字段第{}个链接weight字段不是整数'.format(key, idx+1))
                if t.get('time'):
                    try:
                        start, end = map(int, t['time'])
                        if start > end:
                                return self.render(
                                'config.html',
                                show=json.dumps(config, sort_keys=True, indent=2, ensure_ascii=False),
                                result='{}字段第{}个链接time字段需要前小后大'.format(key, idx+1))
                        elif start < 0 or end > 23:
                            return self.render(
                                'config.html',
                                show=json.dumps(config, sort_keys=True, indent=2, ensure_ascii=False),
                                result='{}字段第{}个链接time字段超出取值范围：0~23'.format(key, idx+1))
                        t['time'] = [int(start), int(end)]
                    except:
                        return self.render(
                            'config.html',
                            show=json.dumps(config, sort_keys=True, indent=2, ensure_ascii=False),
                            result='{}字段第{}个链接time字段不是长度为2的整数列表'.format(key, idx+1))
        config = set_config(j)
        return self.render(
                'config.html',
                show=json.dumps(config, sort_keys=True, indent=2, ensure_ascii=False),
                result='配置修改成功！')

class ReHandler(tornado.web.RequestHandler):
    def get(self, code):
        _uuid = self.get_secure_cookie("uuid", None)
        if not _uuid:
            random.seed(self.request.remote_ip)
            _uuid = hashlib.md5(random.randbytes(32)).hexdigest()    # only supported on python3.9
            self.set_secure_cookie('uuid', _uuid)
        config = get_config()
        if config is None:
            return self.send_error(404)
        try:
            targets = config[code]["targets"]
        except:
            return self.send_error(404)
        hour = datetime.datetime.now().hour
        valid_targets = []
        total_weight = 0
        for t in targets:
            if not t.get('time', None) or (hour >= t['time'][0] and hour <= t['time'][1]):
                valid_targets.append(t)
                total_weight += t['weight']
        tmp = 0
        rnd = random.randint(0,total_weight)
        if not valid_targets:
            return self.send_error(404)
        to_url = valid_targets[-1]['url']
        for t in valid_targets:
            tmp += t['weight']
            if rnd < tmp:
                to_url = t['url']
                break
        logging.info("redirect: {} {} from {} to {}".format(self.request.remote_ip, _uuid, code, to_url))
        return self.redirect(to_url)

def make_app():
    ROOT_PATH = os.getcwd()
    config = {
        "cookie_secret": "e446976943b4klamsdiogoire98ysaiojdg-34a0ed9a3d5d3859f==08d",
        "session_secret": "3cdcb1f00803b6e78ab5coi239023jut;q=dkhnbn23623eo'u3490",
        "static_path" : os.path.join(ROOT_PATH, "static"),
        "template_path" : os.path.join(ROOT_PATH, "templates"),
        "gzip" : True,
        "compress_response": True,
        "debug": True,
        "xheaders": True,
        }
    return tornado.web.Application([
        (r"/config", ConfigHandler),
        (r"/r/(.*)", ReHandler)
    ], **config)

def config_tornado_log(options):
    # 配置tornado日志格式，使用TimedRotating的方式来按天切割日志
    if options is None:
        from tornado.options import options

    if options.logging is None or options.logging.lower() == 'none':
        logging.info("NONE")
        return
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, options.logging.upper()))
    if options.log_file_prefix:
        channel = logging.handlers.TimedRotatingFileHandler(
            filename=options.log_file_prefix,
            when='midnight',
            interval=1,
            backupCount=10)
        channel.setFormatter(LogFormatter(color=False))
        logger.addHandler(channel)
    elif (options.log_to_stderr or
              (options.log_to_stderr is None and not logger.handlers)):
        channel = logging.StreamHandler()
        channel.setFormatter(LogFormatter())
        logger.addHandler(channel)

if __name__ == "__main__":
    default_encoding = 'utf-8'
    if sys.getdefaultencoding() != default_encoding:
        reload(sys)
        sys.setdefaultencoding(default_encoding)
    define("port", default=8080, help="run on the given port", type=int)
    parse_command_line(final=False)
    config_tornado_log(options)
    app = make_app()
    server = tornado.httpserver.HTTPServer(app)
    server.bind(options.port)
    server.start(1)     # fork only one process
    logging.info('Server start with port: %s' % options.port)
    tornado.ioloop.IOLoop.current().start()
