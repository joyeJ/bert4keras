#! -*- coding: utf-8 -*-
# 代码合集

import six
import logging
import numpy as np
import re
import sys


_open_ = open
is_py2 = six.PY2

if not is_py2:
    basestring = str


def is_string(s):
    """判断是否是字符串
    """
    return isinstance(s, basestring)


def strQ2B(ustring):
    """全角符号转对应的半角符号
    """
    rstring = ''
    for uchar in ustring:
        inside_code = ord(uchar)
        # 全角空格直接转换
        if inside_code == 12288:
            inside_code = 32
        # 全角字符（除空格）根据关系转化
        elif (inside_code >= 65281 and inside_code <= 65374):
            inside_code -= 65248
        rstring += unichr(inside_code)
    return rstring


def string_matching(s, keywords):
    """判断s是否至少包含keywords中的至少一个字符串
    """
    for k in keywords:
        if re.search(k, s):
            return True
    return False


def convert_to_unicode(text, encoding='utf-8'):
    """字符串转换为unicode格式（假设输入为utf-8格式）
    """
    if is_py2:
        if isinstance(text, str):
            text = text.decode(encoding, 'ignore')
    else:
        if isinstance(text, bytes):
            text = text.decode(encoding, 'ignore')
    return text


def convert_to_str(text, encoding='utf-8'):
    """字符串转换为str格式（假设输入为utf-8格式）
    """
    if is_py2:
        if isinstance(text, unicode):
            text = text.encode(encoding, 'ignore')
    else:
        if isinstance(text, bytes):
            text = text.decode(encoding, 'ignore')
    return text


class open:
    """模仿python自带的open函数，主要是为了同时兼容py2和py3
    """
    def __init__(self, name, mode='r', encoding=None):
        if is_py2:
            self.file = _open_(name, mode)
        else:
            self.file = _open_(name, mode, encoding=encoding)
        self.encoding = encoding

    def __iter__(self):
        for l in self.file:
            if self.encoding:
                l = convert_to_unicode(l, self.encoding)
            yield l

    def read(self):
        text = self.file.read()
        if self.encoding:
            text = convert_to_unicode(text, self.encoding)
        return text

    def write(self, text):
        if self.encoding:
            text = convert_to_str(text, self.encoding)
        self.file.write(text)

    def close(self):
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.close()


class Progress:
    """显示进度，自己简单封装，比tqdm更可控一些
    iterable: 可迭代的对象；
    period: 显示进度的周期；
    steps: iterable可迭代的总步数，相当于len(iterable)
    """
    def __init__(self, iterable, period=1, steps=None, desc=None):
        self.iterable = iterable
        self.period = period
        if hasattr(iterable, '__len__'):
            self.steps = len(iterable)
        else:
            self.steps = steps
        self.desc = desc
        if self.steps:
            self._format_ = u'%s/%s passed' % ('%s', self.steps)
        else:
            self._format_ = u'%s passed'
        if self.desc:
            self._format_ = self.desc + ' - ' + self._format_
        self.logger = logging.getLogger()

    def __iter__(self):
        for i, j in enumerate(self.iterable):
            if (i + 1) % self.period == 0:
                self.logger.info(self._format_ % (i + 1))
            yield j


