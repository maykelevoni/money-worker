"""Customer session helpers — a lightweight auth layer separate from Django's
staff auth. A logged-in customer is just an id in the session; they never touch
`request.user` or the creator dashboard.
"""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .models import Customer

SESSION_KEY = "customer_id"


def login_customer(request, customer):
    request.session[SESSION_KEY] = customer.id


def logout_customer(request):
    request.session.pop(SESSION_KEY, None)


def current_customer(request):
    cid = request.session.get(SESSION_KEY)
    if not cid:
        return None
    return Customer.objects.filter(pk=cid).first()


def customer_required(view):
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        customer = current_customer(request)
        if customer is None:
            messages.info(request, "Please sign in to view your products.")
            return redirect("store:login")
        request.customer = customer
        return view(request, *args, **kwargs)

    return _wrapped
