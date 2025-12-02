from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.mail import send_mail
from django.db.models import Sum
from django.urls import reverse
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.core.serializers.json import DjangoJSONEncoder
from django.core.files.storage import FileSystemStorage
from .models import Event, Expense, ExpenseShare, Payment
from .utils import calculate_settlements, check_event_creator
from decimal import Decimal
import json
signer = TimestampSigner()
from django.conf import settings
from django.utils.crypto import get_random_string
from django.views.decorators.csrf import csrf_exempt
from .forms import UPIForm
from urllib.parse import urlencode 
from django.http import JsonResponse
from .models import Todo, Note
from .models import Event
from django.contrib.auth import login
from django.utils.crypto import get_random_string
from .forms import ProfileUPIForm
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes



def is_event_creator(user, event):
    return user == event.created_by

def check_event_creator(request, event):
    if request.user != event.created_by:
        messages.error(request, "Only the event creator can make changes.")
        return redirect('event_detail', event_id=event.id)
    return None



@login_required
def dashboard(request):
    from features.expenses.models import UserProfile

    profile, created = UserProfile.objects.get_or_create(user=request.user)


    my_events = Event.objects.filter(created_by=request.user)
    my_event_data = []

    for event in my_events:
        expenses = Expense.objects.filter(event=event)
        total_amount = expenses.aggregate(Sum("amount"))["amount__sum"] or 0

        paid_by_user, owed_by_user = {}, {}

        for expense in expenses:
            involved = expense.members_involved.all()
            count = involved.count() or 1
            split = expense.amount / count

            payer = expense.paid_by.username
            paid_by_user[payer] = paid_by_user.get(payer, 0) + expense.amount

            for m in involved:
                owed_by_user[m.username] = owed_by_user.get(m.username, 0) + split

        per_user = {}
        all_users = set(list(paid_by_user.keys()) + list(owed_by_user.keys()))
        for u in all_users:
            paid = paid_by_user.get(u, 0)
            owed = owed_by_user.get(u, 0)
            balance = paid - owed
            per_user[u] = {
                "paid": round(paid, 2),
                "share": round(owed, 2),
                "balance": round(balance, 2)
            }

        my_event_data.append({
            "event": event,
            "expenses": expenses,
            "total_amount": total_amount,
            "per_user": per_user,
            "members": event.members.all(),
        })

 
    group_events = Event.objects.filter(members=request.user).exclude(created_by=request.user)
    group_event_data = []

    for event in group_events:
        expenses = Expense.objects.filter(event=event)
        total_amount = expenses.aggregate(Sum("amount"))["amount__sum"] or 0

        group_event_data.append({
            "event": event,
            "expenses": expenses,
            "total_amount": total_amount,
            "members": event.members.all(),
        })

    return render(request, "expenses/dashboard.html", {
        "profile": profile,
        "my_event_data": my_event_data,
        "group_event_data": group_event_data,
    })
      
def home(request):
    return render(request, "accounts/home.html")

@login_required
def todo_list(request):
    todos = Todo.objects.filter(user=request.user).order_by('-created_at')
    if request.method == 'POST':
        title = request.POST.get('title')
        if title:
            Todo.objects.create(user=request.user, title=title)
        return redirect('todo_list')
    return render(request, 'expenses/todo_list.html', {'todos': todos})

@login_required
def notes(request):
    notes = Note.objects.filter(user=request.user).order_by('-created_at')
    if request.method == 'POST':
        if 'add_note' in request.POST:
            text = request.POST.get('text')
            if text:
                Note.objects.create(user=request.user, text=text)
        elif 'delete_note' in request.POST:
            note_id = request.POST.get('note_id')
            Note.objects.filter(id=note_id, user=request.user).delete()
        return redirect('notes')
    return render(request, 'expenses/notes.html', {'notes': notes})

@login_required
def delete_todo(request, todo_id):
    todo = get_object_or_404(Todo, id=todo_id, user=request.user)
    todo.delete()
    return redirect('todo_list')


