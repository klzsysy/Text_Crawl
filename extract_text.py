# -*- coding: utf-8 -*-
import re
from public_features import get_url_to_bs, loggings
import itertools

DBUG = 0
reBODY = re.compile( r'<body.*?>([\s\S]*?)<\/body>', re.I)
reCOMM = r'<!--.*?-->'
reTRIM = r'<{0}.*?>([\s\S]*?)<\/{0}>'
reTAG = r'<[\s\S]*?>|[ \t\r\f\v]'
# reTAG  = r'<[\s\S]*?>|[\t\r\f\v]'     # 保留空格 还有bug
reOTH = r'(&nbsp;)+'
relt = r'&lt;'
regt = r'&gt;'
reIMG = re.compile(r'<img[\s\S]*?src=[\'|"]([\s\S]*?)[\'|"][\s\S]*?>')


class Extractor():
    """
    https://github.com/rainyear/cix-extractor-py
    基于行块分布函数的通用网页正文（及图片）抽取
    有修改:
        1:变更了网页抓取与解析压缩方式，解决乱码问题，使用了BeautifulSoup模块进行解析与格式化html内容
        2:对存在报错的位置进行了处理
        3:针对小说类页面过滤无效内容
            self.body = re.sub(reOTH, '', self.body)
            def processText(self):
        4:新增了使用递归处理可能出现多段正文的情况
    """
    def __init__(self, html="", blockSize=5, timeout=5, image=False):
        self.html = html
        self.blockSize = blockSize
        self.timeout = timeout
        self.saveImage = image
        self.rawPage = ""
        self.ctexts = []
        self.cblocks = []

        self.minimum_effective_value = 100          # 段落最低文本
        self.text_temp = ''
        self.store_text = []
        self.section = 1

    def leave_blank(self):
        import keyword
        import builtins
        k = dict(zip(keyword.kwlist, list(map(lambda x: '{} '.format(x), keyword.kwlist))))
        b = dict(zip(dir(builtins),  list(map(lambda x: '{} '.format(x), dir(builtins)))))
        leave_dict = dict(k, **b)
        def re_sub(t):
            self.body = re.sub(pattern='^{}'.format(t[0]), repl=t[1], string=self.body, flags=re.M)
        list(map(re_sub, leave_dict.items()))

    def processTags(self):
        self.body = re.sub(reCOMM, "", self.body)
        self.body = re.sub(reTRIM.format("script"), "" ,re.sub(reTRIM.format("style"), "", self.body))
        # self.body = re.sub(r"[\n]+","\n", re.sub(reTAG, "", self.body))
        self.body = re.sub(reTAG, "", self.body)
        self.body = re.sub(reOTH, '', self.body)

        # r'(&gt;)+' *次重复会导致0次匹配也成功的问题, 适用于有代码页面
        self.body = re.sub(relt, '<', self.body)
        self.body = re.sub(regt, '>', self.body)
        # self.leave_blank()

    def processBlocks(self, recursion=False):
        self.textLens = [len(text) for text in self.ctexts]
        if max(self.textLens) <= self.minimum_effective_value:       # 文本段没有达到预定义的长度
            return None
        self.cblocks  = [0]*(len(self.ctexts) - self.blockSize - 1)     #
        lines = len(self.ctexts)
        for i in range(self.blockSize):
            self.cblocks = list(map(lambda x,y: x+y, self.textLens[i: lines-1-self.blockSize+i], self.cblocks))

        maxTextLen = max(self.cblocks)

        if DBUG: print(maxTextLen)

        self.start = self.end = self.cblocks.index(maxTextLen)
        while self.start > 0 and self.cblocks[self.start] > min(self.textLens):
            self.start -= 1
        try:
            while self.end < lines - self.blockSize and self.cblocks[self.end] > min(self.textLens):
                self.end += 1
        except BaseException:
            return None

        '''尝试再次获取有效文本，针对有多段有效文本的情况'''
        self.text_temp = "\n".join(self.ctexts[self.start:self.end]).strip()
        if not recursion:                                               # 第一次分析 获得本次字符串长度
            self.section = len(self.text_temp)
        else:                                                           # 非第一次的递归操作
            if len(self.text_temp) < int(self.section / 2):             # 本次字符串长度小于第一次的一半则忽略
                return None
        self.store_text.append([self.start, self.text_temp])            # 收集有效的段落
        self.ctexts = self.ctexts[:self.start] + self.ctexts[self.end:] # 删除已提取的段落
        self.processBlocks(recursion=True)                              # 开始递归操作
        return self.store_text


    def processImages(self):
        self.body = reIMG.sub(r'{{\1}}', self.body)

    def del_invalid_text(self):
        """删除特定组合的内容"""
        lists = ("（快捷键←）",
                 "上一章", "返回目录", "加入书签", "推荐本书", "返回书页", "下一章", "（快捷键→）",
                 "投推", "荐票", "回目录", "标记", "书签","登陆", "注册",'新用户', 'FAQ', '道具', '商城', '每日任务',
                 '咨询','投诉', '举报'
                 )
        self.f = self.text.split('\n')

        def iter_text(self):
            """定位到单行内成功匹配三个关键字的行index值"""
            for i in itertools.combinations(lists, r=3):
                ass = 0
                for x in self.f:
                    for ii in i:
                        if ii in x:
                            ass += 1
                    if ass >= 3:
                        return self.text.index(x)
            return None     # 无匹配
        '''在匹配到上诉三个关键词的行截尾'''
        i = iter_text(self)
        if i:
            self.text = self.text[:i].strip()

    def getContext(self):
        self.rawPage = self.html
        try:
            self.body = re.findall(reBODY, self.rawPage)[0]
        except BaseException:
            self.body = self.rawPage
        if DBUG: print(self.rawPage)

        if self.saveImage:
            self.processImages()
        self.processTags()
        self.ctexts = self.body.split("\n")
        self.text = self.processBlocks()
        if self.text is None:
            return None
        # 排序并组合二维列表
        self.text = '\n\n#---------------\n\n'.join(y[1] for y in sorted(self.text, key=lambda x: x[0]))
        self.del_invalid_text()
        if len(self.text) < self.minimum_effective_value:
            return None
        return self.text


def extract_text(page_link, page_tiele, retey=0):
    '''
    请求URL并提取主要文本
    :param page_link:
    :return: UTF-8编码的字符串
    '''

    loggings.debug('Start Read %s' % page_link + page_tiele)
    page_soup, _, _, _, _ = get_url_to_bs(page_link, re_count=retey)
    get_page_tiele = page_soup.title.get_text()
    if page_tiele == '':
        page_tiele = get_page_tiele

    loggings.debug('Read Complete [%s]' % page_tiele)

    ext = Extractor(html=str(page_soup))
    loggings.info('Start trying to filter the page text [%s]' % page_tiele)
    text = ext.getContext()

    if text is None:
        raise IndexError('No valid text to extract, possibly invalid pages, '
                         'or to confirm that a requested site needs to log in. [%s]' % page_tiele)

    loggings.debug('Page text filtering is complete [%s]' % page_tiele)
    text = page_tiele + '\n\n' + text
    """编码转换 极为重要，编码成utf-8后解码utf-8 并忽略错误的内容"""
    text = text.encode('utf-8').decode('utf-8', 'ignore')
    return text, page_tiele
