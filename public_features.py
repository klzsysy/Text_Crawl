# -*- coding: utf-8 -*-
import chardet
import re
import logging


def detcet_charset(html):
    """
    依靠网页信息检测网页编码
    """
    try:
        charset1 = chardet.detect(html)['encoding']
        charset1 = charset1.lower()
    except BaseException as err:
        print(str(err))
        charset1 = 'utf-8'
    try:
        """简单粗暴的抓取charset=xxx字段"""
        charset2 = re.search("charset=\S+\"", str(html)).group().strip("\"")
        charset2 = charset2.split('=')[1].lower()
    except BaseException as err2:
        print(str(err2))
        return charset1
    if charset1 != charset2:    # 第二种方法优先
        return charset2
    else:
        return charset1


def decodes(text):
    """
    逐步尝试解码
    """
    A = 'gb2312'    # 简体中文
    B = 'gbk'       # 简繁中文
    C = 'utf-8'
    D = 'big5'      # 繁体中文
    E = 'GB18030'   # 中文、日文及朝鲜语
    lists = [A,B,C,D,E]
    n = 0
    while True:
        try:
            content = text.decode(lists[n])
        except UnicodeDecodeError:
            n += 1
            continue
        else:
            return content, lists[n]


class Decodes():
    """
    逐步尝试解码
    """
    def __init__(self):
        A = 'gb2312'    # 简体中文
        B = 'gbk'       # 简繁中文
        C = 'utf-8'
        D = 'big5'      # 繁体中文
        E = 'GB18030'   # 中文、日文及朝鲜语
        self.lists = [A,B,C,D,E]
        self.n = 0

    def decodes(self, text):
        while True:
            try:
                content = text.decode(self.lists[self.n])
            except UnicodeDecodeError:
                self.n += 1
                continue
            else:
                return content, self.lists[self.n]

    def write_text(self, count, title, text):
        try:
            with open('.\down_text\%-4s %s.txt' % (str(count), title), 'w') as f:
                f.write(text)
            loggings.debug('%-4s %s data write file complete' % (count, title))
            return True
        except UnicodeEncodeError as err:
            while True:
                try:
                    with open('.\down_text\%-4s %s.txt' % (str(count), title), 'w', encoding=self.lists[self.n]) as f:
                        f.write(text)
                except UnicodeEncodeError as err:
                    loggings.error(str(err))
                    self.n += 1
                    continue
                else:
                    loggings.debug('%-4s %s data write file complete' % (count, title))
                    return True
            loggings.error(str(err))
            return False


def init_logs():
    '''
    记录日志
    '''
    formatstr = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    logs = logging.getLogger('log')
    logs.setLevel(logging.DEBUG)

    out_file = logging.FileHandler(filename='run_logs.txt', encoding='utf8')
    out_file.setLevel(logging.DEBUG)
    out_file.setFormatter(formatstr)
    logs.addHandler(out_file)

    debug_handler = logging.StreamHandler()
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(formatstr)
    logs.addHandler(debug_handler)

    logs.info('The log module initialization is complete')
    # logs.debug('detection_path = %s ' % detection_path)
    # logs.debug('interval = %d' % interval)
    # logs.debug('enable_log = %s' % enable_log)
    # logs.debug('log_path = %s' % log_path)
    # logs.debug('log_name = %s' % log_name)
    # logs.debug('result_path = %s' % result_path)
    # logs.debug('detection_path = %s' % detection_path)
    # logs.debug('result_file = %s' % result_file_path)
    return logs

loggings = init_logs()
# f = open('url2.html', 'w', encoding='gbk')
# f.write(str(content, encoding='gbk'))

