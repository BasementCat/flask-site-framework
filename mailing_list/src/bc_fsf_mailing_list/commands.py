"""Mailing list commands"""

from typing import Any, Union, Optional

import csv, io, sys

import click
from flask import Flask, current_app, url_for
from flask.cli import AppGroup
from tabulate import tabulate
import arrow
from markdown import markdown

from bc_fsf_database import db
from .models import Email


cli = AppGroup('emails')


def pb(v: Any, empty_as_false: bool=False, return_none: bool=False) -> bool:
    """\
    Parse a value as a boolean.

    If empty_as_false, treat an empty value as false instead of raising ValueError
    If return_none, and the value is None, just return None

    Only the first character of the resulting string is considered
    """

    if v is None and return_none:
        return None
    v = str(v).strip()
    if not v:
        if empty_as_false:
            return False
        raise ValueError("Value cannot be empty")
    if v[0] in ('t', 'y', '1'):
        return True
    elif v[0] in ('f', 'n', '0'):
        return False
    raise RuntimeError("Value cannot be converted to bool")


def value_or_none(v: Union[str, None]) -> Union[str, None]:
    """\
    Ensure a value is a string, or None
    """

    if isinstance(v, str):
        return v.strip()
    return v


def clean_dict(d: dict) -> dict:
    """\
    Filter a dictionary, returning a new dict with only keys where the value was
    not None
    """

    out = {}
    for k, v in d.items():
        v = value_or_none(v)
        if v is not None:
            out[k] = v
    return out


HEADERS = {
    'id': {
        'formatter': str,
        'parser': str,
        'required': False,
    },
    'email': {
        'formatter': str,
        'parser': str,
        'required': True,
        'validator': lambda v: '@' in v,
    },
    'name': {
        'formatter': lambda v: str(v or ''),
        'parser': str,
        'required': False,
    },
    'source': {
        'formatter': lambda v: str(v or ''),
        'parser': str,
        'required': False,
    },
    'subscribed': {
        'formatter': lambda v: '1' if v else '',
        'parser': lambda v: pb(v, empty_as_false=True),
        'required': False,
    },
    'confirmed': {
        'formatter': lambda v: '1' if v else '',
        'parser': lambda v: pb(v, empty_as_false=True),
        'required': False,
    },
    'bounced': {
        'formatter': lambda v: '1' if v else '',
        'parser': lambda v: pb(v, empty_as_false=True),
        'required': False,
    },
    'created_at': {
        'formatter': str,
        'parser': arrow.get,
        'required': False,
    },
    'updated_at': {
        'formatter': str,
        'parser': arrow.get,
        'required': False,
    },
}
"""Header definitions for import/export"""


@cli.command('import')
@click.option('-f', '--filename', help="Import from this file; if not present, read from stdin")
@click.option('-e', '--edit', is_flag=True, help="Update existing emails to match the imported files; otherwise existing emails are skipped")
@click.option('-s', '--skip-invalid', is_flag=True, help="Skip invalid rows, instead of aborting the import")
def import_emails(filename: Optional[str], edit: bool, skip_invalid: bool):
    """\
    Import a CSV of emails into the database.
    """
    created = 0
    updated = 0
    errors = []
    fp = None
    def err(i, field, msg, *args):
        errors.append(f"In row #{i+2}, field {field}: " + msg.format(args))
    try:
        with db.session.no_autoflush:
            if filename:
                fp = open(filename, 'r')
                reader = csv.DictReader(fp)
            else:
                reader = csv.DictReader(sys.stdin)

            for i, origrow in enumerate(reader):
                row = {}
                valid = True
                for k, v in HEADERS.items():
                    value = (origrow.get(k) or '').strip() or None
                    if value is None:
                        if v.get('required'):
                            err(i, k, "Field is required")
                            valid = False
                        continue

                    try:
                        value = v['parser'](value)
                    except Exception as e:
                        err(i, k, "Failed to parse value: {}: {}", e.__class__.__name__, e)
                        valid = False
                        continue

                    try:
                        if not v.get('validator', lambda x: True)(value):
                            err(i, k, "Field contains an invalid value")
                            valid = False
                            continue
                    except Exception as e:
                        err(i, k, "Failed to validate value: {}: {}", e.__class__.__name__, e)
                        valid = False
                        continue

                    row[k] = value

                if not valid:
                    continue

                flt = Email.email.like(row['email'])
                if row.get('id'):
                    flt = flt | (Email.id == row['id'])
                obj = Email.query.filter(flt).first()
                if obj:
                    updated += 1
                    if edit:
                        for k, v in row.items():
                            setattr(obj, k, v)
                else:
                    created += 1
                    row.pop('id', None)
                    db.session.add(Email(**row))

            if not errors or not skip_invalid:
                db.session.commit()
            else:
                db.session.rollback()

        if errors:
            print('\n'.join(errors))
            if skip_invalid:
                print("Invalid rows were skipped")
            else:
                print("No changes were made")
                return
        print(f"Created {created} rows")
        if edit:
            print(f"Updated {updated} rows")
        else:
            print(f"Skipped {updated} existing rows")
    finally:
        db.session.rollback()
        if fp:
            fp.close()


