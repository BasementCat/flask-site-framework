from typing import Iterable, Optional

from random import SystemRandom

from flask import current_app
import pyotp
import qrcode
from qrcode.image.svg import SvgPathFillImage

from bc_fsf_database import db
from ..models import User
from . import exc


def generate_otp_backup_codes(count: int=12, digits: int=9) -> Iterable[str]:
    """\
    Generate random backup codes for OTP
    """

    assert count > 0
    assert digits >= 6
    assert not divmod(digits, 3)[1]

    rand = SystemRandom()
    rmax = 10 ** digits
    for _ in range(count):
        code = list(('0' * digits) + str(rand.randint(0, rmax)))
        out = []
        for _ in range(int(digits / 3)):
            group = ''
            for _ in range(3):
                group += code.pop()
            out.append(group)
        yield '-'.join(out)


def begin_totp_setup(user: User, skip_confirm: bool=False, force: bool=False):
    """\
    Begin the TOTP setup process, preparing to overwrite an existing TOTP secret
    with a new one.  If skip_confirm is True, TOTP is immediately setup without verification.
    """

    if not current_app.config['USERS_ALLOW_TOTP']:
        return

    secret = pyotp.random_base32()
    codes = list(generate_otp_backup_codes())
    if skip_confirm:
        if user.totp_secret and not force:
            raise exc.ProcessComplete("TOTP is already set up")
        user.new_totp_secret = user.new_totp_backup_codes = None
        user.totp_secret = secret
        user.totp_backup_codes = codes
    else:
        if user.new_totp_secret and not force:
            raise exc.ProcessInProgress("TOTP setup is already in progress")
        user.new_totp_secret = secret
        user.new_totp_backup_codes = codes
    db.session.commit()


def complete_totp_setup(user: User, code: str):
    """\
    Complete TOTP setup by verifying a generated code; if the code is valid,
    the temporary TOTP secret is copied to the new secret field and backup
    codes are (re)generated.
    """

    if not user.new_totp_secret:
        raise exc.ProcessNotInProgress("TOTP setup is not in progress")
    if not validate_totp(user, code, secret=user.new_totp_secret, backup=False):
        raise exc.InvalidCode("Invalid TOTP code provided")
    user.totp_secret = user.new_totp_secret
    user.totp_backup_codes = user.new_totp_backup_codes
    user.new_totp_secret = user.new_totp_backup_codes = None
    db.session.commit()


def get_totp(user: User, secret: Optional[str]=None) -> Optional[pyotp.TOTP]:
    """\
    Get a TOTP instance for the given secret, or the configured secret, or
    None if no secret is available
    """

    secret = secret or user.totp_secret
    if secret:
        return pyotp.TOTP(secret)


def get_totp_uri(user: User, secret: Optional[str]=None) -> Optional[str]:
    """\
    Get a provisioning URI for a TOTP authenticator app for the given
    secret, or the configured secret, or None if no secret is available

    As this is intended for use during provisioning, the default secret is
    the newly configured secret
    """

    secret = secret or user.new_totp_secret
    totp = get_totp(user, secret=secret)
    if totp:
        return totp.provisioning_uri(name=f'{user.username} ({user.email})', issuer_name=current_app.config['SITE_NAME'])


def get_totp_qr(user: User, secret: Optional[str]=None, cssclass: str='totp-setup-qr') -> Optional[str]:
    """\
    Get a provisioning QR code for a TOTP authenticator app for the given
    secret, or the configured secret, or None if no secret is available

    As this is intended for use during provisioning, the default secret is
    the newly configured secret

    The return value is an SVG that may be directly embedded into a page
    """

    secret = secret or user.new_totp_secret
    uri = get_totp_uri(user, secret=secret)
    if uri:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(
            image_factory=SvgPathFillImage,
            attrib={'class': cssclass},
        )
        return img.to_string(encoding='unicode')


def validate_totp(user: User, code: str, secret: Optional[str]=None, backup: bool=True) -> bool:
    """\
    Validate a TOTP code against either the provided secret, or the stored TOTP
    secret.  When validating a code against the temporary TOTP secret during
    the setup process, the temporary secret must be provided.  In this case
    it is also advisable to pass backup=False to prevent checking against
    backup codes, to avoid accidentally confirming the TOTP setup with a
    pre-existing backup code, which would not validate the new code.
    """

    secret = secret or user.totp_secret
    code = code.strip().replace('-', '')
    valid = False
    if secret:
        totp = get_totp(user, secret=secret)
        valid = totp.verify(code)
        if not valid and backup:
            code = ('x' * 99) + code
            code_parts = []
            for i in range(0, len(code), 3):
                code_parts.append(code[i:i+3])
            code = '-'.join((p for p in code_parts if p.isnumeric()))
            if user.totp_backup_codes and code in user.totp_backup_codes:
                valid = True
                codes = user.totp_backup_codes
                codes.remove(code)
                user.totp_backup_codes = codes
                db.session.commit()
    return valid
