"""Mailing list commands"""

# from typing import Any, Union, Optional

# import csv, io, sys
import getpass

import click
from flask import current_app
from flask.cli import AppGroup
from tabulate import tabulate
# import arrow
# from markdown import markdown

from bc_fsf_base import event
# from bc_fsf_database import db
from .models import User


cli = AppGroup('user')


# def pb(v: Any, empty_as_false: bool=False, return_none: bool=False) -> bool:
#     """\
#     Parse a value as a boolean.

#     If empty_as_false, treat an empty value as false instead of raising ValueError
#     If return_none, and the value is None, just return None

#     Only the first character of the resulting string is considered
#     """

#     if v is None and return_none:
#         return None
#     v = str(v).strip()
#     if not v:
#         if empty_as_false:
#             return False
#         raise ValueError("Value cannot be empty")
#     if v[0] in ('t', 'y', '1'):
#         return True
#     elif v[0] in ('f', 'n', '0'):
#         return False
#     raise RuntimeError("Value cannot be converted to bool")


# def value_or_none(v: Union[str, None]) -> Union[str, None]:
#     """\
#     Ensure a value is a string, or None
#     """

#     if isinstance(v, str):
#         return v.strip()
#     return v


# def clean_dict(d: dict) -> dict:
#     """\
#     Filter a dictionary, returning a new dict with only keys where the value was
#     not None
#     """

#     out = {}
#     for k, v in d.items():
#         v = value_or_none(v)
#         if v is not None:
#             out[k] = v
#     return out


@cli.command('list')
@click.option('-v', '--verbose', count=True)
def list_users(verbose):
    headers = {
        'Username': lambda u: u.username,
        'Email': lambda u: u.email,
        'Status': lambda u: str(u.status),
    }
    if verbose >= 1:
        headers.update({
            'Name': lambda u: u.name or '',
        })
    if verbose >= 2:
        headers.update({
            'Roles': lambda u: ','.join(u.roles or []),
            'Perms': lambda u: ','.join(u.permissions or []),
        })
    if verbose >= 3:
        headers.update({
            'Has ECC': lambda u: 'Yes' if u.email_confirmation_code else '',
            'Has PRC': lambda u: 'Yes' if u.password_reset_code else '',
            'Has TOTP': lambda u: 'Yes' if u.totp_secret else '',
        })
    if verbose >= 4:
        headers.update({
            'Bio': lambda u: u.bio or '',
        })

    t_headers = list(headers.keys())
    rows = []
    for u in User.query:
        row = []
        for getter in headers.values():
            row.append(getter(u))
        rows.append(row)
    print(tabulate.tabulate(rows, headers=t_headers))


@cli.command('perms')
def list_roles_perms():
    plugin = current_app.plugins['user']

    perm_headers = ['Key', 'Name', 'Description', 'Has Callback']
    perm_rows = []
    for k, p in plugin.permissions.items():
        perm_rows.append([k, p['name'], p.get('description') or '', 'Yes' if p.get('callback') else ''])

    role_headers = ['Key', 'Name', 'Description', 'Level', 'Special', 'Includes', 'Permissions']
    role_rows = []
    for k, r in plugin.roles.items():
        role_rows.append([
            k,
            r['name'],
            r.get('description') or '',
            r['level'],
            ', '.join(filter(None, [
                'Anonymous' if r.get('is_anonymous') else None,
                'Superadmin' if r.get('is_superadmin') else None,
            ])),
            ', '.join(r.get('includes') or []),
            ', '.join(r.get('permissions') or []),
        ])

    print("Permissions:")
    print(tabulate.tabulate(perm_rows, headers=perm_headers))
    print()
    print("Roles:")
    print(tabulate.tabulate(role_rows, headers=role_headers))


