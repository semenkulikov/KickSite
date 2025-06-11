from os import PathLike
from typing import Union, Iterable
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'This command deletes all migrations in your project'

    @staticmethod
    def get_migration_paths(root_path: Union[str, PathLike]) -> Iterable[Path]:
        if isinstance(root_path, str):
            root_path = Path(root_path)

        for child in root_path.iterdir():
            if child.is_dir():
                migrations_dir = child / 'migrations'
                if migrations_dir.exists() and migrations_dir.is_dir():
                    for migration_file in migrations_dir.iterdir():
                        if (migration_file.is_file() and
                                migration_file.suffix.strip().lower() == '.py' and
                                migration_file.name != '__init__.py'):
                            yield migration_file.absolute()
            if child.is_file():
                if child.name == 'db.sqlite3':
                    yield child.absolute()

    def handle(self, *args, **options):
        print('Running delete_migrations:')
        for migration_path in self.get_migration_paths(settings.BASE_DIR):
            migration_path.unlink()
            print(f'  Deleting {migration_path}... OK')