@login_required
def pay_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    expenses = Expense.objects.filter(event=event).prefetch_related("shares", "paid_by")
    members = event.members.all()

    per_user = {m.username: {"paid": 0, "share": 0} for m in members}

    for expense in expenses:
        per_user[expense.paid_by.username]["paid"] += expense.amount
        shares = expense.shares.all()
        if shares.exists():
            for share in shares:
                per_user[share.member.username]["share"] += float(share.amount)
        else:
            involved = expense.members_involved.all()
            if involved:
                split = expense.amount / len(involved)
                for m in involved:
                    per_user[m.username]["share"] += split

    balances = {u: round(per_user[u]["paid"] - per_user[u]["share"], 2) for u in per_user}

    # Settlement logic
    debtors = [{"user": u, "amount": -amt} for u, amt in balances.items() if amt < 0]
    creditors = [{"user": u, "amount": amt} for u, amt in balances.items() if amt > 0]
    settlements = []
    for debtor in debtors:
        for creditor in creditors:
            if debtor["amount"] == 0:
                break
            pay_amount = min(debtor["amount"], creditor["amount"])
            if pay_amount > 0:
                settlements.append((debtor["user"], creditor["user"], round(pay_amount, 2)))
                debtor["amount"] -= pay_amount
                creditor["amount"] -= pay_amount

    # ----- Handle POST -----
    if request.method == "POST":
        method = request.POST.get("method")
        receiver_username = request.POST.get("receiver_username")
        amount = Decimal(request.POST.get("amount", "0"))
        upi_id = request.POST.get("upi_id", "")

        try:
            receiver = User.objects.get(username=receiver_username)
        except User.DoesNotExist:
            messages.error(request, "⚠️ Receiver not found.")
            return redirect("pay_event", event_id=event.id)

        Payment.objects.create(
            event=event,
            payer=request.user,
            receiver=receiver,
            amount=amount,
            method=method,
        )

        messages.success(request, f"✅ Payment of ₹{amount} to {receiver.username} via {method.upper()} recorded.")
        return redirect("event_detail", event_id=event.id)

    # Show only user's settlements
    user_settlements = [s for s in settlements if s[0] == request.user.username]
    total_user_owes = sum([s[2] for s in user_settlements])
    all_settled = total_user_owes == 0

    return render(request, "expenses/pay_event.html", {
        "event": event,
        "user_settlements": user_settlements,
        "total_user_owes": total_user_owes,
        "all_settled": all_settled,
    })


# ➕ Add Event
@login_required
def add_event(request):
    if request.method == "POST":
        name = request.POST["name"]
        event = Event.objects.create(name=name, created_by=request.user)
        event.members.add(request.user)
        messages.success(request, f"Event '{name}' created successfully.")
        return redirect("dashboard")
    return render(request, "expenses/add_event.html")

@login_required
def edit_profile(request):
    user = request.user
    profile, created = UserProfile.objects.get_or_create(user=user)

    if request.method == "POST":
        user.email = request.POST.get("email")
        profile.upi_id = request.POST.get("upi_id")  # FIXED FIELD NAME
        user.save()
        profile.save()
        return redirect("dashboard")

    return render(request, "accounts/edit_profile.html", {"profile": profile})



# ✏ Edit Event
@login_required
def edit_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.user != event.created_by:
        messages.error(request, "⚠️ Only the event creator can make changes.")
        return redirect('event_detail', event_id=event.id)

    

    if request.method == "POST":
        event.name = request.POST["name"]
        event.save()
        messages.success(request, f"Event '{event.name}' updated successfully.")
        return redirect("event_detail", event_id=event.id)
    return render(request, "expenses/edit_event.html", {"event": event})


# 🗑 Delete Event
@login_required
def delete_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    # 🚫 Only the event creator can delete
    if request.user != event.created_by:
        messages.error(request, "⚠️ Only the event creator can make changes.")
        return redirect("event_detail", event_id=event.id)

    if request.method == "POST":
        event.delete()
        messages.success(request, "🗑️ Event deleted successfully.")
        return redirect("dashboard")

    # Optional: confirmation page
    return render(request, "expenses/confirm_delete.html", {"event": event})

