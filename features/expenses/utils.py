
from django.core.exceptions import PermissionDenied

def calculate_settlements(balances):
   
    creditors = []
    debtors = []
    settlements = []

    for user, amount in balances.items():
        if amount > 0:
            creditors.append([user, amount])
        elif amount < 0:
            debtors.append([user, -amount])

    creditors.sort(key=lambda x: -x[1])
    debtors.sort(key=lambda x: -x[1])

    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor, debt_amt = debtors[i]
        creditor, cred_amt = creditors[j]

        settled_amt = min(debt_amt, cred_amt)
        settlements.append({
            'from': debtor,
            'to': creditor,
            'amount': round(settled_amt, 2)
        })

        debtors[i][1] -= settled_amt
        creditors[j][1] -= settled_amt

        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1

    return settlements

def check_event_creator(user, event):
    """
    Utility to ensure only the event creator can edit/delete/add expenses.
    Raises PermissionDenied if not creator.
    """
    if event.created_by != user:
        raise PermissionDenied("You do not have permission to modify this event.")
