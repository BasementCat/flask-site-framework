from typing import Dict, Optional, Callable, Any, Iterable, List

import logging

from flask import current_app, g

from bc_fsf_base import event
from .models import User
from .mixins import CompareProperty


logger = logging.getLogger(__name__)


@event.subscribes_to('user.permissions', priority=10)
def get_base_permissions(event, permissions, app, *args, **kwargs):
    """Get the default set of permissions"""

    permissions.update({
        'view': {
            'name': "View",
            'description': "View the site",
        },
        'signup': {
            'name': "Signup",
            'description': "Sign up for an account",
        },
        'login': {
            'name': "Login",
            'description': "Log in to the site",
        },
        'edit_user': {
            'name': "Edit User",
            'description': "Edit the user's own account",
            'callback': lambda p, u, o: u == o,
        },
        'edit_other_user': {
            'name': "Edit Other User",
            'description': "Edit other user accounts",
            'callback': lambda p, u, o: u.rolegroup >= o.rolegroup,
        },
        'edit_user_admin': {
            'name': "Edit User - Admin",
            'description': "Edit admin-only fields on the user's own account",
            'callback': lambda p, u, o: u == o,
        },
        'edit_other_user_admin': {
            'name': "Edit Other User - Admin",
            'description': "Edit admin-only fields on other user accounts",
            'callback': lambda p, u, o: u.rolegroup >= o.rolegroup,
        },
        'approve_users': {
            'name': "Approve Users",
            'description': "Approve users when admin approval is required",
        },
        'verify_users': {
            'name': "Verify Users",
            'description': "Bypass the email verification process for a user",
        },
        'view_admin': {
            'name': "View Admin",
            'description': "View administration pages",
        },
    })
    return permissions


@event.subscribes_to('user.roles', priority=10)
def get_base_roles(event, roles, app, *args, **kwargs):
    """Get the default set of roles"""

    roles.update({
        'anonymous': {
            'name': 'Anonymous',
            'description': "Anonymous users (not logged in)",
            'is_anonymous': True,
            'level': 0,
            'permissions': ['view', 'login'],
        },
        'user': {
            'name': 'User',
            'description': "A logged in user",
            'level': 500,
            'includes': ['anonymous'],
            'permissions': ['edit_user'],
            'is_default': True,
        },
        'moderator': {
            'name': 'Moderator',
            'description': "A moderator of the site",
            'level': 1000,
            'includes': ['user'],
            'permissions': ['approve_users', 'view_admin'],
        },
        'administrator': {
            'name': 'Administrator',
            'description': "An administrator of the site",
            'level': 5000,
            'includes': ['moderator'],
            # Explicitly including signup here - allows admins to create users even if signup disabled
            'permissions': ['edit_other_user', 'edit_user_admin', 'edit_other_user_admin', 'verify_users', 'signup'],
        },
        'superadmin': {
            'name': 'Super Administrator',
            'description': "A super admin (has all permissions)",
            'level': 10000,
            'is_superadmin': True,
        }
    })
    return roles


@event.subscribes_to('user.roles', priority=20)
def configure_signup_perm(event, roles, app, *args, **kwargs):
    """Example of how to modify roles - configure signup permission when enabled by config"""
    if app.config['USERS_ALLOW_SIGNUP']:
        for r in roles.values():
            if r.get('is_anonymous') and 'signup' not in r.get('permissions', []):
                r.setdefault('permissions', []).append('signup')
    return roles


def load(app):
    """Load and resolve all permissions & roles"""

    for k, v in event.publish('user.permissions', {}, app=app).items():
        Permission(k, **v)

    for k, v in event.publish('user.roles', {}, app=app).items():
        Role(k, **v)

    Role.resolve_all()


class Permission:
    """Represents a single permission that may be assigned to a role (or user)"""

    all_permissions: Dict[str, Any] = {}
    """Mapping of all permission objects by their key"""

    default_permissions: List[Any] = []
    """Default permissions applied to new users"""

    def __init__(self, key: str, name: str, description: Optional[str]=None, callback: Optional[Callable[[str, User, Any], bool]]=None, is_default: bool=False):
        """\
        Create a new permission.

        * key: Key by which this permission is referred to
        * name: A human-readable name for the permission
        * description: A more verbose description of what this permission controls
        * callback: A callable accepting the permission being checked (key), the user against which it is being checked, and the object against which it is being checked.  Must return a boolean
        * is_default: If True, this permission is marked as a default permission
        """

        self.key = key
        self.name = name
        self.description = description
        self.callback = callback or (lambda perm, user, obj: True)
        self.all_permissions[self.key] = self
        if is_default:
            self.default_permissions.append(self)

    def __call__(self, user: User, obj: Optional[Any]=None) -> bool:
        """\
        Check this permission.  By default, if no callable is provided, the
        presence of the permission means the user has it; however the optional
        callback can check information about the passed in user/object to
        perform additional checks and determine if the permission applies.
        """

        return self.callback(self.key, user, obj)


