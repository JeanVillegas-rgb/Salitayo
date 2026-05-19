"""
Seed Word Proficiency vocabulary (English and/or Filipino).

  python manage.py migrate
  python manage.py seed_words --email user@example.com
  python manage.py seed_words --email user@example.com --locale fil
  python manage.py seed_words --email user@example.com --locale both
  python manage.py seed_words --email user@example.com --clear --locale both
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.migrations.recorder import MigrationRecorder

from profiles.models import User
from system.models import WordState
from system.seed_vocabulary import SEED_VOCABULARY, build_seed_entries
from system.services import import_word_list, language_column_ready, sync_user_pos_tags

LANGUAGE_MIGRATION = "0004_wordfeatures_language"


def _language_migration_applied() -> bool:
    return MigrationRecorder.Migration.objects.filter(
        app="system",
        name=LANGUAGE_MIGRATION,
    ).exists()


class Command(BaseCommand):
    help = "Seed English and/or Filipino word proficiency vocabulary for a user"

    def add_arguments(self, parser):
        parser.add_argument("--email", type=str, required=True)
        parser.add_argument(
            "--locale",
            type=str,
            choices=["en", "fil", "both"],
            default="both",
            help="Which vocabulary to import (default: both)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete this user's word library before seeding",
        )

    def _ensure_language_schema(self):
        if language_column_ready():
            return
        if not _language_migration_applied():
            self.stdout.write("Applying database migration for bilingual words…")
            call_command("migrate", "system", verbosity=1)
        if not language_column_ready():
            raise SystemExit(
                "Missing column system_wordfeatures.language. "
                "Run: python manage.py migrate"
            )

    def handle(self, *args, **options):
        self._ensure_language_schema()

        user = User.objects.get(email=options["email"])
        locale = options["locale"]
        locales = list(SEED_VOCABULARY.keys()) if locale == "both" else [locale]

        if options["clear"]:
            deleted, _ = WordState.objects.filter(user_id=user.id).delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted} related row(s) for user."))

        total_created = 0
        total_skipped = 0
        for loc in locales:
            entries = build_seed_entries(loc)
            result = import_word_list(user.id, entries)
            total_created += result["created"]
            total_skipped += result["already_known"]
            self.stdout.write(
                self.style.SUCCESS(
                    f"[{loc}] created={result['created']} skipped={result['already_known']} "
                    f"(input={result['total_input']})"
                )
            )

        sync_user_pos_tags(user.id)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done — {total_created} new words, {total_skipped} already in library."
            )
        )