@cli.command('add')
@click.argument('username')
@click.argument('email')
@click.option('-p', '--password', help="Provide a password for the user, if not provided, you will be prompted")
@click.option('-P', '--generate-password', help="Autogenerate a password for the user of this length")
@click.option('-n', '--name', help="Optional display name for the user")
@click.option('-t', '--totp', is_flag=True, help="Enable TOTP for the user, printing the secret & backup codes")
@click.option('-b', '--bio', help="Optional user bio")
@click.option('-r', '--roles', help="Comma-separated list of roles")
@click.option('-e', '--permissions', help="Comma-separated list of permissions (not recommended; use roles)")
@click.option('-d', '--disabled', is_flag=True, help="Create the user as disabled (otherwise they will be active (email confirmation and admin approval are skipped), or in TOTP setup if required)")
@click.option('-T', '--timezone', help="Set the user's timezone")
def add_user(username, email, password, generate_password, name, totp, bio, roles, permissions, disabled, timezone):
    if not password:
        if generate_password:
            password = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789`~!@#$%^&*()_-+={[}]|\\:;"\'<,>.?/', k=int(generate_password)))
        else:
            while not password:
                password = getpass.getpass("Password: ")

    properties = {
        'username': username,
        'email': email,
        'password': password,
        'name': name,
        'is_approved': True,
        'is_disabled': disabled,
        'bio': bio,
        'roles': roles.split(',') if roles else None,
        'permissions': permissions.split(',') if permissions else None,
        'timezone': timezone,
    }
    _, user, messages = event.publish(
        'user.create',
        (properties, None, None),
        do_totp_setup=totp,
        skip_totp_confirm=totp,
        skip_email_confirmation=True,
    )

    event.print_flashed(messages)
    if user:
        print(f"Created user {user.username} as #{user.id}")
        print(f"User's password is: {password}")
        if totp:
            print(f"User's TOTP secret is {user.totp_secret}")
            print("User's TOTP backup codes are:\n\t{}".format('\n\t'.join(user.totp_backup_codes)))


@cli.command('edit')
@click.option('-i', '--id', help="User ID to edit")
@click.option('-u', '--username', help="Username to edit")
@click.option('--approve', is_flag=True, help="Mark the user as approved")
@click.option('--verify', is_flag=True, help="Clear email confirmation for this user")
@click.option('--nopwreset', is_flag=True, help="Clear password reset info for user")
@click.option('--nototpreset', is_flag=True, help="Clear TOTP reset info for user")
@click.option('--enable', is_flag=True, help="Mark user as enabled")
@click.option('--disable', help="Mark user as disabled")
@click.option('--clear-totp',is_flag=True, help="Remove TOTP for this user")

@click.option('-U', '--new-username', help="Set the user's username")
@click.option('-E', '--new-email', help="Set the user's email")
@click.option('-p', '--new-password', help="Set the user's new password")
@click.option('-P', '--ask-new-password', is_flag=True, help="Ask for a new password for the user")
@click.option('-G', '--generate-new-password', is_flag=True, help="Generate a new password for the user")
@click.option('-n', '--new-name', help="Set a new name for the user, '-' to clear")
@click.option('-b', '--new-bio', help="Set a new bio for the user, '-' to clear")
@click.option('-r', '--add-roles', help="Add comma-separated roles to the user")
@click.option('-R', '--new-roles', help="Set comma-separated roles to the user")
@click.option('-m', '--add-permissions', help="Add comma-separated permissions to the user")
@click.option('-M', '--new-permissions', help="Set comma-separated permissions to the user")
@click.option('-t', '--new-timezone', help="Set a new timezone for the user")

def edit_user(id, username, approve, verify, nopwreset, nototpreset, enable, disable, clear_totp,
    new_username, new_email, new_password, ask_new_password, generate_new_password, new_name,
    new_bio, add_roles, new_roles, add_permissions, new_permissions, new_timezone):
    if not (id or username) or (id and username):
        raise RuntimeError("Only one of --id or --username is required")

    user = None
    if id:
        user = User.query.get(id)
    elif username:
        user = User.query.filter(User.username.like(username)).first()
    if not username:
        raise RuntimeError("Can't find user")

    if approve:
        user.is_approved = True

    if verify:
        user.email_confirmation_code = user.email_confirmation_expiration = user.new_email = None

    if nopwreset:
        user.password_reset_code = user.password_reset_expiration = None

    if nototpreset:
        user.new_totp_secret = None

    if enable:
        user.is_disabled = None
    elif disable:
        user.is_disabled = disable

    if clear_totp:
        user.new_totp_secret = user.totp_secret = None
        user.totp_backup_codes = []

    if new_username:
        user.username = new_username

    if new_email:
        user.email = new_email

    if new_password:
        user.set_password(new_password, commit=False)
    elif ask_new_password:
        while not new_password:
            new_password = getpass.getpass("Password: ")
        user.set_password(new_password, commit=False)
    elif generate_password:
        new_password = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789`~!@#$%^&*()_-+={[}]|\\:;"\'<,>.?/', k=int(generate_password)))
        user.set_password(new_password, commit=False)

    if new_name:
        user.name = None if new_name == '-' else new_name

    if new_bio:
        user.bio = None if new_bio == '-' else new_bio

    if add_roles:
        user.roles = user.roles + add_roles.split(',')

    if new_roles:
        user.roles = new_roles.split(',')

    if add_permissions:
        user.permissions = user.permissions + add_permissions.split(',')

    if new_permissions:
        user.permissions = new_permissions.split(',')

    if new_timezone:
        user.timezone = new_timezone

    db.session.commit()

    print(f"Updated user #{user.id} {user.username}")
    if new_password:
        print(f"User's password is: {new_password}")