@cli.command('export')
@click.option('-f', '--filename', help="Export to this file; if not present, write to stdout")
@click.option('-g', '--grep', help="Export emails partially matching this ID or email address")
@click.option('-t', '--time-field', default='created_at', type=click.Choice(('created_at', 'updated_at'), case_sensitive=True), help="Use this time field for --since/--until")
@click.option('--since', help="Export only emails with the given time field >= this datetime")
@click.option('--until', help="Export only emails with the given time field < this datetime")
@click.option('-s', '--source', help="Export only emails with this source. Use '-' to match the null source")
@click.option('-u', '--subscribed', help="Export only emails with subscribed=<value>")
@click.option('-c', '--confirmed', help="Export only emails with confirmed=<value>")
@click.option('-b', '--bounced', help="Export only emails with bounced=<value>")
@click.option('-a', '--all', is_flag=True, help="Export all emails, ignoring all other filters")
@click.option('-p', '--pretty', is_flag=True, help="Export in a human-readable format instead of CSV")
@click.option('-i', '--ids', is_flag=True, help="Print only IDs, suitable for piping to the edit command")
def export_emails(
    filename: Optional[str],
    grep: Optional[str],
    time_field: Optional[str],
    since: Optional[str],
    until: Optional[str],
    source: Optional[str],
    subscribed: Optional[str],
    confirmed: Optional[str],
    bounced: Optional[str],
    all: bool,
    pretty: bool,
    ids: bool
):
    """\
    Export emails from the database, as a CSV or pretty-printed.  By default,
    only "valid" emails are exported - those that are subscribed, confirmed, and
    have not bounced.
    """

    query = Email.query
    if not all:
        if grep:
            query = query.filter(Email.id.like(f'%{grep}%') | Email.email.like(f'%{grep}%'))
        tf = getattr(Email, time_field)
        if since:
            query = query.filter(tf >= since)
        if until:
            query = query.filter(tf < until)
        if source:
            query = query.filter(Email.source == (None if source == '-' else source))
        if subscribed:
            query = query.filter(Email.subscribed == pb(subscribed))
        if confirmed:
            query = query.filter(Email.confirmed == pb(confirmed))
        if bounced:
            query = query.filter(Email.bounced == pb(bounced))

    res = query.all()
    if ids:
        out = '\n'.join([e.id for e in res])
    elif pretty:
        out = tabulate([[v['formatter'](getattr(i, k)) for k, v in HEADERS.items()] for i in res], headers=list(HEADERS.keys()))
    else:
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(list(HEADERS.keys()))
        for row in res:
            writer.writerow([v['formatter'](getattr(row, k)) for k, v in HEADERS.items()])
        out = out.getvalue()

    if filename:
        with open(filename, 'w') as fp:
            fp.write(out + '\n')
    else:
        print(out)


