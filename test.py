# -*- coding: utf-8 -*-

class chinese_to_digits(object):
    def __init__(self):
        self.common_used_numerals = {u'零': 0, u'一': 1, u'二': 2, u'三': 3, u'四': 4, u'五': 5, u'六': 6, u'七': 7, u'八': 8,
                                u'九': 9, u'十': 10, u'百': 100,
                                u'千': 1000, u'万': 10000, u'亿': 100000000}

    def run(self, uchars_cn):
        s=uchars_cn
        if not s :
            return 0
        for i in [u'亿',u'万',u'千',u'百',u'十']:
            if i in s:
                ps=s.split(i)
                lp=self.run(ps[0])
                if lp==0:
                    lp=1
                rp=self.run(ps[1])
                # print(i,s,lp,rp,'\n')
                return lp*self.common_used_numerals.get(i, 0)+rp
        return self.common_used_numerals.get(s[-1], 0)

# c2d = chinese_to_digits()
# print(c2d.run('第三十三章'))