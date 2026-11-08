"""
EduSekai Admissions Celery Background Tasks

Handles asynchronous fail-closed antivirus scanning for admission document uploads.
Operates within tenant schema context.
"""

import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django_tenants.utils import schema_context

from .models import AdmissionDocument, AdmissionActivityLog
from .antivirus import scan_file_for_malware

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def scan_admission_document_task(self, schema_name: str, document_id: str):
    """
    Asynchronous Celery task that inspects an uploaded admission document for malware.
    - Operates within the tenant's PostgreSQL schema context.
    - Idempotent: skips already-processed documents.
    - Fail-closed: marks document as 'error' or 'infected' and keeps it quarantined.
    - Never logs personal data or capability tokens.
    """
    logger.info("Starting antivirus scan task for document %s in schema %s", document_id, schema_name)

    with schema_context(schema_name):
        with transaction.atomic():
            doc = (
                AdmissionDocument.objects.select_for_update()
                .filter(id=document_id)
                .first()
            )

            if not doc:
                logger.warning("Document %s not found in schema %s during scan task.", document_id, schema_name)
                return {"status": "not_found", "document_id": document_id}

            # Idempotency check: if already evaluated as clean or infected, do not duplicate work
            if doc.scan_status in ["clean", "infected"]:
                logger.info("Document %s already scanned with status '%s'. Skipping.", document_id, doc.scan_status)
                return {"status": "already_scanned", "scan_status": doc.scan_status}

            if not doc.file:
                doc.scan_status = "error"
                doc.scan_details = "Document file handle missing from storage."
                doc.scanned_at = timezone.now()
                doc.save(update_fields=["scan_status", "scan_details", "scanned_at"])
                return {"status": "error", "error": "file_missing"}

            try:
                doc.file.open("rb")
            except (FileNotFoundError, OSError) as err:
                logger.error("Could not open file for document %s: %s", document_id, err)
                doc.scan_status = "error"
                doc.scan_details = f"File storage read error: {type(err).__name__}"
                doc.scanned_at = timezone.now()
                doc.save(update_fields=["scan_status", "scan_details", "scanned_at"])
                return {"status": "error", "error": "file_read_error"}

            # Perform malware scan
            is_clean, scan_status, scan_details = scan_file_for_malware(doc.file, filename=doc.file.name)

            doc.scan_status = scan_status
            doc.scan_details = scan_details[:255]
            doc.scanned_at = timezone.now()

            if scan_status == "clean":
                doc.save(update_fields=["scan_status", "scan_details", "scanned_at"])
                logger.info("Document %s passed antivirus scan in schema %s.", document_id, schema_name)
                return {"status": "clean", "document_id": document_id}

            elif scan_status == "infected":
                # Automatically reject infected document and record activity
                doc.verification_status = "rejected"
                doc.rejection_reason = "Automated security alert: uploaded document failed malware inspection."
                doc.save(update_fields=["scan_status", "scan_details", "scanned_at", "verification_status", "rejection_reason"])

                AdmissionActivityLog.objects.create(
                    application=doc.application,
                    action="document_rejected",
                    notes=f"Automated malware quarantine: {doc.title} failed antivirus scan.",
                )

                logger.warning(
                    "SECURITY EVENT: Quarantined infected document %s for application %s in schema %s",
                    document_id,
                    doc.application.application_number,
                    schema_name,
                )
                return {"status": "infected", "document_id": document_id}

            else:
                # Scan error (fail-closed)
                doc.save(update_fields=["scan_status", "scan_details", "scanned_at"])
                logger.error(
                    "Antivirus scan error for document %s in schema %s: %s",
                    document_id,
                    schema_name,
                    scan_details,
                )

                # Retry up to max_retries if transient connection error
                if self.request.retries < self.max_retries:
                    raise self.retry(countdown=5 * (2 ** self.request.retries))

                return {"status": "error", "document_id": document_id, "details": scan_details}



@shared_task
def remind_admission_followups():
    """Daily, in every school: tell each staff member which admission enquiries they should call today or are late.
    Iterates the school schemas itself because a periodic task has no tenant of its own."""
    from django_tenants.utils import get_tenant_model

    from .admissions_followups import remind_followups

    reminded = 0
    for tenant in get_tenant_model().objects.exclude(schema_name="public"):
        with schema_context(tenant.schema_name):
            reminded += remind_followups()["staff"]
    return reminded


@shared_task
def remind_missing_admission_documents():
    """Daily, in every school: nudge families whose application is waiting on documents they have to send."""
    from django_tenants.utils import get_tenant_model

    from .admissions_services import remind_missing_documents

    reminded = 0
    for tenant in get_tenant_model().objects.exclude(schema_name="public"):
        with schema_context(tenant.schema_name):
            reminded += remind_missing_documents()["reminded"]
    return reminded