@cli.command('edit')
@click.option('-i', '--id', help="Email to edit, either ID or full email address.  If not present, read from stdin (like export --ids")
@click.option('-s', '--source', help="Set the email's source. Use '-' to set to null")
@click.option('-u', '--subscribed', help="Set subscribed=<value>")
@click.option('-c', '--confirmed', help="Set confirmed=<value>")
@click.option('-b', '--bounced', help="Set bounced=<value>")
def edit_emails(id: Optional[str], source: Optional[str], subscribed: Optional[str], confirmed: Optional[str], bounced: Optional[str]):
    """\
    Edit an entry in the database, setting properties as described.  May edit
    many entries simultaneously by reading many IDs from stdin
    """

    updates = clean_dict({
        'source': source,
        'subscribed': pb(subscribed, return_none=True),
        'confirmed': pb(confirmed, return_none=True),
        'bounced': pb(bounced, return_none=True),
    })
    # Separate from clean_dict because this would be stripped
    if source == '-':
        updates['source'] = None
    if not updates:
        sys.stderr.write("Nothing to do\n")
        sys.exit(1)

    if id:
        ids = [id]
    else:
        ids = sys.stdin.read()
    ids = list(filter(None, map(str.strip, ids)))
    if not ids:
        sys.stderr.write("No IDs\n")
        sys.exit(2)

    emails = Email.query.filter(Email.id.in_(ids)).all()
    if not emails:
        sys.stderr.write("No emails found with IDs\n")
        sys.exit(1)

    upd = []
    with db.session.no_autoflush:
        try:
            for e in emails:
                for k, v in updates.items():
                    setattr(e, k, v)
                upd.append(f"Updated {e.email} #{e.id}")
            db.session.commit()
            print('\n'.join(upd))
        except:
            db.session.rollback()
            raise


@cli.command('send')
@click.argument('template')
@click.argument('subject')
@click.option('-e', '--test-email', help="Send a test to this email.  Required without --force")
@click.option('-f', '--force', is_flag=True, help="Bypass sending a test email")
def send_emails(template: str, subject: str, test_email: Optional[str], force: bool):
    """\
    Send out an email.  The email body is read from stdin.  Without --force, the
    email is first sent to the provided test email address; and confirmation is
    required prior to sending to the remaining emails.
    """
    if not test_email and not force:
        sys.stderr.write("Without --force, the --test-email is required\n")
        sys.exit(1)

    def send_email(recipients, text_body, html_body, test=False):
        for r in recipients:
            text = html = None
            if text_body:
                text = current_app.jinja_env.from_string(text_body).render(subject=subject, recipient=r)
            if html_body:
                html = current_app.jinja_env.from_string(html_body).render(subject=subject, recipient=r)
            if text and not html:
                html = markdown(text)

            if test:
                email = current_app.plugins['email'].create(subject, to=[test_email])
            else:
                email = current_app.plugins['email'].create(subject, to=[r.email])

            email.render(
                template,
                text_args={'body': text},
                html_args={'body': html},
                subject=subject,
                recipient=r,
                edit_url=url_for('mailing_list.update', id=r.id, _external=True),
            )
            email.send_message()

            if test:
                break

    emails = Email.query.filter(Email.subscribed == True, Email.confirmed == True, Email.bounced == False).all()
    if not emails:
        sys.stderr.write("No emails to send to\n")
        sys.exit(2)

    print("Enter the text email body (if applicable), press ctrl+d when done:")
    text_body = sys.stdin.read().strip() or None
    print("Enter the HTML email body (if applicable), press ctrl+d when done:")
    html_body = sys.stdin.read().strip() or None

    if not force:
        send_email(emails, text_body, html_body, test=True)
        print(f"A test email has been sent to {test_email} - verify it before confirming")
    
    res = input(f"Send to {len(emails)} recipients? enter 'yes' to confirm: ").strip().lower()
    if res != 'yes':
        sys.stderr.write("Aborting\n")
        sys.exit(3)

    send_email(emails, text_body, html_body)
