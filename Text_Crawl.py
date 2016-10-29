# -*- coding: utf-8 -*-
"""
抓取网页提取正文保存到文件或发送到邮箱（适合Kindle）
主要是我自己用于下载小说用的，只测试了几个我自己常去下载的站点，当然也可以用于提取某页面的正文
目前不支持需要登录的网页
"""
import threading
import argparse
import itertools
import time
import re
import logging
import shutil
import os
import urllib.request
from bs4 import BeautifulSoup
import requests
import smtplib
import locale
import sys
import fnmatch
from email import encoders
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.utils import parseaddr, formataddr
import multiprocessing

try:
    import matplotlib.pyplot as pyplot
except ImportError:
    print('无法导入matplotlib模块，绘图功能将无法使用\n安装：>pip install matplotlib\n'
          '或者直接访问下载地址手动安装 https://pypi.python.org/pypi/matplotlib\n')
    mat_import = True
else:
    mat_import = False

"""
默认参数配置，具体用途及可选参数可在args_parser函数中查看
"""
default_args = {
    'pn': False,                                    # 尝试翻页
    'pv': 2,                                        # 翻页时不同段落的有效比例1/pv, 即最长与最短文本段落的比例
    'r': 3,                                         # 最大重试次数
    'debug': 3,                                     # 0关闭，1输出到控制台，2输出到文件，3同时输出
    'block_size': 4,                                # 文本行块分布函数块大小
    'drawing': False,                               # 显示文本块函数
    'leave_blank': True,                            # 保留空格与空行
    'image': False,                                 # 保留图片URL
    'ad_rem': True,                                 # 删除可能的广告
    'loop': False,                                  # 对页面进行多次筛选 适合有多段文本
    'email': False,                                 # 将结果发送邮件发送
    'email_to_address': 'sonny_yang@kindle.cn',     # 默认邮件收件人
    'dest': 'file',                                 # 结果输出位置
    'min_text_length': 100,                         # 页面最长文本段落的最小长度 小于这个值的将丢弃
    'm': 2                                          # 多线程数量  m x cpu
}


