from django.urls import path
from rest_framework import routers

from pengadaan import viewsets as v

router = routers.SimpleRouter()
router.register(r"pengadaan/project", v.AcquisitionProjectViewSet)
router.register(r"pengadaan/milestone", v.AcquisitionMilestoneViewSet)
router.register(r"pengadaan/parcel", v.AcquisitionParcelViewSet)
router.register(r"pengadaan/party", v.EntitledPartyViewSet)
router.register(r"pengadaan/survey", v.ParcelSurveyViewSet)
router.register(r"pengadaan/announcement", v.AnnouncementViewSet)
router.register(r"pengadaan/valuation", v.ValuationViewSet)
router.register(r"pengadaan/deliberation", v.DeliberationViewSet)
router.register(r"pengadaan/deliberation_result", v.DeliberationResultViewSet)
router.register(r"pengadaan/objection", v.ObjectionViewSet)
router.register(r"pengadaan/consignment", v.ConsignmentViewSet)
router.register(r"pengadaan/compensation", v.CompensationViewSet)
router.register(r"pengadaan/payment", v.CompensationPaymentViewSet)
router.register(r"pengadaan/rights_release", v.RightsReleaseViewSet)
router.register(r"pengadaan/handover", v.HandoverViewSet)
router.register(r"pengadaan/household", v.AffectedHouseholdViewSet)
router.register(r"pengadaan/document", v.AcquisitionDocumentViewSet)
router.register(r"pengadaan/holiday", v.HolidayViewSet)
router.register(r"pengadaan/deadline_rule", v.DeadlineRuleViewSet)

urlpatterns = router.urls + [
    path("pengadaan/deadlines/", v.DeadlinesView.as_view(), name="pengadaan-deadlines"),
    path("pengadaan/dashboard/", v.DashboardView.as_view(), name="pengadaan-dashboard"),
    path("pengadaan/choices/", v.ChoicesView.as_view(), name="pengadaan-choices"),
    path("pengadaan/workdays/", v.WorkdaysView.as_view(), name="pengadaan-workdays"),
]
