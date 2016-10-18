# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import re
import urllib.request
from public_features import loggings, analysis_title
import itertools


DBUG   = 0
reBODY =re.compile( r'<body.*?>([\s\S]*?)<\/body>', re.I)
reCOMM = r'<!--.*?-->'
reTRIM = r'<{0}.*?>([\s\S]*?)<\/{0}>'
reTAG  = r'<[\s\S]*?>|[ \t\r\f\v]'
reOTH  = r'(&nbsp;)*'
reIMG  = re.compile(r'<img[\s\S]*?src=[\'|"]([\s\S]*?)[\'|"][\s\S]*?>')


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
    """
    def __init__(self, html="", blockSize=5, timeout=5, image=False):
        self.html = html
        self.blockSize = blockSize
        self.timeout = timeout
        self.saveImage = image
        self.rawPage = ""
        self.ctexts = []
        self.cblocks = []

    def processTags(self):
        self.body = re.sub(reCOMM, "", self.body)
        self.body = re.sub(reTRIM.format("script"), "" ,re.sub(reTRIM.format("style"), "", self.body))
        # self.body = re.sub(r"[\n]+","\n", re.sub(reTAG, "", self.body))
        self.body = re.sub(reTAG, "", self.body)
        self.body = re.sub(reOTH, '', self.body)

    def processBlocks(self):
        self.ctexts   = self.body.split("\n")
        self.textLens = [len(text) for text in self.ctexts]

        self.cblocks  = [0]*(len(self.ctexts) - self.blockSize - 1)
        lines = len(self.ctexts)
        for i in range(self.blockSize):
            self.cblocks = list(map(lambda x,y: x+y, self.textLens[i: lines-1-self.blockSize+i], self.cblocks))

        maxTextLen = max(self.cblocks)

        if DBUG: print(maxTextLen)

        self.start = self.end = self.cblocks.index(maxTextLen)
        while self.start > 0 and self.cblocks[self.start] > min(self.textLens):
            self.start -= 1
        while self.end < lines - self.blockSize and self.cblocks[self.end] > min(self.textLens):
            self.end += 1

        return "\n".join(self.ctexts[self.start:self.end]).strip()

    def processImages(self):
        self.body = reIMG.sub(r'{{\1}}', self.body)

    def processText(self):
        """删除特定组合的内容"""
        lists = ("（快捷键←）",
                 "上一章", "返回目录", "加入书签", "推荐本书", "返回书页", "下一章", "（快捷键→）",
                 "投推", "荐票", "回目录", "标记", "书签"
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
            return -1

        self.text = self.text[:iter_text(self)].strip()

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
        self.text = self.processBlocks()
        self.processText()
        return self.text


def extract_text(page_link, domain_title):
    '''
    请求URL并提取主要文本
    :param page_link:
    :return: UTF-8编码的字符串
    '''
    page_get = urllib.request.urlopen(page_link, timeout=10)
    page_read = page_get.read()
    page_get.close()
    loggings.debug('%s Read complete!' % page_link)

    '''
    html5lib:       最好的容错性,以浏览器的方式解析文档,生成HTML5格式的文档,速度慢
    html.parser:    Python的内置标准库,执行速度适中,文档容错能力强
    lxml:           速度快,文档容错能力强
    '''
    page_soup = BeautifulSoup(page_read, 'html5lib')
    '''获取标题'''
    title = page_soup.title.get_text()
    '''分析提取标题'''
    analysis = analysis_title(title, domain_title)
    title_analysis = analysis.score()
    ext = Extractor(html=str(page_soup))
    text = ext.getContext()

    text = title_analysis + '\n\n' + text
    """编码转换 极为重要，编码成utf-8后解码utf-8 并忽略错误的内容"""
    text = text.encode('utf-8').decode('utf-8', 'ignore')
    return text, title_analysis