class FeaturesList(object):
    def __init__(self, args):
        self.loggings = logging.getLogger('log')
        self.down_path = 'down_text'
        self.saved_filename = []
        self.args = args
        self.Error_url = ['']
        self.Unable_write = ['']

    def init_logs(self, logs, lev=1):
        """
        记录日志，输出到控制台和文件
        """
        formatstr = logging.Formatter('%(asctime)s - %(levelname)-5s - %(message)s')
        e = False
        if lev is 0:
            return
        if lev is 2 or lev is 3:
            logs.setLevel(logging.DEBUG)
            try:
                out_file = logging.FileHandler(filename='run_logs.log', encoding='utf8')
            except IOError:
                lev = 1
                e = True
            else:
                out_file.setLevel(logging.DEBUG)
                out_file.setFormatter(formatstr)
                logs.addHandler(out_file)
        if lev is 1 or lev is 3:
            logs.setLevel(logging.DEBUG)
            debug_handler = logging.StreamHandler()
            debug_handler.setLevel(logging.DEBUG)
            debug_handler.setFormatter(formatstr)
            logs.addHandler(debug_handler)
            if e:
                logs.warning('The log can not be written to the file')
        logs.info('log config complete')

    def text_merge(self, path, merge_name, make=None):
        """
        合并文本        bug 读取文件夹时不判定内容是否是本次生成
        :param path:    文本目录
        :param count:   文本总数
        """
        if len(merge_name) < 2:
            merge_name = 'text_merge.txt'
        else:
            merge_name = re.sub(r'[/\\:\*\?\"<>\|]', '-', merge_name)  # 过滤文件名非法字符
            merge_name = '{}.txt'.format(merge_name)
            self.origin_url_title_file = merge_name

        if os.path.isfile('fileappend.tmp'):
            os.remove('fileappend.tmp')
        if os.path.isfile(merge_name):
            os.remove(merge_name)

        self.loggings.debug('Create a merge file')
        text_merge_path = os.path.join(path, self.down_path)

        file_names = self.saved_filename
        if len(file_names) == 0:
            for _, _, file_names in os.walk(text_merge_path):
                def num(s=''):
                    try:
                        int_s = int(s[:len(s.split()[0])])
                    except BaseException:
                        int_s = 0
                    return int_s
                file_names.sort(key=num)

            self.loggings.debug('The merged text starts...')
        with open(os.path.join(path, "fileappend.tmp"), "a", encoding='utf-8') as dest:
            first = False
            for filename in fnmatch.filter(file_names, '*.txt'):
                with open(os.path.join(text_merge_path, filename), encoding='utf-8') as src:
                    self.loggings.debug('合并 %s' % filename)
                    if first:
                        if make:
                            segmentation = '\n\n# {0} 第{1}页{0} \n\n'.format('-' * 12, str(file_names.index(filename) + 1))
                        else:
                            segmentation = '\n\n# {0}\n\n'.format('-' * 18)
                        dest.write(segmentation)
                    first = True
                    shutil.copyfileobj(src, dest)

        os.rename(os.path.join(path, "fileappend.tmp"), merge_name)
        self.loggings.debug('Text merged successfully:[%s]' % os.path.join(path, merge_name))

    def get_url_to_bs(self, url, re_count=0, ignore=False):
        """
        抓取url 返回 BeautifulSoup对象 协议 主域名 不含协议的url链接 状态码
        :param url:         原始url
        :param re_count:    最大失败重试计数
        :param ignore:      忽略错误
        :return:            BeautifulSoup对象 协议 主域名 不含协议的url链接 状态码
        """
        headers = {'User-Agent':
                       'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                       ' AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36'
                   }
        if not re.match('^https?://', url):
            url = 'http://' + url
        try:
            r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            # loggings.debug(r.request.headers)
            status_code = r.status_code
            content = r.content
            if not ignore and not (310 > status_code >= 200):
                r.close()
                raise urllib.request.URLError('Read Error [%s]，status code:%s' % (url, status_code))
        except BaseException as err:
            if re_count > 0:
                self.loggings.error('URL Access failed %s, [%s] Retry %s ' % (url, str(err), re_count))
                re_count -= 1
                return self.get_url_to_bs(url, re_count)
            if not ignore and re_count <= 0:
                raise err
            else:
                return False, None, None, None, None
        else:
            self.loggings.debug('Read Complete [%s]' % url)
            # 获取协议，域名
            protocol, rest = urllib.request.splittype(url)
            domain = urllib.request.splithost(rest)[0]
            r.close()
            soup = BeautifulSoup(content, 'html5lib')
            return soup, protocol, domain, rest, status_code

    def url_merge(self, page_url, raw_url, protocol):
        """
        :param page_url: 当前页URL
        :param raw_url: 采集到的URL
        :param protocol 协议类型
        :return:        合并的完整URL
        """

        def protocol_check(url=''):
            url = url.strip('/').strip()
            if not re.match('^https?://', url):
                return protocol + '://' + url
            else:
                return url

        if re.match('^(https?://)?((\w+\.)?\S+?\.\w+){1}/[^\s]+', raw_url):
            return protocol_check(raw_url)
        else:
            url1 = protocol_check(page_url)
            url1_segment = url1.strip('/').split('/')
            raw_url_segment = raw_url.strip('/').split('/')
            n, m, x = 0, 0, 0
            for u1 in url1_segment[1:]:
                if url1_segment[-1] == u1 and re.match('\S+\.\S{0,5}', u1):
                    continue
                for u2 in raw_url_segment[n:]:
                    if u1 == u2:
                        n += 1  # 成功计数
                        break
                    else:
                        x += 1  # 失败计数
                        if n == 0:  # 成功前的失败计数
                            m += 1
                        break
                '''首次成功遇到失败跳出，          首次失败成功后再次失败跳出 x-m=成功后的失败次数'''
                if (x > 0 and n > 0 and m == 0) or (x - m > 0):  # 成功匹配raw_url第一段
                    break
            url = '/'.join(url1_segment[:m + 1]) + '/' + raw_url.strip('/')
            return url

    def write_text(self, count, title, text, page_count=5):
        self.try_mkdir(self.down_path)
        if text is None or text == '':
            return True
        title = re.sub(r'[/\\:\*\?\"<>\|]', '-', title)  # 过滤文件名非法字符
        if self.args.s and count == 1000 and self.args.direction is False:
            filename_format = '.\{}\{}.txt'.format(self.down_path, title)
        else:
            filename_format = '.\{0}\{1:<{2}} {3}.txt'.format(self.down_path, str(count), len(str(page_count)), title)

        try:
            with open(filename_format, 'w', encoding='utf-8') as f:
                f.write(text)
            self.loggings.debug('The text was successfully written to the file [%-4s %s]' % (count, title))
        except BaseException as err:
            return err
        else:
            self.saved_filename.append(filename_format.split('\\')[-1])
            return True

    def try_mkdir(self, path):
        if not os.path.isdir(path):
            try:
                os.mkdir(self.down_path)
                self.loggings.debug("create %s folder" % path)
            except BaseException:
                raise OSError('Failed to create the folder %s' % path)

    class ChineseToDigits(object):
        """
        将中文数字转换为 int整数
        """

        def __init__(self):
            self.common_used_numerals = {u'零': 0, u'一': 1, u'二': 2, u'三': 3, u'四': 4, u'五': 5, u'六': 6, u'七': 7,
                                         u'八': 8,
                                         u'九': 9, u'十': 10, u'百': 100,
                                         u'千': 1000, u'万': 10000, u'亿': 100000000}

        def run(self, chars_cn):
            if type(chars_cn) is int:
                return chars_cn
            s = chars_cn
            if not s:
                return 0
            for i in [u'亿', u'万', u'千', u'百', u'十']:
                if i in s:
                    ps = s.split(i)
                    lp = self.run(ps[0])
                    if lp == 0:
                        lp = 1
                    rp = self.run(ps[1])
                    # print(i,s,lp,rp,'\n')
                    return lp * self.common_used_numerals.get(i, 0) + rp
            return self.common_used_numerals.get(s[-1], 0)

    def output_text_terminal(self, text=''):
        platform = sys.platform
        code = locale.getdefaultlocale()[1]
        code_dict = {
            'cp65001': 'utf-8',
            'cp932': 'gbk',
            'cp950': 'big5',
            'cp949': 'euc-kr',
            'cp936': 'gbk'}
        try:
            terminal_size = os.get_terminal_size().columns - 1
        except BaseException:
            terminal_size = 70
        if platform == 'win32':
            try:
                text = text.encode(encoding=code_dict[code], errors='ignore').decode(encoding=code_dict[code])
            except UnicodeEncodeError as err:
                pass
        text_format = '\n{0}\n{2}\n{0}\n{1}\n{0}\n{3}\n{0}'.format(terminal_size * '-', text,
                                                                   '|' * ((terminal_size // 2) - 5)
                                                                   + ' 正文内容 ' + (terminal_size // 2 - 5) * '|',
                                                                   terminal_size * '|')
        print(text_format)

    def next_page(self, htmlbs, direction=None):
        url = None
        if direction == 'up':
            up1 = htmlbs.find('a', string=re.compile(r'上一|[nN][eE]?[xX][tT]|&lt'))
            up2 = htmlbs.find('a', class_=re.compile(r'[pP][rR]?[eE][vV]'))
            if up1:
                url = up1.get('href')
            elif up2:
                url = up2.get('href')

        elif direction == 'down':
            down1 = htmlbs.find('a', string=re.compile('下一|[nN][eE]?[xX][tT]|&gt;'))
            down2 = htmlbs.find('a', class_=re.compile(r'[nN][eE]?[xX][tT]'))
            if down1:
                url = down1.get('href')
            elif down2:
                url = down2.get('href')

        return url

    class get_page_links():
        """
        抓取目录也的章节URL
        """
        def __init__(self, all_page_url_soup, rest, protocol):

            self.protocol = protocol
            self.soup = all_page_url_soup
            self.rest = rest
            self.content = self.soup.find_all(id="content")
            if len(self.content) == 0:
                self.content = self.soup.find_all(id='chapterlist')
            if len(self.content) == 0:
                self.content = self.soup.find('div', re.compile('centent|mainbody|catalog.box|volume-wrap'))
            self.contentbs = BeautifulSoup(str(self.content), 'html5lib')

            self.urllist = self.contentbs.find_all('a')

        def special_treatment(self, raw):
            """
            处理一些特殊URL标签
            :param raw:
            :return:    处理后的内容
            """
            if re.match('javascript:content', raw):
                url_end = self.rest.split('/')[-1].split('.')
                n1 = re.findall('\d+', raw)
                return '/{}/{}/{}{}'.format(n1[1], url_end[0], n1[0], '.' + url_end[1])
            return raw

        def get_href(self, url_merge):
            page_rul = []
            for index in self.urllist:
                href_str = index.get('href')
                title = index.get_text().strip()
                if re.match('^javascript:[^content]+|/?class|#|%s' % (self.protocol + ':' + self.rest), href_str):
                    continue
                if href_str == '':
                    continue
                if re.search('分卷阅读', title):
                    continue
                if re.search('订阅本卷', title):                            # 没登录 VIP章节直接丢弃
                    break
                page_rul.append([self.special_treatment(href_str), title])
            # 合并函数          原始URL                   要组合的列表
            end_links = map(url_merge, [self.rest] * len(page_rul), [x[0] for x in page_rul],
                            [self.protocol] * len(page_rul))

            x = 0
            for link in end_links:
                page_rul[x][0] = link
                x += 1
            if len(page_rul) == 0:
                raise IndexError('\n\n{}\nThe directory page can not find a valid url, '
                                 'Possible links are incorrect or not supported by script'.format(self.rest.strip('/')))
            return page_rul

    def extract_contents_url(self, ori_url, retry=0):
        """
        提取目录页的有效URL，抓取网站title
        :param ori_url: 目录页URL
        :return:        提取的章节URL 列表
        """
        self.loggings.debug('Open original url %s' % ori_url)
        try:
            soup_text, protocol, ori_domain, rest, code = self.get_url_to_bs(ori_url, re_count=retry)
        except BaseException as err:
            self.loggings.error(str(err))
            self.loggings.debug('Script Exit')
            sys.exit(-1)
        else:
            self.loggings.debug('Open original url complete！')
            # if 'qidian.com' in ori_domain:
            #     self.loggings.info('Use "qidian" Configure')
            #     qidian = self.qidian_conf()
            #     qidian.main(ori_url)
            #     sys.exit(0)
            self.origin_url_title = soup_text.title.string
            self.loggings.debug('Start the analysis original html doc...')
            get_page_links = self.get_page_links(soup_text, rest, protocol)
            all_page_links = get_page_links.get_href(url_merge=self.url_merge)

            def match_chinese(s):
                try:
                    re_s = re.match('[第卷]?\s*([零一二三四五六七八九十百千万亿]+)', s).group(1)
                except AttributeError:
                    try:
                        re_s = int(re.match('[第卷]?\s*([0123456789]+[^.-])', s).group(1))
                    except AttributeError:
                        re_s = '零'
                return re_s

            self.loggings.debug('Try to get the Chinese value for each title')
            contents = list(map(match_chinese, [x[-1] for x in all_page_links]))

            self.loggings.debug('make variable chinese_str duplicate')
            '''初始化中文数字转 int'''

            c2d = self.ChineseToDigits()
            self.loggings.debug('Began to Analyze the order of the article list...')
            contents = list(map(c2d.run, contents))

            '''验证目录是否有序'''
            test_number_str = ''.join([str(x) for x in contents])
            orderly = True
            if re.match('0*?123456789', test_number_str):
                orderly = False
                self.loggings.debug('The article list is sorted correctly :)')
            else:
                self.loggings.debug('Article list sort exception :( Start the collating sequence')
            '''将整数化的目录编号加入url title列表'''

            if len(all_page_links) == len(contents):
                for x in range(len(all_page_links)):
                    if orderly:  # 无序 使用实际序号
                        all_page_links[x].append(contents[x])
                    else:
                        all_page_links[x].append(x + 1)  # 有序 直接添加序号

            else:
                self.loggings.error('章节序号分析出现错误，填零处理')
                [all_page_links[x].append(0) for x in range(len(all_page_links))]

            '''目录顺不正常，按照序号count排序'''
            if orderly:
                all_page_links = sorted(all_page_links, key=lambda x: x[-1])
            self.loggings.debug('The article list sort is complete')

            return all_page_links, len(all_page_links), ori_domain


class ExtractText(FeaturesList):
    def __init__(self):
        """
        block_size:  文本块大小， 越小越严格，越大越宽松
        image:       保留图片url
        leave_blank: 保留文字中的空格
        drawing:     绘制文本分布函数图
        loop:      重复过滤模式
        """
        FeaturesList.__init__(self, args)
        # self.args = args
        self.reBODY = re.compile(r'<body.*?>([\s\S]*?)<\/body>', re.I)
        self.reCOMM = r'<!--.*?-->'
        self.reTRIM = r'<{0}.*?>([\s\S]*?)<\/{0}>'
        if self.args.leave_blank:
            self.reTAG = r'<[\s\S]*?>|[\t\r\f\v]'   # 保留空格和空行
        else:
            self.reTAG = r'<[\s\S]*?>|[ \t\r\f\v]'  # 删除所有空格和保留空行
        self.respa = r'(&nbsp;)+'
        self.relt = r'&lt;'
        self.regt = r'&gt;'
        self.rebr = '\n+'
        self.reIMG = re.compile(r'<img[\s\S]*?src=[\'|"]([\s\S]*?)[\'|"][\s\S]*?>')

        self.blocks_size = args.block_size
        self.save_image = args.image
        self.raw_page = ""
        self.c_texts = []
        self.min_text_length = default_args['min_text_length']          # 段落最低文本
        self.store_text = []
        self.section = 1
        self.leave_blank = args.leave_blank
        self.drawing = args.drawing
        self.loop = args.loop
        # loggings.debug('blocks_size={0};save_image={1};leave_blank={2};drawing={3}loop={4}'.format(self.blocks_size,
        #                 self.save_image, self.leave_blank, self.drawing, self.loop))
        if self.drawing:
            self.Draw = draw_processing()

    def tags_process(self):
        self.body = re.sub(self.reCOMM, "", self.body)
        self.body = re.sub(self.reTRIM.format("script"), "", re.sub(self.reTRIM.format("style"), "", self.body))
        self.body = re.sub(self.reTAG, "", self.body)
        self.body = re.sub(self.respa, '', self.body)
        # r'(&gt;)+' *次重复会导致0次匹配也成功的问题, 适用于有代码页面
        self.body = re.sub(self.relt, '<', self.body)
        self.body = re.sub(self.regt, '>', self.body)
        # 替换空白行为空
        while self.leave_blank:
            self.body, n = re.subn(r'\n +\n', '\n\n', self.body)
            # loggings.debug('del ... %s' % str(n))
            if n == 0:
                break

    def blocks_process(self):
        """
        通过《基于行块分布函数的通用网页正文抽取算法》实现
        主要变动:
            1:直接取了分布函数最高点，然后向前后推进确定起始与结束点
            2:新增了使用递归处理可能出现多段正文的情况
        使用 --dr 可查看文本分布函数曲线图, 在断点bug的情况下可能无法显示图形，原因不明。
        """
        self._text = None
        self.c_blocks = []
        self.c_texts_length = [len(x) for x in self.c_texts]
        '''生成块列表'''
        for x in range(len(self.c_texts) - self.blocks_size + 1):
            self.c_blocks.append(sum([len(y) for y in self.c_texts[x:x + self.blocks_size]]))

        # 首次过滤最长的文本段没有达到预定义的长度 则视为太短抛弃
        if max(self.c_texts_length) <= self.min_text_length and not self.recursion:
            self.loggings.debug('文本长度小于预设值{}，被抛弃:\n{}\n{}\n{}'.format(self.min_text_length, '-'*40,
                                                                      self.c_texts[self.c_texts_length.index(max(
                                                                          self.c_texts_length))], '-' * 40))
            return None

        '''函数分布图的最高点'''
        self.loggings.debug('max(c_text_length) = %s' % max(self.c_texts_length))
        max_block = max(self.c_blocks)
        self.start = self.end = self.c_blocks.index(max_block)
        '''
        这里start与end点是大于 行块的最小值。
        point > N，通常这个最小值是0（空行就是0），增大N将会过滤掉长度小于N的行
        '''
        self.N = min(self.c_blocks)
        while self.start >= 0 and self.c_blocks[self.start] > self.N:
            self.start -= 1

        while self.end < len(self.c_blocks) - 1 and self.c_blocks[self.end] > self.N:
            self.end += 1
        self._text = '\n'.join(self.c_texts[self.start + self.blocks_size: self.end])

        if self.drawing:self.Draw.put(self.c_blocks)                # 画图
        self.loggings.debug('blocks:{} blocks_start:{}  blocks_end:{}'.format(len(self.c_blocks), self.start, self.end))
        '''尝试再次获取有效文本，针对有多段有效文本的情况'''

        if self.recursion is False and self.direction_status is False:          # 第一次分析 获得本次字符串长度
            self.section = len(self._text)
            # self.x = 1
        else:                                                                   # 非第一次的操作
            self.x += 1
            d = False

            def detection_text_length(text, parameter, t=''):
                if len(text) < int(self.section / parameter):                   # 本次字符串长度小于第一次的一半则忽略
                    self.loggings.debug('本次分析达不到预定义的要求(大于最长段落的1/{0})，若本段为所需要的请增大"-{4}"值，抛弃内容如下:'
                                        '\n{1}\n{2}\n{3}'.format(parameter, '-' * 100, text, '-' * 100, t))
                    return True

            if self.args.direction:
                d = detection_text_length(self._text, self.args.pv, 'pv')
            elif self.loop:
                d = detection_text_length(self._text, self.loop, 'loop')
            if d:
                return None

        if not self.leave_blank:                                    # 删除空行
            self._text = re.sub(self.rebr, '\n', self._text)

        self.loggings.debug('第%s次再分析完成' % self.x)
        self.loggings.debug('有效标尺 %s' % self.section)
        self.loggings.debug('本次获得有效长度 %s' % len(self._text))
        self.store_text.append([self.start, self._text])            # 收集有效的段落
        # 删除已提取的段落
        self.c_texts = self.c_texts[:self.start + self.blocks_size] + self.c_texts[self.end:]
        # 开始递归操作,查找符合调节的第二段文本
        if self.loop:
            self.loggings.debug('第%s次分析开始' % (self.x + 1))
            self.recursion = True
            self.blocks_process()

        return self.store_text

    def del_invalid_text(self):
        """删除特定组合的内容 解决一些靠算法不好搞的内容"""
        lists = ("（快捷键←）",
                 "上一章", "返回目录", "加入书签", "推荐本书", "返回书页", "下一章", "（快捷键→）",
                 "投推", "荐票", "回目录", "标记", "书签", "登陆", "注册", '新用户', 'FAQ', '道具', '商城', '每日任务',
                 '咨询', '投诉', '举报'
                 )
        self.f = self.finally_text.split('\n')
        index = []

        def iter_text(self):
            """定位到单行内成功匹配三个关键字的行index值"""
            for x in self.f:
                for i in itertools.combinations(lists, r=3):
                    ass = 0
                    for ii in i:
                        if ii in x:
                            ass += 1
                    if ass >= 3:
                        index.append(self.finally_text.index(x))
                        break

        '''在匹配到上诉三个关键词的行截断首尾'''
        iter_text(self)
        if len(index) == 1 and index[0] > len(self.finally_text) / 2:
            self.finally_text = self.finally_text[:index[0]].strip()
        if len(index) >= 2:
            start = max(x for x in index if x < len(self.finally_text) / 2)
            end = min(y for y in index if y > len(self.finally_text) / 2)
            self.finally_text = self.finally_text[start:end]

    def crawl_context(self):
        self.raw_page = str(self.page_soup)
        try:
            self.body = re.findall(self.reBODY, self.raw_page)[0]
        except BaseException:
            # 某些body异常的网页
            self.body = self.raw_page
        if self.save_image: self.body = self.reIMG.sub(r'{{\1}}', self.body)
        self.tags_process()
        self.c_texts = self.body.split("\n")
        self.text = self.blocks_process()

        if self.text is None:
            return None
        # 排序并组合二维列表为字符串
        self.finally_text = '\n\n# -----\n\n'.join(y[1] for y in sorted(self.text, key=lambda x: x[0]))
        self.store_text = []
        self.del_invalid_text()

        return self.finally_text

    def delete_ad(self):
        """
        删除一些常见的广告推广等内容,修改原始对象无需返回函数
        """
        ad_list = []
        ad_list.append(self.page_soup.find_all('div', "thread_recommend thread-recommend"))
        ad_list.append(self.page_soup.find_all('div', "share_btn_wrapper"))
        ad_list.append(self.page_soup.find_all('div', "core_reply j_lzl_wrapper"))
        ad_list.append(self.page_soup.find_all('div', 'weixin'))
        ad_list.append(self.page_soup.find_all('a', string=re.compile('纠错')))
        ad_list.append(self.page_soup.find_all('div', class_=re.compile('region_bright my_app|novel-ranking-frs-body|topic_list_box')))
        ad_list.append(self.page_soup.find_all('li', class_=re.compile('l_badge')))
        for ad in ad_list:
            for x in ad:
                x.decompose()      # 方法将当前节点移除文档树并完全销毁

    def read_qidian(self, page_link=''):
        """
        起点中文网专用配置，该网站正文需要二次抓取
        """
        if 'qidian.com' in page_link:
            page_text = self.page_soup.find(id='chaptercontent')
            page_text = page_text.contents[3]
            page_text_url = page_text.attrs['src']
            page_text_bs, _, _, _, code = self.get_url_to_bs(page_text_url, re_count=self.args.retry)
            page_text_bs = str(page_text_bs)
            if code < 300:
                page_text = re.sub('<[\s\S]*?>|[ \t\r\f\v]', '', page_text_bs)
                page_text = re.sub('\S+\(|\);|\\n+|\'', '', page_text)
                page_text = re.sub('起点中文.*', '', page_text).strip()
                return page_text
            else:
                raise requests.ConnectionError('read failed {}{}'.format(page_link, code))

    def extract_text(self, page_link, page_tiele, page_id=0):
        """
        请求URL并提取主要文本
        :return: UTF-8编码的字符串和页面标题
        """
        self.id = page_id
        direction_url = None
        self.loggings.debug('Start Read %s' % page_link + page_tiele)
        self.page_soup, protocol, _, _, _ = self.get_url_to_bs(page_link, re_count=self.args.retry)
        get_page_tiele = self.page_soup.title.get_text()
        if page_tiele == '':
            page_tiele = get_page_tiele
            if self.direction_status is False:
                self.origin_url_title = page_tiele

        if self.page_soup and self.args.direction:
            direction_url = self.next_page(self.page_soup, direction=self.args.direction)
            if direction_url:
                direction_url = self.url_merge(page_url=page_link, raw_url=direction_url, protocol=protocol)

        self.loggings.debug('Read Complete [%s]' % page_tiele)

        if self.args.ad_rem:
            self.delete_ad()        # 去广告干扰

        self.loggings.info('Start trying to filter the page text [%s]' % page_tiele)

        text = self.read_qidian(page_link)
        if text is None:
            text = self.crawl_context()

        self.loggings.debug('Page text filtering is complete [%s]' % page_tiele)

        if text is None:
            return text, page_tiele, None
        text = page_tiele + '\n\n' + text
        """编码转换 极为重要，编码成utf-8后解码utf-8 并忽略错误的内容"""
        text = text.encode('utf-8').decode('utf-8', 'ignore')
        return text, page_tiele, direction_url

    def start_work(self):
        """
        启动位置
        """
        if not self.args.c:
            link_list = [[self.args.s, '', 1000]]
            page_count = 1
            self.single_process(link_list, page_count)
        else:
            links, page_count, domain = self.extract_contents_url(self.args.c, retry=self.args.retry)  # 从目录页面提取所有章节URL
            # self.single_process(link_list=links,page_count=page_count)
            mu_th(links, page_count)

            if not self.args.dest == 'terminal':
                self.text_merge(os.path.abspath('.'), merge_name=self.origin_url_title)  # 合并文本
                if self.args.email:
                    with open(self.origin_url_title_file, 'r') as f:
                            email = send_email(text=f.read(), title=self.origin_url_title, to_addr=self.args.email)
                            email.send()

        if len(self.Unable_write) == 1 and len(self.Error_url) == 1:
            public.loggings.debug('script complete, Everything OK!')
            sys.exit(0)
        public.loggings.debug('script complete, But there are some errors :(')
        try:
            terminal_size = os.get_terminal_size().columns - 1
        except BaseException:
            terminal_size = 70
        public.loggings.info(
            '\n\n{0}\n{1}Error total:\n{2}\n{3}\n{4}'.format('+' * terminal_size, ' ' * int(terminal_size / 2 - 5),
                                                             '# '.join(self.Error_url), '# '.join(self.Unable_write),
                                                             '+' * terminal_size))

    def single_process(self, link_list, page_count):
        """
        :param link_list:   页面URL总列表
        """
        self.recursion = False                       # 单url重复抓取标记
        self.direction_status = False                # 翻页成功标记
        self.x = 1
        count = 0

        while link_list:
            pop = link_list.pop(0)  # 提取一条链接并从原始列表删除
            link = pop[0]   # url
            title = pop[1]  # title
            count = pop[2]  # id
            try:
                page_text, title, direction = self.extract_text(link, title, count)
            except BaseException as err:
                # raise err
                self.loggings.error('URL{} requests failed, {} {} {}'.format(self.args.retry, title, link, str(err)))
                self.Error_url.append('requests failed ' + ' '.join([str(count), title, link, str(err)]))
            else:
                if self.args.direction and direction:                   # 成功获得下一页url
                    link_list.append([direction, title, count + 1])
                    self.loggings.debug('找到下一页 %s' % direction)
                    self.direction_status = True

                if page_text is None:  # 内容内空
                    msg = '%s No valid text to extract, possibly invalid pages, ' \
                          'or to confirm that a requested site needs to log in.' % title
                    if direction is False and self.args.s:
                        raise IndexError(msg)
                    else:
                        self.loggings.warning(msg)
                else:  # 内容非空
                    if self.args.email and self.direction_status is False and self.args.s:   # 邮件发送 单页面时
                        email = send_email(page_text, title=title, to_addr=self.args.email)
                        email.send()
                    if self.args.dest == 'file' or self.args.dest == 'all':                       # 写入文件
                        wr = self.write_text(count, title, page_text, page_count)
                        if wr is not True:
                            self.Unable_write.append('Write failed ' + ' '.join([str(count), title, link, str(wr)]))
                    if self.args.dest == 'terminal' or self.args.dest == 'all':                   # 控制台输出
                        self.output_text_terminal(page_text)
        if self.drawing:
            time.sleep(1)
            self.Draw.put(None)  # 确保绘图子进程结束后主线程可以退出
            self.loggings.debug('多进程绘图进程已结束')

        if self.direction_status and not self.args.dest == 'terminal':                              # 翻页成功 合并文件
            self.text_merge(os.path.abspath('.'), merge_name=self.origin_url_title, make=self.args.direction)

        if self.direction_status and self.args.email and not self.args.dest == 'terminal':          # 翻页成功且发送邮件
            with open(self.origin_url_title_file, 'r', encoding='utf-8') as f:
                email = send_email(text=f.read(), title=self.origin_url_title, to_addr=self.args.email)
                email.send()


def mu_th(links, page):
    class MuThreading(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)
            self.daemon = True

        def run(self):
            ext = ExtractText()
            ext.single_process(links, page_count=page)

    mu_list = []
    public.loggings.debug('chapter processing starts  ')
    for num in range(os.cpu_count() * args.m):
        m = MuThreading()
        mu_list.append(m)
        m.start()  # 开始线程
    for mu in mu_list:
        mu.join()  # 等待所有线程完成
    public.loggings.debug('Multi-threaded processing is complete! ')


class draw_processing():
    """
    多进程模式画出字块分布函数图
    """
    def __init__(self):
        self.mu_list = {}
        self.n = 0
        self.queue = multiprocessing.Queue()
        self.mu = multiprocessing.Process(target=self.work, args=(self.queue,))
        self.mu.start()
        public.loggings.debug('多进程绘图进程已启动...')

    def draw(self, c_blocks, name='test'):
        pyplot.plot(c_blocks)
        # pyplot.ylabel(name)
        pyplot.title(name)
        pyplot.show()

    def work(self, q):
        while True:
            value = q.get(block=True)
            if value is None:
                break
            if mat_import:
                continue
            title = 'The {}th text distribution function'.format(str(self.n + 1))
            self.mu_list[str(self.n)] = multiprocessing.Process(target=self.draw, args=(value, title))
            self.mu_list[str(self.n)].daemon = False  # False保证主线程不会结束
            start = self.mu_list[str(self.n)]
            start.start()
            self.n += 1

    def put(self, sequence):
        """
        :param sequence:    二维int列表
        """
        self.queue.put(sequence)


class send_email(FeaturesList):
    def __init__(self, text='', title='', to_addr='sonny_yang@kindle.cn'):
        FeaturesList.__init__(self, args)
        # 发件人
        self.from_addr = 'it_yangsy@ish.com.cn'
        # 发件人密码
        self.password = 'klzsysy'
        # 收件人列表
        self.to_addr = self.__split_addr(to_addr)

        self.mail_title = title
        self.smtp_server = 'smtp.ish.com.cn'
        # 退信收件人列表
        # self.bounce_addr = self._split_addr(bounce_addr)
        from io import BytesIO
        i = BytesIO()
        i.write(text.encode('utf-8'))
        self.text = i.getvalue()

    def __split_addr(self, email_addr=''):
        addr = []
        for x in email_addr.split(';'):
            x = x.strip()
            addr.append(x)
        return addr

    def __format_addr(self, s):
        name, addr = parseaddr(s)
        return formataddr((Header(name, 'utf-8').encode(), addr))

    def __sendmail(self):

        self.msg = MIMEMultipart()
        self.msg.attach(MIMEText('给我发到kindle', 'plain', 'utf-8'))

        self.msg['From'] = self.__format_addr('Python Program <%s>' % self.from_addr)
        self.msg['To'] = ';'.join(self.to_addr)
        self.msg['Subject'] = Header('Convert', 'utf-8').encode()

        self.mime = MIMEBase('text', 'txt', filename=self.mail_title + '.txt')
        self.mime.add_header('Content-Disposition', 'attachment', filename=self.mail_title + '.txt')
        self.mime.add_header('Content-ID', '<0>')
        self.mime.add_header('X-Attachment-Id', '0')
        self.mime.set_payload(self.text)
        encoders.encode_base64(self.mime)
        self.msg.attach(self.mime)
        self.loggings.debug("构建邮件完成，尝试发送邮件...")
        try:
            self.loggings.debug("开始解析邮件服务器信息")
            server = smtplib.SMTP(self.smtp_server, 25)
            # server.set_debuglevel(1)
            self.loggings.debug("开始登录到smtp服务器")
            server.login(self.from_addr, self.password)
            self.loggings.debug("登录到SMTP服务器成功开始发送邮件")
            server.sendmail(self.from_addr, self.to_addr, self.msg.as_string())
            server.close()
        except smtplib.SMTPAuthenticationError as err:
            self.loggings.debug("登录到smtp服务器失败！")
            raise err
        except Exception as err:
            self.loggings.error('邮件发送失败\nError:\n' + str(err) + '\n\nHeader:\n' + self.msg.as_string())
        else:
            self.loggings.info("邮件已成功发送到%s" % self.to_addr)

    def send(self):
        self.__sendmail()

# class UrlAction(argparse.Action):
#     def __call__(self, parser, namespace, values, option_string=None):
#         global html_url
#         html_url = values[0]
#         setattr(namespace, self.dest, values)


def args_parser():
    parse = argparse.ArgumentParser(prog='Text fetching', description='文本抓取使用方法',
                                    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ''''''
    parse_url_group = parse.add_mutually_exclusive_group(required=True)
    parse_url_group.add_argument('-c', metavar='catalog url', nargs=1, type=str,
                                 help='目录页地址，下载小说通常为所有章节的目录页url')
    parse_url_group.add_argument('-s', metavar='single url', nargs=1, type=str,
                                 help='文本页URL, 抓取单一url的文本内容')
    ''''''
    parse.add_argument('-pn', dest='direction', choices=['up', 'down'], default=default_args['pn'], help='尝试向前或向后翻页')
    parse.add_argument('-pv', nargs='?', type=int, choices=range(2, 6), default=default_args['pv'], help='翻页参数，不同页的有效内容最大相差比')
    parse.add_argument('-r', nargs=1, dest='retry', type=int, choices=range(0, 8), default=[default_args['r']], help='最大请求失败重试次数')
    parse.add_argument('-m', type=int, choices=range(1, 6), default=default_args['m'], help='多线程倍数, N = m x cpu')
    parse.add_argument('-debug', nargs=1, type=int, choices=range(0, 4), default=[default_args['debug']],
                       help='debug功能，0关闭，1输出到控制台，2输出到文件，3同时输出')

    switch_group = parse.add_argument_group(title='高级选项', description='针对不同的情况调整策略以获得最佳效果, 参数只需要输入开头即可')
    switch_group.add_argument('-b', dest='block_size', type=int, choices=range(2, 12), default=default_args['block_size'],
                              help='文本行块分布函数块大小，值越小筛选越严格，获得的内容可能越少，适用于正文密集度高，反之同理')
    switch_group.add_argument('--drawing', action='store_const', const=True, default=default_args['drawing'],
                              help='绘制文本分布函数图，图形化上一个选项的文本块分布函数，可调整不同值做对比，仅在文本页-s模式有效')
    switch_group.add_argument('--blank-remove', dest='leave_blank', action='store_const', const=False,
                              default=default_args['leave_blank'], help='删除文本中的空格与空行，默认保留')
    switch_group.add_argument('--image-remove', dest='image', action='store_const', const=True, default=default_args['image'],
                              help='保留正文中的图片链接，默认删除')
    switch_group.add_argument('--ad-remove', dest='ad_rem', action='store_const', const=False, default=default_args['ad_rem'],
                              help='关闭 删除广告及推广 功能，默认删除广告')
    switch_group.add_argument('-loop', nargs='?', type=int, choices=range(2, 6), const=2, default=default_args['loop'],
                              help='启用循环过滤，对页面进行多次筛选，适合有多段落的情况，预设值为不小于首段文本长度的1/2')
    switch_group.add_argument('-email', metavar='xx@abc.com', nargs='?', const=default_args['email_to_address'],
                              default=default_args['email'], help='将获取的正文以邮件附件的形式发送到收件人, 不输入邮件地址发送到预设邮箱 %(const)s')
    switch_group.add_argument('-dest', choices=['off', 'file', 'terminal', 'all'], default=default_args['dest'],
                              help='将内容输出到指定目标 %(choices)s')

    parse.add_argument('--version', action='version', version='%(prog)s 0.6', help='显示版本号')
    ide_debug = '-s http://beautifulsoup.readthedocs.io/zh_CN/latest/   -b 10 --dr -loo 5'.split()
    # ide_debug = '-c http://www.52dsm.com/chapter/6712.html'.split()
    ide_debug = None
    args_ = parse.parse_args(ide_debug)
    args_.debug = args_.debug[0]
    args_.retry = args_.retry[0]
    if args_.c:
        args_.drawing = False               # 抓取目录-c模式下关闭绘图功能
        args_.direction = False             # 抓取目录-c模式下关闭下一页功能
        args_.c = args_.c[0]
    elif args_.s:
        args_.s = args_.s[0]
    print(args_)
    return args_


if __name__ == '__main__':
    args = args_parser()
    public = FeaturesList(args=args)
    public.init_logs(public.loggings, args.debug)
    Ext = ExtractText()
    Ext.start_work()
