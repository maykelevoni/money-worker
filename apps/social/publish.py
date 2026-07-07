"""Helpers to publish to selected SocialAccounts via Upload-Post.

Accounts are grouped by their Upload-Post profile, since one API call posts to
one profile's platforms. Several accounts may share a profile, or each have
their own.
"""
from collections import OrderedDict

from .models import SocialAccount


def accounts_for(workspace, kind_platforms, ids):
    """Active accounts in this workspace, whose platform is valid for the kind."""
    return list(
        SocialAccount.objects.for_workspace(workspace).filter(
            pk__in=ids, is_active=True, platform__in=kind_platforms
        )
    )


def group_by_profile(accounts):
    """OrderedDict {up_profile: [platform, ...]} (deduped, order-stable)."""
    groups = OrderedDict()
    for a in accounts:
        groups.setdefault(a.up_profile, [])
        if a.platform not in groups[a.up_profile]:
            groups[a.up_profile].append(a.platform)
    return groups
