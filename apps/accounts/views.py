from django import forms
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.text import slugify

from .models import Membership, Workspace


class RegisterForm(UserCreationForm):
    """Signup form: username + email + password. On save, also spins up the
    user's own Workspace and an owner Membership so the app has a tenant to
    hang their data on (WorkspaceMiddleware needs this)."""

    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


def _unique_slug(base):
    base = slugify(base) or "workspace"
    slug = base
    i = 2
    while Workspace.objects.filter(slug=slug).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug


def register(request):
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.email = form.cleaned_data["email"]
                user.save()
                workspace = Workspace.objects.create(
                    name=f"{user.username}'s workspace",
                    slug=_unique_slug(user.username),
                )
                Membership.objects.create(
                    user=user,
                    workspace=workspace,
                    role=Membership.Role.OWNER,
                    is_default=True,
                )
            login(request, user)
            return redirect("/")
    else:
        form = RegisterForm()

    return render(request, "registration/register.html", {"form": form})
