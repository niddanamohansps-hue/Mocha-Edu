# Parent Portal has no domain models of its own. It is a read-only
# consumer layer over families.StudentParentRelation and the existing
# attendance/timetable/examinations models - see services.py for the
# authorization logic and views.py for the endpoints.
