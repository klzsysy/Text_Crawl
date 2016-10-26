# -*- coding: utf-8 -*-
import re
import logging
import shutil
import os
import fnmatch
import urllib.request
from bs4 import BeautifulSoup
import requests
from email import encoders
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.utils import parseaddr, formataddr
import multiprocessing
import smtplib
import locale
import sys

try:
    import matplotlib.pyplot as pyplot
except ImportError:
    print('无法导入matplotlib模块，绘图功能将无法使用\n安装：>pip install matplotlib\n'
          '或者直接访问下载地址手动安装 https://pypi.python.org/pypi/matplotlib\n')
    mat_import = True
else:
    mat_import = False

# 下载目录
down_path = 'down_text'

def init_logs(logs, lev=1):
    '''
    记录日志，输出到控制台和文件
    '''
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

loggings = logging.getLogger('log')


def text_merge(path, count):
    '''
    合并文本
    :param path: 文本目录
    '''
    if os.path.isfile('fileappend.tmp'):
        os.remove('fileappend.tmp')
    if os.path.isfile('text_merge.txt'):
        os.remove('text_merge.txt')

    with open(os.path.join(path, "fileappend.tmp"), "a", encoding='utf-8') as dest:
        loggings.debug('Create a merge file')
        text_merge_path = os.path.join(path, down_path)
        for _, _, filenames in os.walk(text_merge_path):
            loggings.debug('The merged text starts...')
            '''文件名排序'''
            def num(s):
                return int(s[:len(str(count))])
            filenames.sort(key=num)

            for filename in fnmatch.filter(filenames, "*.txt"):
                with open(os.path.join(text_merge_path, filename), encoding='utf-8') as src:
                    shutil.copyfileobj(src, dest)
                    dest.write('\n\n# ---------------------\n\n')
    os.rename(os.path.join(path, "fileappend.tmp"), "text_merge.txt")
    loggings.debug('Text merged successfully:[%s]' % os.path.join(path, 'text_merge.txt'))


def get_url_to_bs(url, re_count=0, ignore=False):
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
            loggings.error('URL Access failed %s, [%s] Retry %s ' % (url, str(err), re_count))
            re_count -= 1
            return get_url_to_bs(url, re_count)
        if not ignore and re_count <= 0:
            raise err
        else:
            return False, None, None, None, None
    else:
        loggings.debug('Read Complete [%s]' % url)
        # 获取协议，域名
        protocol, rest = urllib.request.splittype(url)
        domain = urllib.request.splithost(rest)[0]
        r.close()
        soup = BeautifulSoup(content, 'html5lib')
        return soup, protocol, domain, rest, status_code


def url_merge(url1, raw_url, protocol):
    """
    :param url1:    当前页URL
    :param raw_url: 采集到的URL
    :param protocol 协议类型
    :return:        合并的完整URL
    """
    def protocol_check(url=''):
        url = url.strip('/').strip()
        if not re.match('^https?://', url):
            return protocol + '://' + url
        else:return url

    if re.match('^(https?://)?((\w+\.)?\S+?\.\w+){1}/[^\s]+', raw_url):
        return protocol_check(raw_url)
    else:
        url1 = protocol_check(url1)
        url1_segment = url1.strip('/').split('/')
        raw_url_segment = raw_url.strip('/').split('/')
        n, m, x = 0, 0, 0
        for u1 in url1_segment[1:]:
            if url1_segment[-1] == u1 and re.match('\S+\.\S{0,5}', u1):
                continue
            for u2 in raw_url_segment[n:]:
                if u1 == u2:
                    n += 1      # 成功计数
                    break
                else:
                    x += 1      # 失败计数
                    if n == 0:  # 成功前的失败计数
                        m += 1
                    break
            '''首次成功遇到失败跳出，          首次失败成功后再次失败跳出 x-m=成功后的失败次数'''
            if (x > 0 and n > 0 and m == 0) or (x - m > 0):           # 成功匹配raw_url第一段
                break
        url = '/'.join(url1_segment[:m+1]) + '/' + raw_url.strip('/')
        return url


def write_text(args, count, title, text, page_count=5):
    if text is None or text == '':
        return True
    title = re.sub(r'[/\\:\*\?\"<>\|]', '-', title)         # 过滤文件名非法字符
    if args.s and count == 1000:
        filename_format = '.\{}\{}.txt'.format(down_path, title)
    else:
        filename_format = '.\{0}\{1:<{2}} {3}.txt'.format(down_path, str(count), len(str(page_count)), title)
    try:
        with open(filename_format, 'w', encoding='utf-8') as f:
            f.write(text)
        loggings.debug('The text was successfully written to the file [%-4s %s]' % (count, title))
        return True
    except BaseException as err:
        return err


def try_mkdir(path):
    if not os.path.isdir(path):
        try:
            os.mkdir(down_path)
            loggings.debug("create %s folder" % path)
        except BaseException:
            raise OSError('Failed to create the folder %s' % path)


