"""Mailing list commands"""

import getpass
import os
import json
import datetime

import click
from flask import current_app
from flask.cli import AppGroup
from tabulate import tabulate
import arrow
import pyotp

from bc_fsf_base import event
from bc_fsf_database import db
from .models import User


cli = AppGroup('user')


@cli.command('list')
@click.option('-v', '--verbose', count=True)
def list_users(verbose):
    def code(user, type_):
        if getattr(user, f'{type_}_code'):
            exp = getattr(user, f'{type_}_expiration')
            if exp < arrow.utcnow():
                return 'Expired'
            return 'Yes'
        return ''

    def email_conf(user):
        out = code(user, 'email_confirmation')
        if out:
            if user.new_email:
                out += f' - {user.new_email}'
        return out

    def status(user):
        out = []
        if not user.is_approved:
            out.append('Unapproved')
        if user.is_disabled:
            out.append(f'Disabled - {user.is_disabled}')
        return ', '.join(out)

    def totp(user):
        if user.totp_secret:
            return 'Yes'
        elif user.new_totp_secret:
            return 'Pending'
        return ''

    headers = {
        'ID': lambda u: u.id,
        'Username': lambda u: u.username,
        'Email': lambda u: u.email,
        'Status': status,
    }
    if verbose >= 1:
        headers.update({
            'Name': lambda u: u.name or '',
            'Timezone': lambda u: u.timezone,
        })
    if verbose >= 2:
        headers.update({
            'Roles': lambda u: ','.join(u.roles or []),
            'Perms': lambda u: ','.join(u.permissions or []),
        })
    if verbose >= 3:
        headers.update({
            'Has ECC': email_conf,
            'Has PRC': lambda u: code(u, 'password_reset'),
            'Has TOTP': totp,
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
    print(tabulate(rows, headers=t_headers))


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
    print(tabulate(perm_rows, headers=perm_headers))
    print()
    print("Roles:")
    print(tabulate(role_rows, headers=role_headers))


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
    user, _, errs, warns, meta = event.publish(
        'user.create',
        (properties, None, None),
        do_totp_setup=totp,
        skip_totp_confirm=totp,
        skip_email_confirmation=True,
    )

    for e in errs:
        print('ERROR:', e)
    for e in warns:
        print('WARN:', e)
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
@click.option('-G', '--generate-new-password', help="Generate a new password for the user of this length")
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
    if not user:
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
    elif generate_new_password:
        new_password = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789`~!@#$%^&*()_-+={[}]|\\:;"\'<,>.?/', k=int(generate_new_password)))
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


@cli.command('delete')
@click.option('-i', '--id', help="User ID to edit")
@click.option('-u', '--username', help="Username to edit")
def edit_user(id, username):
    if not (id or username) or (id and username):
        raise RuntimeError("Only one of --id or --username is required")

    user = None
    if id:
        user = User.query.get(id)
    elif username:
        user = User.query.filter(User.username.like(username)).first()
    if not user:
        raise RuntimeError("Can't find user")

    if not input("Are you sure you want to delete this user? ").strip().lower().startswith('y'):
        print("Abort")
        return

    db.session.delete(user)
    db.session.commit()


@cli.command('totp')
@click.option('-a', '--add', help="Add a token")
@click.option('-u', '--update', help="With --add, update the underlying token with this id")
@click.option('-d', '--description', help="Description for the added token (required with --add, unless --update)")
@click.option('-r', '--remove', help="Delete a token by ID")
def totp_debug(add, update, description, remove):
    if add and remove:
        raise RuntimeError("Can't use --add & --remove")
    if add and not description and not update:
        raise RuntimeError("--description is required with --add without --update")
    if update and not add:
        raise RuntimeError("--add is required for --update")
    if remove and (update or description):
        raise RuntimeError("Can't use --update or --description with --remove")

    fname = os.path.join(current_app.instance_path, 'totp-gen-test.json')
    if os.path.exists(fname):
        with open(fname, 'r') as fp:
            tokens = json.load(fp)
    else:
        tokens = []

    if add or remove:
        def resolve_id(id):
            try:
                id = int(id)
                t = tokens[id]
                return id, t
            except (TypeError, ValueError):
                raise RuntimeError("Provided id is not int")
            except IndexError:
                raise RuntimeError("Provided id does not exist")

        if add:
            if update:
                id, t = resolve_id(update)
                t['token'] = add
                if description:
                    t['description'] = description
                print("Updated token:", id, t['description'])
            else:
                tokens.append({'token': add, 'description': description})
                print("Added token:", description)

        if remove:
            id, t = resolve_id(remove)
            del tokens[id]
            print("Removed token:", t['description'])

        with open(fname, 'w') as fp:
            json.dump(tokens, fp, indent=4)

    headers = ['ID', 'Description', 'Code', 'Remaining s']
    rows = []
    for i, t in enumerate(tokens):
        totp = pyotp.TOTP(t['token'])
        rows.append([
            i,
            t['description'],
            totp.now(),
            totp.interval - datetime.datetime.now().timestamp() % totp.interval
        ])
    print(tabulate(rows, headers=headers))
