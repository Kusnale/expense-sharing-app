from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Accounts system
    path('accounts/', include('features.accounts.urls')),

    # Expenses main app
    path('', include('features.expenses.urls')),
]
