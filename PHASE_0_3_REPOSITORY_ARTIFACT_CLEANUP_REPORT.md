# Phase 0.3 — Repository Artifact Cleanup Report

## 1. Artifact Identified
- **Filename:** `Fianl_Year_Project.pdf`
- **Location (removed):** `backend/submissions/2026/01/`
- **File type:** PDF document
- **Approximate size:** 3.8 MB (3,998,713 bytes)
- **Git tracked:** Yes, committed at `HEAD`. Content hash `1cf73e1d7c82a57613883347a579b8dcdb7e7f05`.
- **Content:** not opened or reproduced. Identification relies on the filename, its `year/month` upload-style location, and the earlier audit's classification as a student project file.

## 2. Why It Was Removed
Repository inspection showed the file was not an application dependency:
- `backend/submissions/` is not a Django app and is not listed in `INSTALLED_APPS`.
- `MEDIA_ROOT` is `backend/media`. Runtime uploads for `AssignmentSubmission.submission_file` are written under `media/`, not `backend/submissions/`, so the directory is not a storage path.
- The filename appears in no code, test, migration, or configuration. It appears only in this project's own analysis documents.
- No database record references it (checked in every tenant schema).

The file is a student project document committed by mistake, not a required asset.

## 3. Reference Check

| Area | Result |
|---|---|
| Backend Python code | No reference to the filename |
| Django management commands | No reference |
| Tests | No reference |
| Migrations | No reference to the filename. `course_content` migrations reference the `submissions/%Y/%m/` upload path only, which is a generic path template |
| Database records | None across all tenant schemas |
| Frontend code | No reference to the filename. The hook comment about "submissions" is unrelated |
| README / documentation | No reference to the filename |
| Deployment / CI / Docker | No reference |

## 4. Directory Check
`backend/submissions/` had no legitimate purpose:
- It is not a Python package, app, or module.
- It is not a runtime storage path (`MEDIA_ROOT` is `backend/media`).
- Once the file was removed, the directory held only empty `2026/01/` folders. Git does not track empty directories, so no `.gitkeep` is needed.

The empty `2026/01`, `2026`, and `submissions` folders were removed with `rmdir`, which fails on any non-empty directory. This was a safe, empty-only removal.

## 5. Files Removed
Only one file was removed:
- `backend/submissions/2026/01/Fianl_Year_Project.pdf`

Plus the three empty directories above, which contained nothing else.

## 6. Other Potential Artifacts (NOT removed — future cleanup candidates)
A limited scan of tracked documents found:

1. **`backend/course_content/2026/01/Fianl_Year_Project.pdf`** — a byte-for-byte identical copy of the removed file, tracked by Git at the same size (3,998,713 bytes). It is under `course_content/`, not `submissions/`, so it was outside this phase's scope and was left in place. It is a strong candidate for the next cleanup pass, after confirming no `CourseContent.file` records reference it.
2. **`backend/course_content/2026/01/Screen-Recording.webm`** — a screen recording (~4.5 MB) in the same upload-style folder. It looks like a personal/project artifact. Its Git-tracked status was not verified in this phase.

Both are listed for review only. Neither was removed or modified.

**Recommendation:** add `backend/submissions/` and `backend/course_content/20*/` to ignore rules, or move upload test data to `backend/media/`, which is already gitignored (`backend/.gitignore:20: media/`). This prevents recurrence. It was not done in this phase because it changes repository configuration beyond the scope of the artifact removal.

## 7. Validation
```
python manage.py check
System check identified no issues (0 silenced).
```
**Result: PASS.**

No test suite was run. This is a repository-artifact removal, so no application code changed. The `course_content` file-reference scan confirmed no database record points at the removed file.

## 8. Database
No database changes.

## 9. Migrations
No migrations.

## 10. Git
- **No commit.** No push.
- **No staging.** The deletion is an unstaged working-tree change (`git status` shows ` D`), so the change is not staged.
- `git status --short` after the change shows exactly one new change from this phase, the deletion `D backend/submissions/2026/01/Fianl_Year_Project.pdf`.
- All pre-existing working-tree changes were preserved: Phase 0.1 and 0.2 changes, the analysis report, and the Phase 0.1/0.2 reports.
- No destructive git commands were run.
