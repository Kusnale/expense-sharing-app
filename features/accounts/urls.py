from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),

    # Optional dashboard inside accounts
    path("dashboard/", views.dashboard_view, name="dashboard"),

    # Home also available here
    path("", views.home, name="home"),
]
