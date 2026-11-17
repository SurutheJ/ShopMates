import os
import sqlite3
import stat
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase


class BackupDbTests(TransactionTestCase):
    # Not TestCase: SQLite cannot back up a database that sits inside the open transaction TestCase wraps around each test.
    def run_backup(self, folder):
        call_command('backup_db', to=folder, stdout=open(os.devnull, 'w'))
        return sorted(Path(folder).glob('db-*.sqlite3'))

    def test_it_writes_a_readable_copy_with_the_current_rows(self):
        get_user_model().objects.create_user('backup_probe', password='x')
        with tempfile.TemporaryDirectory() as folder:
            files = self.run_backup(folder)
            self.assertEqual(len(files), 1)
            copy = sqlite3.connect(files[0])
            try:
                table = get_user_model()._meta.db_table
                rows = copy.execute(f"select count(*) from {table} where username='backup_probe'").fetchone()
            finally:
                copy.close()
            self.assertEqual(rows[0], 1)

    def test_the_file_is_private_to_the_owner(self):
        with tempfile.TemporaryDirectory() as folder:
            (path,) = self.run_backup(folder)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_it_never_overwrites_an_existing_backup(self):
        fixed = datetime(2026, 11, 16, 15, 0, 0)
        with tempfile.TemporaryDirectory() as folder, \
                patch('deals.management.commands.backup_db.timezone.localtime', return_value=fixed):
            self.run_backup(folder)
            (path,) = Path(folder).glob('db-*.sqlite3')
            before = path.read_bytes()
            with self.assertRaises(CommandError):
                self.run_backup(folder)
            self.assertEqual(path.read_bytes(), before)
