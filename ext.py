# -*- coding: utf-8 -*-
import requests as req
import re

DBUG   = 0

reBODY =re.compile( r'<body.*?>([\s\S]*?)<\/body>', re.I)
reCOMM = r'<!--.*?-->'
reTRIM = r'<{0}.*?>([\s\S]*?)<\/{0}>'
reTAG  = r'<[\s\S]*?>|[ \t\r\f\v]'
reOTH  = r'(&nbsp;)*'
reIMG  = re.compile(r'<img[\s\S]*?src=[\'|"]([\s\S]*?)[\'|"][\s\S]*?>')

class Extractor():
    def __init__(self, url = "", blockSize=3, timeout=5, image=False):
        self.url       = url
        self.blockSize = blockSize
        self.timeout   = timeout
        self.saveImage = image
        self.rawPage   = ""
        self.ctexts    = []
        self.cblocks   = []

    def getRawPage(self):
        try:
            resp = req.get(self.url, timeout=self.timeout)
        except Exception as e:
            raise e

        if DBUG: print(resp.encoding)

        resp.encoding = "gbk"

        return resp.status_code, resp.text

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
            self.cblocks = list(map(lambda x,y: x+y, self.textLens[i : lines-1-self.blockSize+i], self.cblocks))

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
        '''删除特定组合的内容'''
        lists = ("（快捷键←）上一章|返回目录|加入书签|推荐本书|返回书页|下一章（快捷键→）",
                 "投推荐票回目录标记书签"
                 )
        for n in lists:
            try:
                self.text = self.text[:self.text.index(n)]
            except BaseException:
                continue
            else:
                break


    def getContext(self):
        code, self.rawPage = self.getRawPage()
        try:
            self.body = re.findall(reBODY, self.rawPage)[0]
        except BaseException:
            self.body = self.rawPage
        if DBUG: print(code, self.rawPage)

        if self.saveImage:
            self.processImages()
        self.processTags()
        self.text = self.processBlocks()
        self.processText()
        return self.text
        # print(len(self.body.strip("\n")))


if __name__ == '__main__':
    ext = Extractor(url="http://www.52dsm.com/chapter/6712/3284687.html", blockSize=5, image=False)
    print(ext.getContext())