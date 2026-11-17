from django.core.cache import cache, caches
from django.core.cache.backends.db import DatabaseCache
from django.test import TestCase

from deals import throttle


class SharedThrottleTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_default_cache_is_the_database_so_workers_share_it(self):
        self.assertIsInstance(caches['default'], DatabaseCache)

    def test_a_second_worker_sees_the_same_count(self):
        """Two separate cache objects stand in for two server processes."""
        other_worker = DatabaseCache('django_cache', {})
        self.assertTrue(throttle.allow('t:shared', 2))
        self.assertTrue(throttle.allow('t:shared', 2))
        self.assertEqual(other_worker.get('t:shared'), 2)
        self.assertFalse(throttle.allow('t:shared', 2))

    def test_limit_is_per_key(self):
        self.assertTrue(throttle.allow('t:a', 1))
        self.assertFalse(throttle.allow('t:a', 1))
        self.assertTrue(throttle.allow('t:b', 1))
