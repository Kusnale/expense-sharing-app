from django.db import models
from django.contrib.auth.models import User
from django.db.models import JSONField

from django.core.validators import MinValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
import secrets


class Event(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_events")
    members = models.ManyToManyField(User, related_name="events")
    created_at = models.DateTimeField(auto_now_add=True)

    def get_per_user_split(self):
        per_user = {}
        expenses = self.expenses.all()

        # 🔹 Step 1: Calculate paid and owed from all expenses
        for expense in expenses:
            paid_by = expense.paid_by.username
            members = expense.members_involved.all()
            split_amount = expense.amount / len(members) if members else 0

            # Add paid amount
            per_user.setdefault(paid_by, {'paid': 0, 'share': 0, 'balance': 0})
            per_user[paid_by]['paid'] += expense.amount

            # Add each member's share
            for member in members:
                username = member.username
                per_user.setdefault(username, {'paid': 0, 'share': 0, 'balance': 0})
                per_user[username]['share'] += split_amount
 
        # 🔹 Step 2: Apply recorded payments (cash / UPI)
        payments = self.payments.all()
        for payment in payments:
            payer = payment.payer.username
            receiver = payment.receiver.username
            amount = float(payment.amount)

            per_user.setdefault(payer, {'paid': 0, 'share': 0, 'balance': 0})
            per_user.setdefault(receiver, {'paid': 0, 'share': 0, 'balance': 0})

            # Reduce payer’s balance, increase receiver’s
            per_user[payer]['balance'] -= amount
            per_user[receiver]['balance'] += amount

        # 🔹 Step 3: Final balance calculation
        for username, data in per_user.items():
            net = data['paid'] - data['share'] + data['balance']
            data['balance'] = round(net, 2)

        return per_user

    def __str__(self):
        return self.name


class Expense(models.Model):
    SPLIT_CHOICES = [
        ('equal', 'Equally'),
        ('exact', 'Exact Amounts'),
        ('share', 'By Shares'),
        ('reimburse', 'Reimbursement'),
    ]
    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='expenses')
    description = models.CharField(max_length=200)
    amount = models.FloatField(validators=[MinValueValidator(0.01)])
    paid_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses_paid')
    members_involved = models.ManyToManyField(User, related_name='expenses_involved')
    split_type = models.CharField(max_length=10, choices=SPLIT_CHOICES, default='equal')
    exact_amounts = models.JSONField(blank=True, null=True)  # e.g. {"asus": 1000, "shruti": 2000}
    created_at = models.DateTimeField(auto_now_add=True)
    bill_image = models.ImageField(upload_to="bills/", blank=True, null=True)
    def __str__(self):
        return f"{self.description} ({self.amount})"



class ExpenseShare(models.Model):
    expense = models.ForeignKey('Expense', on_delete=models.CASCADE, related_name='shares')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_shares')
    member = models.ForeignKey(User, on_delete=models.CASCADE, related_name='member_shares')
    amount = models.FloatField(default=0)

    def __str__(self):
        return f"{self.member.username} owes {self.amount} for {self.expense.description}"


import uuid


class Payment(models.Model):
    PAYMENT_METHODS = [
        ('UPI', 'UPI'),
        ('CASH', 'Cash'),
    ]
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="payments")
    payer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="made_payments")
    payee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_payments", null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=PAYMENT_METHODS)
    upi_id = models.CharField(max_length=100, blank=True, null=True)
    txn_id = models.CharField(max_length=100, blank=True, null=True)  
    status = models.CharField(max_length=20, default="Pending")       
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.payer} paid {self.payee} ₹{self.amount} via {self.method}"

class Reminder(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_reminders")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_reminders")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)


class Member(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    upi = models.CharField(max_length=100, blank=True, null=True)
    invite_token = models.CharField(max_length=100, unique=True, blank=True, null=True)
    
    def save(self, *args, **kwargs):
        if not self.invite_token:
            self.invite_token = uuid.uuid4().hex  # generate unique token
        super().save(*args, **kwargs)

class PendingMember(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='pending_members')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invited_members')

    def __str__(self):
        return f"{self.name} ({self.email}) - {self.event.name}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    upi = models.CharField(max_length=255, blank=True, null=True)  # field name: upi

    def __str__(self):
        return f"{self.user.username}'s profile"




class Todo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Note(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text[:30]







