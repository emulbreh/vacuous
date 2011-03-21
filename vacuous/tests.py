# -*- coding: utf-8 -*-
import shutil, os, time
from unittest import TestCase

from django.db import models

from vacuous.backends.dulwich import Backend
from vacuous.backends import load_backend
from vacuous.exceptions import FileDoesNotExist
from vacuous.adapters import Adapter


class Foo(models.Model):
    path = models.CharField(max_length=100)
    revision = models.CharField(max_length=50)
    data = models.TextField(blank=True)

    def __unicode__(self):
        return "%s@%s" % (self.path, self.revision)
        
class FooAdapter(Adapter):
    flavor = 'git'
    repo = 'foo.git'
    branch = 'master'
    
    path = Adapter.proxy('path')
    data = Adapter.proxy('data')
    revision = Adapter.proxy('revision')

FooAdapter.register(Foo)

class VcsSyncTests(TestCase):
    TEST_REPO = 'test_foo.git'

    def tearDown(self):
        if os.path.exists(self.TEST_REPO):
            shutil.rmtree(self.TEST_REPO)
        if os.path.exists('foo.git'):
            shutil.rmtree('foo.git')
            
    def test_adapter(self):
        backend = load_backend('git', 'foo.git')
        backend.init_repo()
        
        backend.commit('initial commit', force=True)

        f0 = Foo.objects.create(path='test.txt', data='1234')
        backend.commit('test1')
        time.sleep(1)
        
        f1 = Foo.objects.create(path='foobar/test.txt', data='5678')
        
        f0.path = 'foobar/old.txt'
        f0.save()
        f1.data = '56789'
        f1.save()
        backend.commit('test2')
        time.sleep(1)
        
        f0.delete()
        f1.data = '56789\n01234'
        f1.save()
        backend.commit('test3')
        time.sleep(1)
        
        Foo.objects.all().delete()
        backend.commit('delete all')
        time.sleep(1)

        #for c in backend.history():
        #    print "==" * 30
        #    print c.message
        #    print c.udiff
        #    print
        
        backend.delete_repo()

    def test_basics(self):
        backend = load_backend('git', self.TEST_REPO)
        backend.init_repo()
        
        r0text = u"v1äöü"
        backend.write('test.txt', r0text)
        r0 = backend.commit('initial commit')
        time.sleep(1)
        
        r1text = u"v2ß@œ"
        backend.write('test.txt', r1text)
        r1 = backend.commit('second commit')
        time.sleep(1)
        
        self.assertEqual(backend.read('test.txt'), r1text)
        
        self.assertEqual(backend.read('test.txt', revision=r0), r0text)
        
        self.assertEqual(backend.read('test.txt', revision=r1), r1text)
        
        backend.rename('test.txt', 'foo/bar.txt')
        r2 = backend.commit('third commit')
        time.sleep(1)
        
        self.assertEqual(backend.read('foo/bar.txt'), r1text)
        self.assertRaises(FileDoesNotExist, backend.read, 'test.txt')
        
        self.assertEqual(backend.read('test.txt', revision=r1), r1text)
        
        backend.create_branch('v1')
        backend.write('foo/bar.txt', r0text)
        backend.commit('revert')
        time.sleep(1)

        self.assertEqual(backend.read('foo/bar.txt'), r0text)
        self.assertEqual(backend.read('foo/bar.txt', branch='v1'), r1text)
        
        backend.write('foo/bar.txt', u"test")
        backend.commit('change v1', branch='v1')
        time.sleep(1)

        self.assertEqual(backend.read('foo/bar.txt'), r0text)

        history = backend.history()
        self.assertEqual(len(history), 4)
        #for c in history:
        #    break
        #    print "--" * 30
        #    print "%s: %s %s" % (c.revision, c.commit_time, c.message)
        #    print c.committer, c.commit_time, c.author, c.author_time
        #    print ", ".join(c.paths)
        #    print c.udiff

        history = backend.history('foo/bar.txt')
        self.assertEqual(len(history), 2)
        self.assertEqual(['revert', 'third commit'], [c.message for c in history])
        
        self.assertEqual(backend.read('foo/bar.txt', branch='v1'), u"test")
        
        backend.rename_branch('v1', 'v2')
        
        self.assertEqual(backend.read('foo/bar.txt', branch='v2'), u"test")
        
        self.assertFalse(backend.has_branch('v1'))
        self.assertTrue(backend.has_branch('v2'))

        backend.delete_branch('v2')
        self.assertFalse(backend.has_branch('v2'))

        backend.delete_repo()
        self.assertFalse(os.path.exists(self.TEST_REPO))
        
        