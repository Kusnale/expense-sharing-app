from django import forms

from .models import UserProfile
from .models import Expense, Event

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            'event',
            'description',
            'amount',
            'paid_by',
            'members_involved',
            'split_type',
            'exact_amounts',
            'bill_image',
        ]
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter description'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter amount'}),
            'paid_by': forms.Select(attrs={'class': 'form-select'}),
            'members_involved': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'split_type': forms.Select(attrs={'class': 'form-select'}),
            'exact_amounts': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional JSON for exact splits'}),
        }

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event Name'}),
        }


class UPIForm(forms.Form):
    upi = forms.CharField(label="UPI ID", max_length=50)
    amount = forms.DecimalField(label="Amount", max_digits=10, decimal_places=2)


class ProfileUPIForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['upi']
        widgets = {
            'upi': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter UPI ID'}),
        }

                                    