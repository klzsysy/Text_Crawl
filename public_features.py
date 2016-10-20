# -*- coding: utf-8 -*-
import re
import logging
import shutil
import os
import fnmatch
import urllib.request
from bs4 import BeautifulSoup


Down_path = 'down_text'


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


def get_url_to_bs(url, re_count=0, ingore=False):
    """
    抓取url               返回 BeautifulSoup对象 协议 主域名 不含协议的url链接 状态码
    :param url:         原始url
    :param re_count:    最大失败重试计数
    :param ingore:      忽略错误
    :return:            BeautifulSoup对象 协议 主域名 不含协议的url链接 状态码
    """
    headers = {'User-Agent':
                   'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                   ' AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36'
               }
    if not re.match('^https?://', url):
        url = 'http://' + url
    request = urllib.request.Request(url, headers=headers)
    try:
        result = urllib.request.urlopen(request, timeout=15)
        content = result.read()
    except BaseException as err:
        if re_count > 0:
            loggings.error('URL read ERROR, retry %s' % re_count + str(err))
            re_count -= 1
            get_url_to_bs(url, re_count)
        if not ingore:
            raise err
        else:
            return False, None, None, None, None
    else:
        # info = result.info()
        loggings.info('read URL complete！')
        # 获取协议，域名
        protocol, rest = urllib.request.splittype(url)
        domain = urllib.request.splithost(rest)[0]
        status_code = result.code
        result.close()
        soup = BeautifulSoup(content, 'html5lib')
        return soup, protocol, domain, rest, status_code


def url_merge(url1, raw_url, protocol):
    """
    :param url1:    当前页URL
    :param raw_url: 采集到的URL
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
                try:
                    self.split_str = re.search('[\|, -]+', self.rever_page_title_str).group()   # 取得分割符 搜索第一个分割符号
                except AttributeError as err:
                    loggings.error('analysis_title 无法找到分隔符号:' + str(err))
                    self.title_sp = [x.strip() for x in self.page_title_str.split(' ')]
                else:
                    self.title_sp = [x.strip() for x in self.page_title_str.split(self.split_str)]
            else:       # not website title
                self.math_text(self.page_title_str)
                self.split_str = re.match('\S+?([, -]+)', self.page_title_str).group(1)
                self.title_sp = [x.strip() for x in self.page_title_str.split(self.split_str)]
        except BaseException as err:
            loggings.error('analysis_title:' + str(err))
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
        if text is None or text == '':
            return True
        # try:
        #     if not re.search('[0123456789一二三四五六七八九十零〇百千两]+', title).group() == count+1:
        #         count = ''
        # except AttributeError:
        #     pass
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


def try_mkdir(path):
    if not os.path.isdir(path):
        try:
            os.mkdir(Down_path)
            loggings.debug("create %s complete" % path)
        except BaseException:
            raise OSError('can not create folder %s' % path)


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
        特殊处理一些URL标签
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
            if re.match('^javascript:[^content]+|/?class|#|%s' % self.protocol+self.rest, href_str):
                continue
            if href_str == '':
                continue
            page_rul.append([self.special_treatment(href_str), title])
        #   合并函数        原始URL                   要组合的列表
        end_links = map(url_merge, [self.rest]*len(page_rul), [x[0] for x in page_rul], [self.protocol]*len(page_rul))

        x = 0
        for link in end_links:
            page_rul[x][0] = link
            x += 1
        return page_rul

class chinese_to_digits(object):
    """
    将中文数字转换为 int整数
    """
    def __init__(self):
        self.common_used_numerals = {u'零': 0, u'一': 1, u'二': 2, u'三': 3, u'四': 4, u'五': 5, u'六': 6, u'七': 7, u'八': 8,
                                u'九': 9, u'十': 10, u'百': 100,
                                u'千': 1000, u'万': 10000, u'亿': 100000000}

    def run(self, uchars_cn):
        s=uchars_cn
        if not s :
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