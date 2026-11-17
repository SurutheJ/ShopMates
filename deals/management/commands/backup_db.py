import os
import sqlite3

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    help = 'Save a dated copy of the SQLite database (never overwrites). Run it by hand or from a daily task.'

    def add_arguments(self, parser):
        parser.add_argument('--to', default=str(settings.BASE_DIR / 'backups'), help='Folder for the copy.')

    def handle(self, *args, **options):
        folder = options['to']
        os.makedirs(folder, mode=0o700, exist_ok=True)
        stamp = timezone.localtime().strftime('%Y%m%d-%H%M%S')
        path = os.path.join(folder, f'db-{stamp}.sqlite3')
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)   # fails if the file exists
        except FileExistsError:
            raise CommandError(f'{path} already exists; not overwriting it. Try again in a second.')
        os.close(fd)
        connection.ensure_connection()
        target = sqlite3.connect(path)
        try:
            connection.connection.backup(target)   # SQLite's own online backup: safe while the site is running
        finally:
            target.close()
        self.stdout.write(f'Backup written to {path}')
