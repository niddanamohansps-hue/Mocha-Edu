from django.core.management.base import BaseCommand, CommandError

from academics.backfill import DECISIONS, apply_tenant, validate_decisions


class Command(BaseCommand):
    help = "Phase 1.2D: create the approved AcademicYear rows. Dry-run unless --apply is given."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the rows. Omit to dry-run only.")

    def handle(self, *args, **options):
        try:
            validate_decisions()
        except ValueError as exc:
            raise CommandError(str(exc))

        dry_run = not options["apply"]
        for tenant, cfg in DECISIONS.items():
            result, plan = apply_tenant(tenant, cfg, dry_run=dry_run)
            self.stdout.write(f"--- {tenant} ({'dry-run' if dry_run else 'applied'}) ---")
            for action, name in plan:
                self.stdout.write(f"  {action}: {name}")
            if not dry_run:
                self.stdout.write(f"  created={result.created} existing={result.existing}")
