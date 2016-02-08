import unittest
import os
import io
import re
import six
import json
import logging

import signac.contrib

if six.PY2:
    logging.basicConfig(level=logging.WARNING)
    from tempdir import TemporaryDirectory
else:
    from tempfile import TemporaryDirectory


SIGNAC_ACCESS_MODULE = """import os
import re

import signac.contrib

RE_TXT = ".*a_(?P<a>\d)\.txt"

class Crawler(signac.contrib.RegexFileCrawler):
    tags = {'test1', 'test2'}

Crawler.define(RE_TXT, signac.contrib.formats.TextFile)

def get_crawlers(root):
    return {'main':  Crawler(os.path.join(root, '.'))}
"""

class TestFormat(object):
    def read(self):
        assert 0

    def close(self):
        assert 0


class TestGrid(object):
    name = 'inmemorytestgrid'
    files = dict()

    class FileExistsError(IOError):
        pass
    FileNotFoundError = KeyError

    class _Writer(io.BytesIO):

        def __init__(self, cache, file_id):
            self.cache = cache
            self.file_id = file_id

        def close(self):
            self.cache[self.file_id] = self.getvalue()
            super(TestGrid._Writer, self).close()

    def __init__(self, _id):
        self._id = _id

    def config(self):
        return {'id': self._id}

    @classmethod
    def from_config(cls, config):
        return TestGrid(_id=config['id'])

    def new_file(self, mode='wb', **kwargs):
        _id = kwargs['_id']
        cache = self.files.setdefault(self._id, dict())
        if _id in cache:
            raise self.FileExistsError(_id)
        if mode == 'wb':
            return self._Writer(cache, _id)
        else:
            raise ValueError(mode)

    def get(self, file_id, mode='r'):
        cache = self.files[self._id]
        buf = cache[file_id]
        if mode == 'r':
            return io.StringIO(buf.decode())
        elif mode == 'rb':
            return io.BytesIO(buf)
        else:
            raise ValueError(mode)


class CrawlerBaseTest(unittest.TestCase):

    def setUp(self):
        self._tmp_dir = TemporaryDirectory(prefix='signac_')
        self.addCleanup(self._tmp_dir.cleanup)

    def setup_project(self):
        def fn(name):
            return os.path.join(self._tmp_dir.name, name)
        with open(fn('a_0.txt'), 'w') as file:
            file.write('{"a": 0}')
        with open(fn('a_1.txt'), 'w') as file:
            file.write('{"a": 1}')
        with open(fn('signac_access.py'), 'w') as module:
            module.write(SIGNAC_ACCESS_MODULE)

    def test_regex_file_crawler_pre_compiled(self):
        self.setup_project()

        crawler = signac.contrib.RegexFileCrawler(root=self._tmp_dir.name)
        regex = re.compile(".*a_(?P<a>\d)\.txt")
        crawler.define(regex, TestFormat)
        no_find = True
        for doc_id, doc in crawler.crawl():
            no_find = False
            self.assertEqual(doc_id, doc['_id'])
            ffn = os.path.join(doc['root'], doc['filename'])
            m = regex.match(ffn)
            self.assertIsNotNone(m)
            self.assertTrue(os.path.isfile(ffn))
            with open(ffn) as file:
                doc2 = json.load(file)
                self.assertEqual(doc2['a'], doc['a'])
        self.assertFalse(no_find)

    def test_regex_file_crawler(self):
        self.setup_project()

        crawler = signac.contrib.RegexFileCrawler(root=self._tmp_dir.name)
        pattern = ".*a_(?P<a>\d)\.txt"
        regex = re.compile(pattern)
        crawler.define(pattern, TestFormat)
        no_find = True
        for doc_id, doc in crawler.crawl():
            no_find = False
            self.assertEqual(doc_id, doc['_id'])
            ffn = os.path.join(doc['root'], doc['filename'])
            m = regex.match(ffn)
            self.assertIsNotNone(m)
            self.assertTrue(os.path.isfile(ffn))
            with open(ffn) as file:
                doc2 = json.load(file)
                self.assertEqual(doc2['a'], doc['a'])
        self.assertFalse(no_find)

    def test_master_crawler(self):
        self.setup_project()
        crawler = signac.contrib.MasterCrawler(root=self._tmp_dir.name)
        crawler.tags = {'test1'}
        no_find = True
        for doc_id, doc in crawler.crawl():
            no_find = False
            self.assertEqual(doc_id, doc['_id'])
            ffn = os.path.join(doc['root'], doc['filename'])
            self.assertTrue(os.path.isfile(ffn))
            with open(ffn) as file:
                doc2 = json.load(file)
                self.assertEqual(doc2['a'], doc['a'])
            no_data = True
            for data in signac.contrib.fetch(doc):
                no_data = False
                self.assertEqual(signac.contrib.formats.TextFile, type(data))
                data.close()
            self.assertFalse(no_data)
        self.assertFalse(no_find)

    def test_master_crawler_tags(self):
        self.setup_project()
        crawler = signac.contrib.MasterCrawler(root=self._tmp_dir.name)
        self.assertEqual(0, len(list(crawler.crawl())))
        crawler.tags = None
        self.assertEqual(0, len(list(crawler.crawl())))
        crawler.tags = {}
        self.assertEqual(0, len(list(crawler.crawl())))
        crawler.tags = {'nomatch'}
        self.assertEqual(0, len(list(crawler.crawl())))
        crawler.tags = {'test1'}
        self.assertEqual(2, len(list(crawler.crawl())))
        crawler.tags = {'test2'}
        self.assertEqual(2, len(list(crawler.crawl())))
        crawler.tags = {'test1', 'test2'}
        self.assertEqual(2, len(list(crawler.crawl())))
        crawler.tags = {'test1', 'bs'}
        self.assertEqual(2, len(list(crawler.crawl())))
        crawler.tags = {'test2', 'bs'}
        self.assertEqual(2, len(list(crawler.crawl())))
        crawler.tags = {'test1', 'test2', 'bs'}
        self.assertEqual(2, len(list(crawler.crawl())))

    def test_custom_grid(self):
        self.setup_project()
        write_grid = TestGrid('custom_grid')
        read_grid = TestGrid('custom_grid')
        bad_grid = TestGrid('bad')
        crawler = signac.contrib.MasterCrawler(
            root=self._tmp_dir.name,
            link_local=False,
            grids=(write_grid,))
        crawler.tags = {'test1'}
        index = {_id: doc for _id, doc in crawler.crawl()}
        self.assertEqual(len(index), 2)
        check = list()
        for _id, doc in index.items():
            for data in signac.contrib.fetch(doc, grids=(read_grid, )):
                m = json.load(data)
                self.assertTrue('a' in m)
                check.append(m)
        self.assertEqual(len(check), 2)
        check = list()
        for _id, doc in index.items():
            for data in signac.contrib.fetch(doc, grids=(bad_grid, read_grid)):
                m = json.load(data)
                self.assertTrue('a' in m)
                check.append(m)
        self.assertEqual(len(check), 2)
        for _id, doc in index.items():
            with self.assertRaises(IOError):
                signac.contrib.fetch_one(doc, grids=[])
        for _id, doc in index.items():
            with self.assertRaises(IOError):
                signac.contrib.fetch_one(doc, grids=(bad_grid,))


if __name__ == '__main__':
    unittest.main()
