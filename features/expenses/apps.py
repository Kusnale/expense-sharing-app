from django.apps import AppConfig

class ExpensesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'features.expenses'

    def ready(self):
        import features.expenses.signals
