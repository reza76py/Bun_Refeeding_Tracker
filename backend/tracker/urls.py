from django.urls import path, re_path

from tracker import clock_views, views

urlpatterns = [
    # Auth
    path("auth/csrf/", views.CsrfView.as_view()),
    path("auth/login/", views.login_view),
    path("auth/logout/", views.logout_view),
    path("auth/me/", views.me_view),
    # Stores
    path("stores/", views.StoreListView.as_view()),
    path("stores/<int:pk>/", views.StoreDetailView.as_view()),
    # Aisles & bays
    path("aisles/", views.AisleListView.as_view()),
    path("aisles/<int:pk>/", views.AisleDetailView.as_view()),
    path("aisles/<int:aisle_id>/bays/", views.BayListView.as_view()),
    path("bays/<int:pk>/", views.BayDetailView.as_view()),
    path("aisles/<int:aisle_id>/cages/", views.AisleCageListView.as_view()),
    path("aisle-cages/<int:pk>/", views.AisleCageDetailView.as_view()),
    path("catalogue/summary/", views.CatalogueSummaryView.as_view()),
    # Today: % fed per cage per date
    path("feed/summary/", views.FeedSummaryView.as_view()),
    path("feed/", views.FeedSetView.as_view()),
    # Clock: real start / end sessions per cage (trailing slash optional)
    path("clock/summary/", clock_views.ClockSummaryView.as_view()),
    re_path(r"^clock/start/?$", clock_views.ClockStartView.as_view()),
    re_path(r"^clock/end/?$", clock_views.ClockEndView.as_view()),
    re_path(r"^clock/cancel/?$", clock_views.ClockCancelView.as_view()),
    re_path(r"^clock/manual/?$", clock_views.ClockManualView.as_view()),
    path("clock/export.csv", clock_views.ClockExportView.as_view()),
    # Assumptions
    path("assumptions/", views.AssumptionListCreateView.as_view()),
    path("assumptions/active/", views.ActiveAssumptionView.as_view()),
    # Calculator
    path("calculator/preview/", views.CalculatorPreviewView.as_view()),
    # Work days & cages
    path("workdays/", views.WorkDayListCreateView.as_view()),
    path("workdays/<int:pk>/", views.WorkDayDetailView.as_view()),
    path("workdays/<int:work_day_id>/cages/", views.CageCreateView.as_view()),
    path("cages/<int:pk>/", views.CageDetailView.as_view()),
    # Dashboard & reports
    path("dashboard/summary/", views.DashboardSummaryView.as_view()),
    path("reports/summary/", views.ReportsSummaryView.as_view()),
]