# 📋 Event Detail
@login_required
def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    expenses = Expense.objects.filter(event=event).prefetch_related(
        "members_involved", "paid_by", "shares"
    )
    members = event.members.all()

    # ---- Total spent ---- #
    total_amount = sum(exp.amount for exp in expenses)

    # ---- Per-user calculations ---- #
    per_user = {m.username: {"paid": 0, "share": 0} for m in members}

    for expense in expenses:
        # Paid amount
        per_user[expense.paid_by.username]["paid"] += expense.amount

        # --- Use ExpenseShare if available (covers exact/share/reimburse) --- #
        shares = expense.shares.all()
        if shares.exists():
            for share in shares:
                per_user[share.member.username]["share"] += float(share.amount)
        else:
            # fallback: equal split
            involved = expense.members_involved.all()
            if involved:
                split = expense.amount / len(involved)
                for m in involved:
                    per_user[m.username]["share"] += split

    # ---- Balances ---- #
    balances = {
        u: round(per_user[u]["paid"] - per_user[u]["share"], 2)
        for u in per_user
    }

    # ---- Multi-person Settlement Calculation ---- #
    debtors = [{"user": u, "amount": -amt} for u, amt in balances.items() if amt < 0]
    creditors = [{"user": u, "amount": amt} for u, amt in balances.items() if amt > 0]

    settlements = []
    for debtor in debtors:
        for creditor in creditors:
            if debtor["amount"] == 0:
                break
            pay_amount = min(debtor["amount"], creditor["amount"])
            if pay_amount > 0:
                settlements.append({
                    "from": debtor["user"],
                    "to": creditor["user"],
                    "amount": round(pay_amount, 2),
                })
                debtor["amount"] -= pay_amount
                creditor["amount"] -= pay_amount

    # ---- Settlement summary lines ---- #
    settlement_summary = []
    seen = set()
    for s in settlements:
        line = f"{s['from']} → {s['to']} : ₹{s['amount']}"
        if line not in seen:
            seen.add(line)
            settlement_summary.append(line)
    if not settlement_summary:
        settlement_summary = ["All settled!"]  # <-- added

    # ---- Pie chart data ---- #
    pie_data = [
        {"name": u, "value": round(per_user[u]["share"], 2)} for u in per_user
    ]

    # ---- Per-user split table ---- #
    per_user_split = [
        {
            "member": u,
            "paid": round(per_user[u]["paid"], 2),
            "share": round(per_user[u]["share"], 2),
            "balance": round(balances[u], 2),
        }
        for u in per_user
    ]

    context = {
        "event": event,
        "expenses": expenses,
        "members": members,
        "total_spent": round(total_amount, 2),
        "pie_data_json": json.dumps(pie_data),
        "per_user": per_user,
        "per_user_split": per_user_split,
        "balances": balances,
        "settlements": settlements,
        "settlement_summary": settlement_summary,
    }

    return render(request, "expenses/event_detail.html", context)



from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
import json
from .models import Event  # adjust if Event is in another app