def parallel_apply(func,
                   iterable,
                   workers,
                   max_queue_size,
                   callback=None,
                   dummy=False):
    """多进程或多线程地将func应用到iterable的每个元素中。
    注意这个apply是异步且无序的，也就是说依次输入a,b,c，但是
    输出可能是func(c), func(a), func(b)。
    参数：
        dummy: False是多进程/线性，True则是多线程/线性；
        callback: 处理单个输出的回调函数；
    """
    if dummy:
        from multiprocessing.dummy import Pool, Queue
    else:
        from multiprocessing import Pool, Queue

    in_queue, out_queue = Queue(max_queue_size), Queue()

    def worker_step(in_queue, out_queue):
        # 单步函数包装成循环执行
        while True:
            d = in_queue.get()
            r = func(d)
            out_queue.put(r)

    # 启动多进程/线程
    pool = Pool(workers, worker_step, (in_queue, out_queue))

    if callback is None:
        results = []

    # 后处理函数
    def process_out_queue():
        out_count = 0
        for _ in range(out_queue.qsize()):
            d = out_queue.get()
            out_count += 1
            if callback is None:
                results.append(d)
            else:
                callback(d)
        return out_count

    # 存入数据，取出结果
    in_count, out_count = 0, 0
    for d in iterable:
        in_count += 1
        while True:
            try:
                in_queue.put(d, block=False)
                break
            except six.moves.queue.Full:
                out_count += process_out_queue()
        if in_count % max_queue_size == 0:
            out_count += process_out_queue()

    while out_count != in_count:
        out_count += process_out_queue()

    pool.terminate()

    if callback is None:
        return results


def sequence_padding(inputs, length=None, padding=0):
    """Numpy函数，将序列padding到同一长度
    """
    if length is None:
        length = max([len(x) for x in inputs])

    outputs = np.array([
        np.concatenate([x, [padding] * (length - len(x))])
        if len(x) < length else x[:length] for x in inputs
    ])
    return outputs


def is_one_of(x, ys):
    """判断x是否在ys之中
    等价于x in ys，但有些情况下x in ys会报错
    """
    for y in ys:
        if x is y:
            return True
    return False


class DataGenerator(object):
    """数据生成器模版
    """
    def __init__(self, data, batch_size=32):
        self.data = data
        self.batch_size = batch_size
        self.steps = len(self.data) // self.batch_size
        if len(self.data) % self.batch_size != 0:
            self.steps += 1

    def __len__(self):
        return self.steps

    def __iter__(self, random=False):
        raise NotImplementedError

    def forfit(self):
        while True:
            for d in self.__iter__(True):
                yield d


class BeamSearch(object):
    """通用beam search基类
    """
    def __init__(self, start_id, end_id, maxlen):
        self.start_id = start_id
        self.end_id = end_id
        self.maxlen = maxlen
        if start_id is None:
            self.first_output_ids = np.empty((1, 0), dtype=int)
        else:
            self.first_output_ids = np.array([[self.start_id]])

    def predict(self, inputs, output_ids, step):
        """用户需自定义递归预测函数
        """
        raise NotImplementedError

    def decode(self, inputs, topk):
        """beam search过程
        """
        inputs = [np.array([i] * topk) for i in inputs]
        output_ids, output_scores = self.first_output_ids, np.zeros(1)
        for step in range(self.maxlen):
            scores = self.predict(inputs, output_ids, step)  # 计算当前得分
            scores = output_scores.reshape((-1, 1)) + scores  # 综合累积得分
            indices = scores.argpartition(-topk, axis=None)[-topk:]  # 仅保留topk
            indices_1 = indices // scores.shape[1]  # 行索引
            indices_2 = (indices % scores.shape[1]).reshape((-1, 1))  # 列索引
            output_ids = np.concatenate([output_ids[indices_1], indices_2], 1)  # 更新输出
            output_scores = np.take_along_axis(scores, indices, axis=None)  # 更新得分
            best_one = output_scores.argmax()  # 取最优
            if indices_2[best_one] == self.end_id:  # 判断是否可以输出
                return output_ids[best_one]
        # 达到长度直接输出
        return output_ids[output_scores.argmax()]


class Hook:
    """注入uniout模块，实现import时才触发
    """
    def __init__(self, module):
        self.module = module

    def __getattr__(self, attr):
        """使得 from bert4keras.backend import uniout
        等效于 import uniout （自动识别Python版本，Python3
        下则无操作。）
        """
        if attr == 'uniout':
            if is_py2:
                import uniout
        else:
            return getattr(self.module, attr)


Hook.__name__ = __name__
sys.modules[__name__] = Hook(sys.modules[__name__])
del Hook
