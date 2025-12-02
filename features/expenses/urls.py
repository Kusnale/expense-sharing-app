
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .views import profile_settings, update_upi
from . import views

urlpatterns = [
    # Home page
    path("", views.home, name="home"),

    # Dashboard
    path("dashboard/", views.dashboard, name="dashboard"),

    # Event CRUD
    path('event/add/', views.add_event, name='add_event'),
    path('event/<int:event_id>/', views.event_detail, name='event_detail'),
    path('event/<int:event_id>/edit/', views.edit_event, name='edit_event'),
    path('event/<int:event_id>/delete/', views.delete_event, name='delete_event'),

    # Members
    path('event/<int:event_id>/members/add/', views.add_member, name='add_member'),
    path('event/<int:event_id>/members/remove/<int:member_id>/', views.remove_member, name='remove_member'),

    # Expenses
    path('expense/add/<int:event_id>/', views.add_expense, name='add_expense'),
    path('expense/<int:expense_id>/edit/', views.edit_expense, name='edit_expense'),
    path('expense/<int:expense_id>/delete/', views.delete_expense, name='delete_expense'),

    # Payments and reminders
    path('event/<int:event_id>/pay/', views.pay_event, name='pay_event'),
    path('event/<int:event_id>/settle/', views.settle_payment, name='settle_payment'),
    path('event/<int:event_id>/send-reminder/', views.send_reminder, name='send_reminder'),

    # Profile / UPI
    path("profile/", views.profile, name="profile"),
    path("update-upi/", views.update_upi, name="update_upi"),

    # Other features
    path('send-email/', views.send_email_view, name='send_email'),
    path('notes/', views.notes, name='notes'),
    path('todo/', views.todo_list, name='todo_list'),
    path('todo/<int:todo_id>/delete/', views.delete_todo, name='todo_delete'),
    path('upi/success/', views.upi_success, name='upi_success'),

    # Invites
    path('event/<int:event_id>/invite/', views.invite_friend, name='invite_friend'),
    path('join_event/<int:event_id>/<str:token>/', views.join_event_from_invite, name='join_event_from_invite'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)