class get_page_links(object):
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
            self.content = self.soup.find('div', re.compile('centent|mainbody|catalog.box'))
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

    def get_href(self):
        page_rul = []
        for index in self.urllist:
            href_str = index.get('href')
            title = index.get_text().strip()
            if re.match('^javascript:[^content]+|/?class|#|%s' % (self.protocol + ':' +self.rest), href_str):
                continue
            if href_str == '':
                continue
            page_rul.append([self.special_treatment(href_str), title])
        #                 合并函数                          原始URL                   要组合的列表
        end_links = map(url_merge, [self.rest]*len(page_rul), [x[0] for x in page_rul], [self.protocol]*len(page_rul))

        x = 0
        for link in end_links:
            page_rul[x][0] = link
            x += 1
        if len(page_rul) == 0:
            raise IndexError('\n\n{}\nThe directory page can not find a valid url, '
                             'Possible links are incorrect or not supported by script'.format(self.rest.strip('/')))
        return page_rul


class chinese_to_digits(object):
    """
    将中文数字转换为 int整数
    """
    def __init__(self):
        self.common_used_numerals = {u'零': 0, u'一': 1, u'二': 2, u'三': 3, u'四': 4, u'五': 5, u'六': 6, u'七': 7, u'八': 8,
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
                ps=s.split(i)
                lp=self.run(ps[0])
                if lp==0:
                    lp=1
                rp=self.run(ps[1])
                # print(i,s,lp,rp,'\n')
                return lp*self.common_used_numerals.get(i, 0)+rp
        return self.common_used_numerals.get(s[-1], 0)


class draw_processing(object):
    """
    多进程模式画出字块分布函数图
    """
    def __init__(self):
        self.mu_list = {}
        self.n = 0
        self.queue = multiprocessing.Queue()
        self.mu = multiprocessing.Process(target=self.work, args=(self.queue,))
        self.mu.start()
        loggings.debug('多线程绘图进程已启动...')

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
            if mat_import: continue
            title = 'The {}th text distribution function'.format(str(self.n+1))
            self.mu_list[str(self.n)] = multiprocessing.Process(target=self.draw, args=(value, title))
            self.mu_list[str(self.n)].daemon = False        # False保证主线程不会结束
            start = self.mu_list[str(self.n)]
            start.start()
            self.n += 1

    def put(self, sequence):
        """
        :param sequence:    二维int列表
        """
        self.queue.put(sequence)


class send_email(object):
    def __init__(self, text='', title='', to_addr='sonny_yang@kindle.cn'):
        # 发件人
        self.from_addr = 'it_yangsy@ish.com.cn'
        # 发件人密码
        self.password = 'klzsysy'
        # 收件人列表
        self.to_addr = self._split_addr(to_addr)

        self.mail_title = title
        self.smtp_server = 'smtp.ish.com.cn'
        # 退信收件人列表
        # self.bounce_addr = self._split_addr(bounce_addr)
        from io import BytesIO
        i = BytesIO()
        i.write(text.encode('utf-8'))
        self.text = i.getvalue()

    def _split_addr(self, email_addr=''):
        addr = []
        for x in email_addr.split(';'):
            x = x.strip()
            addr.append(x)
        return addr

    def _format_addr(self, s):
        name, addr = parseaddr(s)
        return formataddr((Header(name, 'utf-8').encode(), addr))

    def _sendmail(self):

        self.msg = MIMEMultipart()
        self.msg.attach(MIMEText('给我发到kindle', 'plain', 'utf-8'))

        self.msg['From'] = self._format_addr('Python Program <%s>' % self.from_addr)
        self.msg['To'] = ';'.join(self.to_addr)
        self.msg['Subject'] = Header('Convert', 'utf-8').encode()

        self.mime = MIMEBase('text', 'txt', filename=self.mail_title+'.txt')
        self.mime.add_header('Content-Disposition', 'attachment', filename=self.mail_title+'.txt')
        self.mime.add_header('Content-ID', '<0>')
        self.mime.add_header('X-Attachment-Id', '0')
        self.mime.set_payload(self.text)
        encoders.encode_base64(self.mime)
        self.msg.attach(self.mime)
        loggings.debug("构建邮件完成，尝试发送邮件...")
        try:
            loggings.debug("开始解析邮件服务器信息")
            server = smtplib.SMTP(self.smtp_server, 25)
            # server.set_debuglevel(1)
            loggings.debug("开始登录到smtp服务器")
            server.login(self.from_addr, self.password)
            loggings.debug("登录到SMTP服务器成功开始发送邮件")
            server.sendmail(self.from_addr, self.to_addr, self.msg.as_string())
            server.close()
        except smtplib.SMTPAuthenticationError as err:
            loggings.debug("登录到smtp服务器失败！")
            raise err
        except Exception as err:
            loggings.error('邮件发送失败\nError:\n' + str(err) + '\n\nHeader:\n' + self.msg.as_string())
        else:
            loggings.info("邮件已成功发送到%s" % self.to_addr)

    def send(self):
        self._sendmail()


def output_text_terminal(text=''):
    platform = sys.platform
    code = locale.getdefaultlocale()[1]
    code_dict = {
        'cp65001':'utf-8',
        'cp932':'gbk',
        'cp950':'big5',
        'cp949':'euc-kr',
        'cp936':'gbk'}
    try:
        terminal_size = os.get_terminal_size().columns - 1
    except BaseException:
        terminal_size = 70

    if platform == 'win32':
        try:
            text = text.encode(encoding=code_dict[code], errors='ignore').decode(encoding=code_dict[code])
        except BaseException as err:
            pass
    text_format = '\n{0}\n{2}\n{0}\n{1}\n{0}\n{3}\n{0}'.format(terminal_size * '-', text, '|' * ((terminal_size//2) - 5)
                    + ' 正文内容 '+ (terminal_size//2 - 5) * '|', terminal_size * '|')
    print(text_format)
