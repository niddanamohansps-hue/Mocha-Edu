"""
Importing a school's existing data (core/bulk_import.py):

- GET  /api/imports/<kind>/template/   Excel template with an example row and a "How to fill" sheet
- POST /api/imports/<kind>/            multipart {file, confirm}: checks every row; without confirm=true
                                       nothing is saved and a preview is returned; with it, everything is
                                       saved in one go, or nothing when any row has a problem.

kinds: students (add_student), staff (add_staff), opening-fees (manage_fee_structures).
"""
from django.http import HttpResponse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import log_action
from roles.permissions import HasPermission

from .bulk_import import PREVIEW_ROWS, ImportFileError, read_rows, template_xlsx


def _importers():
    from fees import bulk_import as fees_import
    from staff import bulk_import as staff_import
    from students import bulk_import as students_import

    return {
        "students": (students_import, "add_student", "Students", getattr(students_import, "NOTES", [])),
        "staff": (staff_import, "add_staff", "Staff", []),
        "opening-fees": (fees_import, "manage_fee_structures", "Opening fees", []),
    }


class _ImportBase(APIView):
    def initial(self, request, *args, **kwargs):
        self.importer = _importers().get(kwargs.get("kind"))
        super().initial(request, *args, **kwargs)

    def get_permissions(self):
        importer = _importers().get(self.kwargs.get("kind"))
        codename = importer[1] if importer else "add_student"
        return [IsAuthenticated(), HasPermission(codename)]


class ImportTemplateView(_ImportBase):
    def get(self, request, kind):
        if self.importer is None:
            return Response({"error": "Unknown import."}, status=status.HTTP_404_NOT_FOUND)
        module, _, title, notes = self.importer
        response = HttpResponse(
            template_xlsx(title, module.COLUMNS, notes),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="edusekai-{kind}-template.xlsx"'
        return response


class ImportView(_ImportBase):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, kind):
        if self.importer is None:
            return Response({"error": "Unknown import."}, status=status.HTTP_404_NOT_FOUND)
        module, _, title, _ = self.importer
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"error": "Choose the filled template to upload."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            rows = read_rows(upload, module.COLUMNS)
        except ImportFileError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        checked = module.check(rows)
        body = {
            "rows": len(checked.rows),
            "errors": sorted(checked.errors, key=lambda e: e["row"])[:500],
            "error_count": len(checked.errors),
            "preview": [module.preview(r) for r in checked.rows[:PREVIEW_ROWS]],
            "saved": 0,
        }
        confirm = str(request.data.get("confirm", "")).lower() in ("true", "1", "yes")
        if checked.errors or not confirm:
            return Response(body, status=status.HTTP_200_OK if not checked.errors else status.HTTP_400_BAD_REQUEST)
        try:
            body["saved"] = module.save(checked.rows)
        except ValidationError as exc:  # e.g. the plan's student limit
            detail = exc.detail.get("error") if isinstance(exc.detail, dict) else exc.detail
            return Response({**body, "error": str(detail[0] if isinstance(detail, list) else detail)},
                            status=status.HTTP_400_BAD_REQUEST)
        log_action(request, action=f"import_{kind.replace('-', '_')}", model_name=title, object_id=None,
                   changes={"file": upload.name[:100], "rows": body["saved"]})
        return Response(body, status=status.HTTP_201_CREATED)
