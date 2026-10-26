from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .paper_views import BlueprintRuleViewSet, PaperSectionViewSet, PaperViewSet
from .views import ChapterViewSet, MyScopeView, QuestionViewSet, SubjectReviewerViewSet, TopicViewSet

router = SimpleRouter()
router.register(r"chapters", ChapterViewSet, basename="qb-chapter")
router.register(r"topics", TopicViewSet, basename="qb-topic")
router.register(r"reviewers", SubjectReviewerViewSet, basename="qb-reviewer")
router.register(r"questions", QuestionViewSet, basename="qb-question")
router.register(r"papers", PaperViewSet, basename="qb-paper")
router.register(r"paper-sections", PaperSectionViewSet, basename="qb-paper-section")
router.register(r"blueprint-rules", BlueprintRuleViewSet, basename="qb-blueprint-rule")

urlpatterns = [
    path("my-scope/", MyScopeView.as_view(), name="qb-my-scope"),
    path("", include(router.urls)),
]
