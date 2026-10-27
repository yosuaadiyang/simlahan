"""Cetak panduan peran (Markdown) dari users.role_guide.

cd backend && python manage.py panduan_peran > ../docs/panduan-peran.md
"""

from django.core.management.base import BaseCommand

from users.role_guide import render_markdown


class Command(BaseCommand):
    help = "Cetak panduan peran SimLahan dalam format Markdown"

    def handle(self, *args, **options):
        self.stdout.write(render_markdown(), ending="")
