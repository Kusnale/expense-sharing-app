from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

  
from features.expenses.models import Event 
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

import json

def home(request):
    return render(request, "accounts/home.html")

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Remember me: if unchecked, session will expire at browser close
            if not request.POST.get('remember'):
                request.session.set_expiry(0)
            return redirect("dashboard")
        else:
            messages.error(request, "Invalid username/email or password.")
            return redirect("login")
    return render(request, "accounts/login.html")


def signup_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        p1 = request.POST.get("password1", "")
        p2 = request.POST.get("password2", "")
        if not username or not email or not p1 or not p2:
            messages.error(request, "All fields are required.")
            return redirect("signup")
        if p1 != p2:
            messages.error(request, "Passwords do not match.")
            return redirect("signup")
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect("signup")
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already used. Please log in or use another email.")
            return redirect("signup")
        user = User.objects.create_user(username=username, email=email, password=p1)
        user.is_active = True
        user.save()
        messages.success(request, "Account created — you can now log in.")
        return redirect("login")
    return render(request, "accounts/signup.html")


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "Logged out.")
    return redirect("login")


# Dashboard page (after login)
def dashboard_view(request):
    return render(request, 'accounts/dashboard.html')




