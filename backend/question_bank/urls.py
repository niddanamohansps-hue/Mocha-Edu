from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import ChapterViewSet, MyScopeView, QuestionViewSet, SubjectReviewerViewSet, TopicViewSet

router = SimpleRouter()
router.register(r"chapters", ChapterViewSet, basename="qb-chapter")
router.register(r"topics", TopicViewSet, basename="qb-topic")
router.register(r"reviewers", SubjectReviewerViewSet, basename="qb-reviewer")
router.register(r"questions", QuestionViewSet, basename="qb-question")

urlpatterns = [
    path("my-scope/", MyScopeView.as_view(), name="qb-my-scope"),
    path("", include(router.urls)),
]
