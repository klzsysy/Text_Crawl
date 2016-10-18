# -*- coding: utf-8 -*-
import chardet
import re
import logging
import shutil
import os
import fnmatch

Down_path = 'down_text'


def text_merge(path, count):
    '''
    合并文本
    :param path: 文本目录
    '''
    with open(os.path.join(path, "fileappend.tmp"), "a", encoding='utf-8') as dest:
        loggings.debug('create merge text')
        text_merge_path = os.path.join(path, Down_path)
        for _, _, filenames in os.walk(text_merge_path):
            loggings.debug('start merge text...')
            '''文件名排序'''
            def num(s):
                return int(s[:len(str(count))])
            filenames.sort(key=num)

            for filename in fnmatch.filter(filenames, "*.txt"):
                with open(os.path.join(text_merge_path, filename), encoding='utf-8') as src:
                    shutil.copyfileobj(src, dest)
                    dest.write('\n\n')
    os.rename(os.path.join(path, "fileappend.tmp"), "text_merge.txt")
    loggings.info('merge text: %s' % os.path.join(path, 'text_merge.txt'))
    loggings.info('text merge complete!')


def url_merge(url1, url2):
    url1_segment = url1.strip('/').split('/')
    url2_segment = url2.strip('/').split('/')
    n, m, x = 0, 0, 0
    for u1 in url1_segment[1:]:
        if url1_segment[-1] == u1 and re.match('\S+\.\S{0,5}', u1):
            continue
        for u2 in url2_segment[n:]:
            if u1 == u2:
                n += 1      # 成功计数
                break
            else:
                x += 1      # 失败计数
                if n == 0:  # 成功前的失败计数
                    m += 1
                break
        '''首次成功遇到失败跳出，          首次失败成功后再次失败跳出 x-m=成功后的失败次数'''
        if (x > 0 and n > 0 and m == 0) or (x - m > 0):           # 成功匹配url2第一段
            break
    url = '/'.join(url1_segment[:m+1]) + '/' + url2.strip('/')
    return url


class analysis_title(object):
    def __init__(self, page_title, domain_title_str):
        domain_title_str = str(domain_title_str).strip()
        self.page_title_str = str(page_title).strip()
        try:
            '''尝试提取网站名'''
            self.domain_title = re.match('(\S+)[- |:]', domain_title_str).group(1)
        except BaseException:
            self.domain_title = ''
        try:
            if not self.domain_title == '':
                self.page_title_str = re.sub(self.domain_title, '', self.page_title_str)    # 去除网站名
                self.rever_page_title_str = self.page_title_str[::-1]
                self.split_str = re.match('[, -]*', self.rever_page_title_str).group()      # 取得分割符
                if not self.split_str == '':
                    self.title_sp = [x.strip() for x in self.page_title_str.split(self.split_str)]
            else:       # not website title
                self.math_text(self.page_title_str)
                self.split_str = re.match('\S+?([, -]+)', self.page_title_str).group(1)
                self.title_sp = [x.strip() for x in self.page_title_str.split(self.split_str)]
        except BaseException as err:
            loggings.error(str(err))
            self.title_sp = [x.strip() for x in self.page_title_str.split(' ')]

    def math_text(self, text):
        if re.match('^[\S]*\s[第卷][0123456789一二三四五六七八九十零〇百千两]*[章回部节集卷].*', text):
            return text
        else:
            return None

    def score(self):
        title_list = sorted(self.title_sp, key=len)
        for x in title_list:
            r_x = self.math_text(x)
            if r_x:
                return r_x
        return title_list[-1]

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
        self.lists = [A, B, C, D, E]
        self.n = 0

    # def decodes(self, text):
    #     while True:
    #         try:
    #             content = text.decode(self.lists[self.n])
    #         except UnicodeDecodeError:
    #             self.n += 1
    #             continue
    #         else:
    #             return content, self.lists[self.n]

    def write_text(self, count, title, text, page_count):
        try:
            with open('.\{}\{:<{}} {}.txt'.format(Down_path, str(count), len(str(page_count)),
                                                 title), 'w', encoding='utf-8') as f:
                f.write(text)
            loggings.debug('%-4s %s data write file complete' % (count, title))
            return True
        except UnicodeEncodeError as err:
            '''遇到编码异常尝试使用其他编码'''
            while True:
                try:
                    with open('.\{}\{:<{}} {}.txt'.format(Down_path, str(count), len(str(page_count)), title),
                              'w', encoding=self.lists[self.n]) as f:
                        f.write(text)
                except UnicodeEncodeError as err:
                    loggings.error(str(err))
                    self.n += 1
                    continue
                else:
                    loggings.debug('{:<{}} {} data write file complete'.format(count, len(str(page_count)), title))
                    return True
            loggings.error(str(err))
            return False


def init_logs():
    '''
    记录日志，输出到控制台和文件
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
    return logs

loggings = init_logs()