class Role(CompareProperty('level')):
    """\
    Represents a single role that may be assigned to a user, and includes
    permissions and other roles
    """

    all_roles: Dict[str, Any] = {}
    """Mapping of all role objects by their key"""

    anonymous_role: Optional[Any] = None
    """The default role applied to anonymous users"""

    default_roles: List[Any] = []
    """Default roles to be applied to new users"""

    def __init__(self, key: str, name: str, level: int, description: Optional[str]=None, is_anonymous: bool=False, is_superadmin: bool=False, permissions: Optional[Iterable[str]]=None, includes: Optional[Iterable[str]]=None, is_default: bool=False):
        """\
        Create a new role.

        * key: Key by which this role is referred to
        * name: A human-readable name for the role
        * level: A numeric level representing this role's position in the role hierarchy
        * description: A more verbose description of what this role is for
        * is_anonymous: If this role is to be applied to anonymous users (not logged in)
        * is_superadmin: If this role implicitly has all permissions
        * permissions: List of permission keys directly applicable to this role
        * includes: List of role keys that this role should "include" (their permissions, and their children's permissions, etc, are inherited by this role)
        * is_default: If True, this role is marked as a default role
        """

        self.key = key
        self.name = name
        self.level = level
        self.description = description
        self.is_anonymous = is_anonymous
        self.is_superadmin = is_superadmin
        self.permissions = permissions or []
        self.includes = includes or []
        self.resolved_permissions = {}
        self.resolved_roles = set()
        self.all_roles[self.key] = self
        if is_default:
            self.default_roles.append(self)

    def resolve(self):
        """\
        Resolve inherited permissions/roles
        """

        queue = [self]
        while queue:
            role = queue.pop(0)
            self.resolved_roles.add(role.key)
            for k in role.permissions:
                try:
                    self.resolved_permissions[k] = Permission.all_permissions[k]
                except KeyError:
                    logger.warning("Failed to resolve permission %s for role %s, it will always be False", k, self.key)
            for k in role.includes:
                try:
                    queue.append(self.all_roles[k])
                except KeyError:
                    logger.warning("Failed to resolve included role %s for role %s, its permissions will not be included", k, self.key)

            if role.is_anonymous:
                if self.__class__.anonymous_role:
                    logger.warning("Role %s is overriding anonymous role from %s", role.key, self.__class__.anonymous_role.key)
                self.__class__.anonymous_role = role

    @classmethod
    def resolve_all(cls):
        """\
        Perform resolution process on all defined roles
        """
        for role in cls.all_roles.values():
            role.resolve()

        if not cls.anonymous_role:
            logger.warning("No anonymous role is defined")

    def contains_role(self, role_key):
        return role_key in self.resolved_roles

    def check_permissions(self, *perms, user: Optional[User]=None, obj: Optional[Any]=None) -> bool:
        """\
        Check if the given user has any given permissions for the given object

        Does not check if the user has this role; should only be called on roles
        the user has
        """

        if self.is_superadmin:
            # Superadmin implicitly has all permissions
            return True

        for p in perms:
            if p in self.resolved_permissions:
                if self.resolved_permissions[p](user, obj):
                    return True

        return False


class RoleGroup(CompareProperty('maxlevel')):
    """Represent the group of roles (and permissions) assigned to a user"""

    def __init__(self, user: Optional[User]=None):
        self.user = user
        if self.user:
            self.roles = list(filter(None, (Role.all_roles.get(r) for r in (self.user.roles or []))))
            self.permissions = {p.key: p for p in filter(None, (Permission.all_permissions.get(r) for r in (self.user.permissions or [])))}
        else:
            self.roles = []
            self.permissions = []
            if Role.anonymous_role:
                self.roles = [Role.anonymous_role]

        self.maxlevel = max((r.level for r in self.roles)) if self.roles else 0

    def contains_role(self, role_key):
        for role in self.roles:
            if role.contains_role(role_key):
                return True
        return False

    def check_permissions(self, *perms, obj: Optional[Any]=None) -> bool:
        """\
        Check if the user given in the constructor has permissions for the given
        object
        """

        for r in self.roles:
            if r.check_permissions(*perms, user=self.user, obj=obj):
                return True

        for p in perms:
            if p in self.permissions:
                if self.permissions[p](self.user, obj):
                    return True

        return False

    @classmethod
    def for_user(cls, user: Optional[User]=None) -> Any:
        k = user.id if user else '__default__'
        g.setdefault('users_role_groups', {})
        if k not in g.users_role_groups:
            g.users_role_groups[k] = cls(user)
        return g.users_role_groups[k]