@login_required
@require_POST  # ensures only POST requests are allowed
def send_reminder(request, event_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON."})

    settlement_line = data.get("settlement_line")
    event = get_object_or_404(Event, id=event_id)

    if not settlement_line or "→" not in settlement_line or ":" not in settlement_line:
        return JsonResponse({"success": False, "message": "Invalid settlement format."})

    # Parse settlement: "Debtor → Creditor : ₹Amount"
    try:
        debtor, rest = settlement_line.split("→")
        creditor, amount = rest.split(":")
        debtor = debtor.strip()
        creditor = creditor.strip()
        amount = amount.strip()
    except ValueError:
        return JsonResponse({"success": False, "message": "Error parsing settlement line."})

    try:
        debtor_user = User.objects.get(username=debtor)
        recipient_email = debtor_user.email
    except User.DoesNotExist:
        return JsonResponse({"success": False, "message": f"No user found for {debtor}."})

    if not recipient_email:
        return JsonResponse({"success": False, "message": f"No email found for {debtor}."})

    try:
        send_mail(
            subject=f"💰 Payment Reminder for {event.name}",
            message=(
                f"Hi {debtor},\n\n"
                f"This is a reminder to pay {amount} to {creditor} for the event '{event.name}'.\n"
                f"Please settle it soon!\n\n"
                f"- Expense Sharing App"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        return JsonResponse({"success": True, "message": f"Reminder sent to {debtor}."})
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Failed to send email: {e}"})

from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt  # or use CSRF token in JS
def send_email_view(request):
    if request.method == 'POST':
        try:
            send_mail(
                'Hello from Django!',
                'This is a test email sent via Gmail SMTP.',
                settings.EMAIL_HOST_USER,
                ['recipient@example.com'],  # change to your target email
                fail_silently=False,
            )
            return JsonResponse({'success': True, 'message': 'Email sent successfully!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@login_required
def settle_payment(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    user = request.user

    # Get all expenses in this event
    expenses = Expense.objects.filter(event=event)
    members = event.members.all()

    # ---- Calculate paid and owed ----
    paid = {m.username: 0 for m in members}
    owed = {m.username: 0 for m in members}

    for exp in expenses:
        shares = ExpenseShare.objects.filter(expense=exp)
        for s in shares:
            owed[s.member.username] += s.amount
        paid[exp.paid_by.username] += exp.amount

    balances = {m: paid[m] - owed[m] for m in paid}

    # ---- Determine receiver ----
    if balances[user.username] < 0:
        owes_amount = abs(balances[user.username])
        receiver_username = max(
            (u for u in balances if balances[u] > 0),
            key=lambda u: balances[u],
            default=None
        )
        receiver_user = User.objects.get(username=receiver_username) if receiver_username else None
    else:
        owes_amount = 0
        receiver_user = None

    # 🧩 Fetch receiver UPI if available
    receiver_upi = (
        receiver_user.profile.upi_id
        if receiver_user and hasattr(receiver_user, "profile") and receiver_user.profile.upi_id
        else None
    )

    # Handle POST
    if request.method == "POST":
        payment_method = request.POST.get("payment_method")

        if payment_method == "UPI":
            if not receiver_upi:
                messages.error(request, f"{receiver_user.username} has not set a UPI ID yet.")
                return redirect("event_detail", event_id=event.id)
            # Redirect to a UPI payment confirmation page
            return render(request, "expenses/upi_payment.html", {
                "event": event,
                "receiver": receiver_user,
                "receiver_upi": receiver_upi,
                "amount": owes_amount,
            })

        elif payment_method == "Cash":
            Payment.objects.create(
                event=event,
                payer=request.user,
                receiver=receiver_user,
                amount=owes_amount,
                method="Cash",
            )
            messages.success(
                request,
                f"✅ Payment of ₹{owes_amount:.2f} to {receiver_user.username} via Cash recorded."
            )
            return redirect("event_detail", event_id=event.id)

    return render(request, "expenses/settle_payment.html", {
        "event": event,
        "user": user,
        "receiver": receiver_user,
        "receiver_upi": receiver_upi,
        "owes_amount": owes_amount,
    })

# ➕ Add Expense
@login_required
def add_expense(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    redirect_response = check_event_creator(request, event)
    if redirect_response:
        return redirect_response

    if request.method == "POST":
        description = request.POST.get("description", "").strip()
        total_amount = float(request.POST.get("amount", 0))
        paid_by = get_object_or_404(User, id=request.POST.get("paid_by"))
        members = User.objects.filter(id__in=request.POST.getlist("members"))

        if not members.exists():
            messages.error(request, "Cannot split expense: no members selected.")
            return redirect('event_detail', event_id=event.id)

        per_person = total_amount / members.count()
        split_type = request.POST.get("split_type", "equal")

        # ✅ Handle bill image upload
        bill_image = request.FILES.get("bill_image")

        # ✅ Create expense
        expense = Expense.objects.create(
            event=event,
            description=description,
            amount=total_amount,
            paid_by=paid_by,
            split_type=split_type,
            bill_image=bill_image,
        )
        expense.members_involved.set(members)
        shares = []

        # ---- SPLIT TYPES ---- #
        if split_type == "equal":
            per_person = total_amount / members.count()
            for m in members:
                shares.append(
                    ExpenseShare(expense=expense, member=m, user=request.user, amount=per_person)
                )

        elif split_type == "exact":
            exact_data = {}
            for m in members:
                exact_val = request.POST.get(f"exact_amount_{m.id}")
                if exact_val:
                    val = float(exact_val)
                    exact_data[m.username] = val
                    shares.append(
                        ExpenseShare(expense=expense, member=m, user=request.user, amount=val)
                    )
            expense.exact_amounts = exact_data  # store exact splits safely

            # sanity check for exact splits
            total_exact = sum(exact_data.values())
            if round(total_exact, 2) != round(expense.amount, 2):
                messages.warning(
                    request,
                    f"⚠️ Exact split total ({total_exact}) doesn’t match total amount ({expense.amount}).",
                )

        elif split_type == "shares":
            total_shares = sum([int(request.POST.get(f"share_{m.id}", 1)) for m in members])
            if total_shares == 0:
                messages.error(request, "Cannot split expense: total shares cannot be zero.")
                return redirect('event_detail', event_id=event.id)

            share_data = {}
            for m in members:
                s = int(request.POST.get(f"share_{m.id}", 1))
                amt = (s / total_shares) * total_amount
                share_data[m.username] = s
                shares.append(
                    ExpenseShare(expense=expense, member=m, user=request.user, amount=amt)
                )
            expense.extra_data = share_data

        elif split_type == "reimburse":
            per_person = total_amount / members.count()
            for m in members:
                shares.append(
                    ExpenseShare(expense=expense, member=m, user=request.user, amount=per_person)
                )

        expense.save()
        ExpenseShare.objects.bulk_create(shares)
        messages.success(request, f"Expense '{description}' added successfully ({split_type} split).")
        return redirect("event_detail", event_id=event.id)

    # GET request → render the form
    return render(request, "expenses/add_expense.html", {
        "event": event,
        "members": event.members.all(),
    })

# ✏ Edit Expense
@login_required
def edit_expense(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id)
    event = expense.event

    # ✅ Only event creator can edit
    if request.user != event.created_by:
        messages.error(request, "You are not authorized to edit this expense.")
        return redirect("event_detail", event_id=event.id)

    if request.method == "POST":
        description = request.POST.get("description", "").strip()
        amount = request.POST.get("amount", "").strip()
        paid_by_id = request.POST.get("paid_by")
        split_type = request.POST.get("split_type", "equal")
        selected_members = request.POST.getlist("members")

        if not description or not amount or not paid_by_id:
            messages.error(request, "⚠️ Please fill in all required fields.")
            return redirect("edit_expense", expense_id=expense.id)

        try:
            amount = float(amount)
        except ValueError:
            messages.error(request, "⚠️ Please enter a valid amount.")
            return redirect("edit_expense", expense_id=expense.id)

        # ✅ Base fields
        expense.description = description
        expense.amount = amount
        expense.paid_by = get_object_or_404(User, id=paid_by_id)
        expense.split_type = split_type

        if "bill_image" in request.FILES:
            expense.bill_image = request.FILES["bill_image"]

        expense.save()

        # 🔄 Clear old shares and recalc
        ExpenseShare.objects.filter(expense=expense).delete()
        members = User.objects.filter(id__in=selected_members)
        shares = []
        exact_data = {}

        # ---------- SPLIT TYPES ----------
        if split_type == "equal":
            per_person = amount / len(members)
            for m in members:
                shares.append(ExpenseShare(expense=expense, member=m, amount=per_person, user=request.user))
            expense.exact_amounts = {}

        elif split_type == "exact":
            total_exact = 0
            for m in members:
                val = request.POST.get(f"exact_amount_{m.id}", "")
                if val:
                    try:
                        val = float(val)
                        total_exact += val
                        exact_data[str(m.id)] = val
                        shares.append(ExpenseShare(expense=expense, member=m, amount=val, user=request.user))
                    except ValueError:
                        continue
            expense.exact_amounts = exact_data
            if round(total_exact, 2) != round(amount, 2):
                messages.warning(request, f"⚠ Exact total ₹{total_exact} ≠ Expense ₹{amount}")

        elif split_type == "percent":
            total_percent = 0
            for m in members:
                val = request.POST.get(f"percent_{m.id}", "")
                if val:
                    try:
                        val = float(val)
                        total_percent += val
                        share_amt = (val / 100) * amount
                        shares.append(ExpenseShare(expense=expense, member=m, amount=share_amt, user=request.user))
                        exact_data[str(m.id)] = val
                    except ValueError:
                        continue
            expense.exact_amounts = exact_data
            if round(total_percent, 2) != 100:
                messages.warning(request, f"⚠ Percent total {total_percent}% ≠ 100%")

        elif split_type == "shares":
            total_shares = sum([int(request.POST.get(f"share_{m.id}", 1)) for m in members])
            for m in members:
                s = int(request.POST.get(f"share_{m.id}", 1))
                share_amt = (s / total_shares) * amount
                exact_data[str(m.id)] = s
                shares.append(ExpenseShare(expense=expense, member=m, amount=share_amt, user=request.user))
            expense.exact_amounts = exact_data

        elif split_type == "reimburse":
            per_person = amount / len(members)
            for m in members:
                shares.append(ExpenseShare(expense=expense, member=m, amount=per_person, user=request.user))
            expense.exact_amounts = {}

        # ✅ Save all new shares
        ExpenseShare.objects.bulk_create(shares)
        expense.save()

        messages.success(request, f"✅ Expense '{description}' updated successfully.")
        return redirect("event_detail", event_id=event.id)

    else:
        # GET request → show existing data in form
        extra_data = expense.exact_amounts or {}
        return render(
            request,
            "expenses/edit_expense.html",
            {
                "expense": expense,
                "event": event,
                "members": event.members.all(),
                "extra_data": extra_data,
            },
        )


@login_required
def delete_expense(request, expense_id):
    # Try to get expense safely
    expense = get_object_or_404(Expense, id=expense_id)
    event = expense.event  # Get the related event

    # 🔐 Only event creator can delete the expense
    if request.user != event.created_by:
        messages.error(request, "⚠️ Only the event creator can make changes.")
        return redirect('event_detail', event_id=event.id)

    # Only allow POST delete for safety
    if request.method == "POST":
        expense.delete()
        messages.success(request, "Expense deleted successfully!")
        return redirect("event_detail", event_id=event.id)

    # Show confirmation page before deleting
    return render(request, "expenses/confirm_delete.html", {"expense": expense, "event": event})

import secrets


@login_required
def add_member(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    # Only event creator allowed
    if request.user != event.created_by:
        messages.error(request, "Only the event creator can add members.")
        return redirect('event_detail', event.id)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()

        if not name:
            messages.error(request, "Name cannot be empty.")
            return redirect('add_member', event.id)

        # Get or create user WITHOUT triggering duplicate key errors
        user, created = User.objects.get_or_create(username=name)

        # If already a member, silently ignore
        if user not in event.members.all():
            event.members.add(user)
            messages.success(request, f"{name} added successfully!")

        return redirect('event_detail', event.id)

    return render(request, "expenses/add_member.html", {"event": event})

def join_event_from_invite(request, event_id, token):
    event = get_object_or_404(Event, id=event_id)

    try:
        profile = UserProfile.objects.get(invite_token=token)
        user = profile.user

        # Add to event
        event.members.add(user)

        # Clear token
        profile.invite_token = None
        profile.save()

        # Login automatically
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)

        messages.success(request, f"Welcome {user.first_name}! You've joined '{event.name}'.")
        return redirect('event_detail', event_id=event.id)

    except UserProfile.DoesNotExist:
        messages.error(request, "Invalid or expired invitation.")
        return redirect('dashboard')


# Delete Member
@login_required
def delete_member(request, event_id, member_id):
    event = get_object_or_404(Event, id=event_id)
    member = get_object_or_404(User, id=member_id)

    if request.method == "POST":
        event.members.remove(member)
        ExpenseShare.objects.filter(expense__event=event, member=member).delete()

        # Recalculate splits for each expense
        for expense in Expense.objects.filter(event=event):
            members = expense.members_involved.all()
            total_amount = expense.amount
            if members.exists():
                per_person = total_amount / members.count()
                ExpenseShare.objects.filter(expense=expense).delete()
                for m in members:
                    ExpenseShare.objects.create(
                        expense=expense,
                        member=m,
                        user=expense.paid_by,
                        amount=per_person
                    )

        # Re-render per-user split and get new total
        split_html = render_to_string("expenses/per_user_split.html", {"event": event})
        total_amount = sum(exp.amount for exp in Expense.objects.filter(event=event))

        return JsonResponse({
            "success": True,
            "split_html": split_html,
            "updated_total": total_amount
        })

    return JsonResponse({"success": False, "error": "Invalid request."})



def join_event(request, event_id, token):
    event = get_object_or_404(Event, id=event_id)
    try:
        profile = UserProfile.objects.get(invite_token=token)
        user = profile.user
        event.members.add(user)
        messages.success(request, f"You have joined {event.name} successfully!")
        return redirect('event_detail', event_id=event.id)
    except UserProfile.DoesNotExist:
        messages.error(request, "Invalid or expired invitation link.")
        return redirect('dashboard')


from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
@login_required
def invite_friend(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    # Only event creator can invite
    if request.user != event.created_by:
        messages.error(request, "⚠️ Only the event creator can invite members.")
        return redirect('event_detail', event_id=event.id)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()

        if not email:
            messages.error(request, "Please enter an email.")
            return redirect('event_detail', event_id=event.id)

        if not name:
            messages.error(request, "Please enter a name.")
            return redirect('event_detail', event_id=event.id)

        # Check if user already exists
        user = User.objects.filter(email=email).first()

        if not user:
            # Create new user with the provided name
            username = (name.replace(" ", "").lower() or email.split('@')[0])[:30]
            tmp_password = User.objects.make_random_password()

            user = User.objects.create(
                username=username,
                email=email,
                first_name=name,
                is_active=True
            )
            user.set_password(tmp_password)
            user.save()
            created = True
        else:
            created = False

        # create profile or update
        profile, _ = UserProfile.objects.get_or_create(user=user)

        profile.invite_token = secrets.token_urlsafe(15)
        profile.save()

        invite_url = request.build_absolute_uri(
            reverse('join_event_from_invite', args=[event.id, profile.invite_token])
        )

        # Email body
        message = f"Hello {name},\n\nYou are invited to join: {event.name}\n\nClick below:\n{invite_url}\n"

        if created:
            message += f"\nYour temporary login details:\nUsername: {user.username}\nPassword: {tmp_password}\n"

        send_mail(
            subject=f"Invitation to join {event.name}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
        )

        messages.success(request, f"Invitation sent to {email}")

        return redirect('event_detail', event_id=event.id)

    return render(request, "expenses/invite_friend.html", {"event": event})


def settle_expenses(per_user):
    debtors = []
    creditors = []

    # Separate debtors and creditors
    for name, data in per_user.items():
        bal = round(data['balance'], 2)
        if bal < 0:
            debtors.append([name, -bal])  # Owes money
        elif bal > 0:
            creditors.append([name, bal])  # Gets money

    i, j = 0, 0
    transactions = []

    while i < len(debtors) and j < len(creditors):
        debtor, owe = debtors[i]
        creditor, get = creditors[j]

        amount = min(owe, get)
        transactions.append((debtor, creditor, amount))

        debtors[i][1] -= amount
        creditors[j][1] -= amount

        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1

    return transactions

def get_per_user_split(event):
    expenses = event.expenses.all()
    per_user = {}

    # First, ensure every user in event is tracked
    all_members = set()
    for expense in expenses:
        all_members.update(expense.members_involved.all())
        all_members.add(expense.paid_by)
    for member in all_members:
        per_user[member.username] = {"paid": 0, "share": 0, "balance": 0}

    # Then process all expenses
    for expense in expenses:
        members = expense.members_involved.all()
        split_type = expense.split_type

        # record payment
        per_user[expense.paid_by.username]["paid"] += expense.amount

        # split logic
        if split_type == "equal":
            share = expense.amount / len(members)
            for member in members:
                per_user[member.username]["share"] += round(share, 2)

        elif split_type == "exact":
            # ✅ use JSON exact_amounts correctly
            if expense.exact_amounts:
                for username, value in expense.exact_amounts.items():
                    if username in per_user:
                        per_user[username]["share"] += round(float(value), 2)
            else:
                # fallback if exact not provided
                share = expense.amount / len(members)
                for member in members:
                    per_user[member.username]["share"] += round(share, 2)

        elif split_type == "shares":
            # (future) Add share ratio logic here
            pass

    # Calculate balances (paid - share)
    for username, data in per_user.items():
        data["balance"] = round(data["paid"] - data["share"], 2)

    return per_user




# ---- Clean Settlement Calculation ---- #
def calculate_settlements(balances):
    debtors = []
    creditors = []
    settlements = []

    for user, balance in balances.items():
        if balance < 0:
            debtors.append({"user": user, "amount": -balance})
        elif balance > 0:
            creditors.append({"user": user, "amount": balance})

    for debtor in debtors:
        for creditor in creditors:
            if debtor["amount"] == 0:
                break
            pay_amount = min(debtor["amount"], creditor["amount"])
            if pay_amount > 0:
                settlements.append({
                    "from": debtor["user"],
                    "to": creditor["user"],
                    "amount": round(pay_amount, 2)
                })
                debtor["amount"] -= pay_amount
                creditor["amount"] -= pay_amount

    return settlements   # ✅ dicts, not strings


@csrf_exempt
def record_payment(request, event_id):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method."})

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON data."})

    payer = request.user
    payee_username = data.get("payee")
    amount = data.get("amount")
    method = data.get("method")
    upi_id = data.get("upi_id", None)

    # ✅ Validate inputs
    if not all([payee_username, amount, method]):
        return JsonResponse({"success": False, "error": "Missing payment data."})

    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return JsonResponse({"success": False, "error": "Event not found."})

    try:
        payee = User.objects.get(username=payee_username)
    except User.DoesNotExist:
        return JsonResponse({"success": False, "error": f"User '{payee_username}' not found."})

    try:
        Payment.objects.create(
            event=event,
            payer=payer,
            payee=payee,
            amount=float(amount),
            method=method,
            upi_id=upi_id if method == "UPI" else None
        )
        return JsonResponse({
            "success": True,
            "message": f"✅ Payment of ₹{amount} to {payee_username} recorded via {method}."
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})





@login_required
def upi_success(request):
    return render(request, "expenses/upi_success.html")


def pay_expense(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id)
    payee_upi = getattr(expense.paid_by.profile, "upi", None)  # Correct field name

    if not payee_upi:
        payee_upi = "Not available"

    amount = expense.amount
    note = f"Expense payment for {expense.event.name}"

    params = {
        "pa": payee_upi,                  # Payee address
        "pn": expense.paid_by.username,   # Payee name
        "am": amount,
        "cu": "INR",
        "tn": note,
    }
    upi_url = "upi://pay?" + urlencode(params)

    return render(request, "expenses/pay.html", {
        "expense": expense,
        "upi_url": upi_url,
        "receiver_upi": payee_upi,  # pass to template for JS popup
    })

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Payment, Event
from django.utils import timezone

@login_required
def upi_success(request):
    """
    Handles UPI redirect after payment and records payment in DB.
    Expects GET params: txn_id, receiver, amount
    """
    txn_id = request.GET.get("txn_id")
    receiver_username = request.GET.get("receiver")
    amount = request.GET.get("amount")
    event_id = request.GET.get("event_id")  # optional if you track event

    if txn_id and receiver_username and amount:
        try:
            # Record payment
            Payment.objects.create(
                payee_username=receiver_username,  # assuming your Payment model has payee_username field
                amount=float(amount),
                method="UPI",
                txn_id=txn_id,
                status="Success",
                created_at=timezone.now(),
            )
            messages.success(request, f"Payment of ₹{amount} to {receiver_username} recorded successfully.")
            return render(request, "expenses/upi_success.html", {"receiver": receiver_username, "amount": amount})
        except Exception as e:
            messages.error(request, f"Error recording payment: {str(e)}")
    else:
        messages.error(request, "Payment details missing or invalid.")

    return redirect("dashboard")

@login_required
def remove_member(request, event_id, member_id):
    event = get_object_or_404(Event, id=event_id)
    if request.user == event.owner:
        member = get_object_or_404(User, id=member_id)
        event.members.remove(member)
        
        # Optional: delete any expenses associated with that member too
        Expense.objects.filter(event=event, payer=member).delete()

        messages.success(request, f"{member.username} has been removed")
    else:
        messages.error(request, "Only event owner can remove members")
    return redirect('event_detail', event_id=event.id)

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import UserProfile

@login_required
def profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        upi = request.POST.get("upi_id")
        profile.upi_id = upi
        profile.save()
        return redirect("profile")  # reload page and persist
    
    return render(request, "profile.html", {"profile": profile})


from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import UserProfile
import json
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ProfileUPIForm


@login_required
def profile_settings(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileUPIForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "UPI saved successfully!")
            return redirect('profile_settings')
        else:
            messages.error(request, "Invalid UPI format.")
    else:
        form = ProfileUPIForm(instance=profile)

    return render(request, "expenses/profile.html", {"form": form, "profile": profile})

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import UserProfile
import json

@login_required
def update_upi(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            new_upi = data.get("upi", "").strip()
            if not new_upi:
                return JsonResponse({"success": False, "message": "UPI cannot be empty."})
            
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            profile.upi = new_upi
            profile.save()
            return JsonResponse({"success": True, "upi": profile.upi})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})
    return JsonResponse({"success": False, "message": "Invalid request"})
