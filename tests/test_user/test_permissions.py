from unittest import TestCase
from unittest.mock import patch, call, MagicMock

from flask import g

from flask_site_framework.user.permissions import (
    get_base_permissions,
    get_base_roles,
    configure_signup_perm,
    load,
    Permission,
    Role,
    RoleGroup,
)

from . import mock_app, MockUser


class RolePermTestCase(TestCase):
    def setUp(self):
        Permission.all_permissions = {}
        Permission.default_permissions = []
        Role.all_roles = {}
        Role.anonymous_role = None
        Role.default_roles = []


class TestBaseFunctions(RolePermTestCase):
    def test_get_base_perms(self):
        with mock_app({}) as app:
            res = get_base_permissions('user.permissions', {}, app)
            self.assertEqual(res['view']['name'], 'View')

    def test_get_base_roles(self):
        with mock_app({}) as app:
            res = get_base_roles('user.roles', {}, app)
            self.assertEqual(res['anonymous']['name'], 'Anonymous')
            self.assertIn('view', res['anonymous']['permissions'])

    def test_signup_perm(self):
        with mock_app({'USERS_ALLOW_SIGNUP': False}) as app:
            base = get_base_roles('user.roles', {}, app)
            res = configure_signup_perm('user.roles', base, app)
            self.assertNotIn('signup', res['anonymous']['permissions'])

        with mock_app({'USERS_ALLOW_SIGNUP': True}) as app:
            base = get_base_roles('user.roles', {}, app)
            res = configure_signup_perm('user.roles', base, app)
            self.assertIn('signup', res['anonymous']['permissions'])

    @patch('flask_site_framework.user.permissions.event.publish')
    @patch('flask_site_framework.user.permissions.Permission')
    @patch('flask_site_framework.user.permissions.Role')
    def test_load(self, mock_role_cls, mock_perm_cls, mock_publish):
        with mock_app({}) as app:
            load(app)
            mock_publish.assert_has_calls([
                call('user.permissions', {}, app=app),
                call('user.roles', {}, app=app),
            ], any_order=True)
            # mock_role_cls.assert_called()
            # mock_perm_cls.assert_called()
            mock_role_cls.resolve_all.assert_called_once()

    @patch('flask_site_framework.user.permissions.Permission')
    @patch('flask_site_framework.user.permissions.Role')
    def test_load(self, mock_role_cls, mock_perm_cls):
        with mock_app({'USERS_ALLOW_SIGNUP': True}) as app:
            load(app)
            mock_role_cls.assert_called()
            mock_perm_cls.assert_called()
            mock_role_cls.resolve_all.assert_called_once()


class TestPermission(RolePermTestCase):
    def test_create(self):
        p1 = Permission('foo', 'Foo')
        p2 = Permission('bar', 'Bar', description='Bar perm')
        c = lambda p, u, o: True
        p3 = Permission('baz', 'Baz', description='Baz perm', callback=c)
        p4 = Permission('d1', 'd1', is_default=True)
        p5 = Permission('d2', 'd2', is_default=True)

        a = Permission.all_permissions
        self.assertEqual(len(a), 5)

        self.assertEqual(a['foo'].key, 'foo')
        self.assertEqual(a['foo'].name, 'Foo')
        self.assertIsNone(a['foo'].description)
        self.assertTrue(callable(a['foo'].callback))
        self.assertNotEqual(a['foo'].callback, c)

        self.assertEqual(a['bar'].key, 'bar')
        self.assertEqual(a['bar'].name, 'Bar')
        self.assertEqual(a['bar'].description, 'Bar perm')
        self.assertTrue(callable(a['bar'].callback))
        self.assertNotEqual(a['bar'].callback, c)

        self.assertEqual(a['baz'].key, 'baz')
        self.assertEqual(a['baz'].name, 'Baz')
        self.assertEqual(a['baz'].description, 'Baz perm')
        self.assertTrue(callable(a['baz'].callback))
        self.assertEqual(a['baz'].callback, c)

        self.assertEqual(Permission.default_permissions, [p4, p5])

    def test_check__simple(self):
        p = Permission('test', 'test')
        self.assertTrue(p(None))

    def test_check__simple__obj(self):
        p = Permission('test', 'test')
        self.assertTrue(p(None, obj='foo'))

    def test_check__simple__user(self):
        p = Permission('test', 'test')
        u = MockUser()
        self.assertTrue(p(u))

    def test_check__simple__user__obj(self):
        p = Permission('test', 'test')
        u = MockUser()
        self.assertTrue(p(u, obj='foo'))

    def test_check__cb(self):
        cb = MagicMock()
        cb.return_value = True
        p = Permission('test', 'test', callback=cb)
        self.assertTrue(p(None))
        cb.assert_called_once_with('test', None, None)

    def test_check__cb__obj(self):
        cb = MagicMock()
        cb.return_value = True
        p = Permission('test', 'test', callback=cb)
        self.assertTrue(p(None, obj='foo'))
        cb.assert_called_once_with('test', None, 'foo')

    def test_check__cb__user(self):
        cb = MagicMock()
        cb.return_value = True
        p = Permission('test', 'test', callback=cb)
        u = MockUser()
        self.assertTrue(p(u))
        cb.assert_called_once_with('test', u, None)

    def test_check__cb__user__obj(self):
        cb = MagicMock()
        cb.return_value = True
        p = Permission('test', 'test', callback=cb)
        u = MockUser()
        self.assertTrue(p(u, obj='foo'))
        cb.assert_called_once_with('test', u, 'foo')

    def test_check_cb__var(self):
        def cb(p, u, o):
            return o == 'foo'

        p = Permission('test', 'test', callback=cb)
        self.assertTrue(p(None, obj='foo'))
        self.assertFalse(p(None, obj='bar'))


class TestRole(RolePermTestCase):
    def test_create(self):
        r = Role('test1', 'Test', 10)
        self.assertEqual(r.key, 'test1')
        self.assertEqual(r.name, 'Test')
        self.assertEqual(r.level, 10)
        self.assertIsNone(r.description)
        self.assertFalse(r.is_anonymous)
        self.assertFalse(r.is_superadmin)
        self.assertEqual(r.permissions, [])
        self.assertEqual(r.includes, [])
        self.assertEqual(r.resolved_permissions, {})
        self.assertEqual(r.resolved_roles, set())
        self.assertEqual(len(Role.all_roles), 1)
        self.assertEqual(Role.all_roles['test1'], r)

        r = Role('test2', 'Test', 10, description='Test role', is_anonymous=True, is_superadmin=True,
            permissions=['foo'], includes=['bar'])
        self.assertEqual(r.key, 'test2')
        self.assertEqual(r.description, 'Test role')
        self.assertTrue(r.is_anonymous)
        self.assertTrue(r.is_superadmin)
        self.assertEqual(r.permissions, ['foo'])
        self.assertEqual(r.includes, ['bar'])
        self.assertEqual(r.resolved_permissions, {})
        self.assertEqual(r.resolved_roles, set())
        self.assertEqual(len(Role.all_roles), 2)
        self.assertEqual(Role.all_roles['test2'], r)

        d1 = Role('test3', 'Test', 10, is_default=True)
        d2 = Role('test4', 'Test', 10, is_default=True)
        self.assertEqual(Role.default_roles, [d1, d2])

    def test_resolve__simple(self):
        p1 = Permission('testperm1', 'testperm')
        p2 = Permission('testperm2', 'testperm')
        rb = Role('base', 'base', 10, permissions=['testperm1'])
        rr = Role('resolved', 'resolved', 20, permissions=['testperm2'], includes=['base'])
        rr.resolve()
        self.assertEqual(rr.resolved_permissions, {'testperm1': p1, 'testperm2': p2})
        self.assertEqual(rr.resolved_roles, {'base', 'resolved'})

    def test_resolve__anon(self):
        self.assertIsNone(Role.anonymous_role)
        r = Role('test', 'test', 10, is_anonymous=True)
        r.resolve()
        self.assertTrue(Role.anonymous_role is r)

    def test_resolve__anon_multi(self):
        self.assertIsNone(Role.anonymous_role)
        r1 = Role('test', 'test', 10, is_anonymous=True)
        r1.resolve()
        self.assertTrue(Role.anonymous_role is r1)
        r2 = Role('test2', 'test', 10, is_anonymous=True)
        r2.resolve()
        self.assertTrue(Role.anonymous_role is not r1)
        self.assertTrue(Role.anonymous_role is r2)

    def test_resolve__perm_fail(self):
        p1 = Permission('testperm1', 'testperm')
        rb = Role('base', 'base', 10, permissions=['testperm1', 'testperm2'])
        rb.resolve()
        self.assertEqual(rb.resolved_permissions, {'testperm1': p1})

    def test_resolve__role_fail(self):
        rb = Role('base', 'base', 10)
        rr = Role('resolved', 'resolved', 20, includes=['base', 'foo'])
        rr.resolve()
        self.assertEqual(rr.resolved_roles, {'base', 'resolved'})


class RolePermFixture:
    def setUp(self):
        super().setUp()

        Permission(
            'view',
            "View",
            description="View the site",
        )
        Permission(
            'login',
            "Login",
            description="Log in to the site",
        )
        Permission(
            'edit_user',
            "Edit User",
            description="Edit the user's own account",
            callback=lambda p, u, o: u == o,
        )
        Permission(
            'edit_other_user',
            "Edit Other User",
            description="Edit other user accounts",
            callback=lambda p, u, o: u.rolegroup > o.rolegroup,
        )
        Permission(
            'approve_users',
            "Approve Users",
            description="Approve users when admin approval is required",
        )
        Permission(
            'view_admin',
            "View Admin",
            description="View administration pages",
        )

        Role(
            'anonymous',
            'Anonymous',
            description="Anonymous users (not logged in)",
            is_anonymous=True,
            level=0,
            permissions=['view', 'login'],
        )
        Role(
            'user',
            'User',
            description="A logged in user",
            level=500,
            includes=['anonymous'],
            permissions=['edit_user'],
        )
        Role(
            'moderator',
            'Moderator',
            description="A moderator of the site",
            level=1000,
            includes=['user'],
            permissions=['approve_users', 'view_admin'],
        )
        Role(
            'administrator',
            'Administrator',
            description="An administrator of the site",
            level=5000,
            includes=['moderator'],
            permissions=['edit_other_user'],
        )
        Role(
            'superadmin',
            'Super Administrator',
            description="A super admin (has all permissions)",
            level=10000,
            is_superadmin=True,
        )

        Role.resolve_all()


class TestRoleFull(RolePermFixture, RolePermTestCase):
    def test_resolve_all(self):
        # already called as part of setup
        self.assertIn('view', Role.all_roles['anonymous'].resolved_permissions)
        self.assertIn('login', Role.all_roles['anonymous'].resolved_permissions)

        self.assertIn('view', Role.all_roles['user'].resolved_permissions)
        self.assertIn('login', Role.all_roles['user'].resolved_permissions)
        self.assertIn('edit_user', Role.all_roles['user'].resolved_permissions)

        self.assertIn('view', Role.all_roles['moderator'].resolved_permissions)
        self.assertIn('login', Role.all_roles['moderator'].resolved_permissions)
        self.assertIn('edit_user', Role.all_roles['moderator'].resolved_permissions)
        self.assertIn('approve_users', Role.all_roles['moderator'].resolved_permissions)
        self.assertIn('view_admin', Role.all_roles['moderator'].resolved_permissions)

        self.assertIn('view', Role.all_roles['administrator'].resolved_permissions)
        self.assertIn('login', Role.all_roles['administrator'].resolved_permissions)
        self.assertIn('edit_user', Role.all_roles['administrator'].resolved_permissions)
        self.assertIn('approve_users', Role.all_roles['administrator'].resolved_permissions)
        self.assertIn('view_admin', Role.all_roles['administrator'].resolved_permissions)
        self.assertIn('edit_other_user', Role.all_roles['administrator'].resolved_permissions)

    def test_contains(self):
        self.assertFalse(Role.all_roles['anonymous'].contains_role('user'))

        self.assertTrue(Role.all_roles['user'].contains_role('anonymous'))
        self.assertFalse(Role.all_roles['user'].contains_role('moderator'))

        self.assertTrue(Role.all_roles['moderator'].contains_role('anonymous'))
        self.assertTrue(Role.all_roles['moderator'].contains_role('user'))
        self.assertFalse(Role.all_roles['moderator'].contains_role('administrator'))

        self.assertTrue(Role.all_roles['administrator'].contains_role('anonymous'))
        self.assertTrue(Role.all_roles['administrator'].contains_role('user'))
        self.assertTrue(Role.all_roles['administrator'].contains_role('administrator'))
        self.assertFalse(Role.all_roles['administrator'].contains_role('superadmin'))

    def test_check(self):
        self.assertTrue(Role.all_roles['anonymous'].check_permissions('login', user=None))
        self.assertFalse(Role.all_roles['anonymous'].check_permissions('view_admin', user=None))
        self.assertFalse(Role.all_roles['anonymous'].check_permissions('invalid', user=None))

        u = MockUser()
        self.assertTrue(Role.all_roles['moderator'].check_permissions('login', user=u))
        self.assertTrue(Role.all_roles['moderator'].check_permissions('view_admin', user=u))
        self.assertFalse(Role.all_roles['moderator'].check_permissions('invalid', user=u))

    def test_check__multi(self):
        self.assertTrue(Role.all_roles['anonymous'].check_permissions('login', 'view', user=None))
        self.assertTrue(Role.all_roles['anonymous'].check_permissions('login', 'invalid', user=None))
        self.assertFalse(Role.all_roles['anonymous'].check_permissions('invalid1', 'invalid', user=None))

    def test_check__super(self):
        u = MockUser()
        self.assertTrue(Role.all_roles['superadmin'].check_permissions('login', user=u))
        self.assertTrue(Role.all_roles['superadmin'].check_permissions('view_admin', user=u))
        self.assertTrue(Role.all_roles['superadmin'].check_permissions('invalid', user=u))

    def test_check__super_multi(self):
        self.assertTrue(Role.all_roles['superadmin'].check_permissions('login', 'view', user=None))
        self.assertTrue(Role.all_roles['superadmin'].check_permissions('login', 'invalid', user=None))
        self.assertTrue(Role.all_roles['superadmin'].check_permissions('invalid1', 'invalid', user=None))

    def test_check__user_edit(self):
        user1 = MockUser(rolegroup=10)
        user2 = MockUser(rolegroup=10)
        admin1 = MockUser(rolegroup=30)
        admin2 = MockUser(rolegroup=30)
        sa1 = MockUser(rolegroup=40)
        sa2 = MockUser(rolegroup=40)

        self.assertFalse(Role.all_roles['anonymous'].check_permissions('edit_user', 'edit_other_user', user=None, obj=user1))
        self.assertTrue(Role.all_roles['user'].check_permissions('edit_user', 'edit_other_user', user=user1, obj=user1))
        self.assertFalse(Role.all_roles['user'].check_permissions('edit_user', 'edit_other_user', user=user1, obj=user2))
        self.assertTrue(Role.all_roles['administrator'].check_permissions('edit_user', 'edit_other_user', user=admin1, obj=admin1))
        self.assertTrue(Role.all_roles['administrator'].check_permissions('edit_user', 'edit_other_user', user=admin1, obj=user1))
        self.assertFalse(Role.all_roles['administrator'].check_permissions('edit_user', 'edit_other_user', user=admin1, obj=admin2))
        self.assertTrue(Role.all_roles['superadmin'].check_permissions('edit_user', 'edit_other_user', user=sa1, obj=user1))
        self.assertTrue(Role.all_roles['superadmin'].check_permissions('edit_user', 'edit_other_user', user=sa1, obj=admin1))
        self.assertTrue(Role.all_roles['superadmin'].check_permissions('edit_user', 'edit_other_user', user=sa1, obj=sa2))

    def test_compare(self):
        self.assertLess(Role.all_roles['anonymous'], Role.all_roles['user'])
        self.assertEqual(Role.all_roles['anonymous'], Role.all_roles['anonymous'])
        self.assertGreater(Role.all_roles['user'], Role.all_roles['anonymous'])
        self.assertGreater(Role.all_roles['moderator'], Role.all_roles['user'])
        self.assertGreater(Role.all_roles['administrator'], Role.all_roles['moderator'])
        self.assertGreater(Role.all_roles['superadmin'], Role.all_roles['administrator'])


class TestRoleGroup(RolePermFixture, RolePermTestCase):
    def test_create__anon(self):
        rg = RoleGroup()
        self.assertIsNone(rg.user)
        self.assertEqual(rg.permissions, [])
        self.assertEqual(rg.roles, [Role.all_roles['anonymous']])

    def test_create__user(self):
        u = MockUser(roles=['user'], permissions=['approve_users'])
        rg = RoleGroup(user=u)
        self.assertTrue(rg.user is u)
        self.assertEqual(rg.permissions, {'approve_users': Permission.all_permissions['approve_users']})
        self.assertEqual(rg.roles, [Role.all_roles['user']])

    def test_create__user__missing(self):
        u = MockUser(roles=['invalid', 'user'], permissions=['invalid', 'approve_users'])
        rg = RoleGroup(user=u)
        self.assertTrue(rg.user is u)
        self.assertEqual(rg.permissions, {'approve_users': Permission.all_permissions['approve_users']})
        self.assertEqual(rg.roles, [Role.all_roles['user']])

    def test_create__user__maxlevel(self):
        rg_anon = RoleGroup()
        rg_user = RoleGroup(user=MockUser(roles=['user'], permissions=[]))
        rg_admin = RoleGroup(user=MockUser(roles=['administrator'], permissions=[]))
        self.assertGreater(rg_user, rg_anon)
        self.assertGreater(rg_admin, rg_user)

    def test_contains(self):
        rg = RoleGroup(user=MockUser(roles=['moderator'], permissions=[]))
        self.assertTrue(rg.contains_role('moderator'))
        self.assertTrue(rg.contains_role('user'))
        self.assertTrue(rg.contains_role('anonymous'))
        self.assertFalse(rg.contains_role('administrator'))
        self.assertFalse(rg.contains_role('superadmin'))

    def test_check__anon(self):
        rg = RoleGroup()
        self.assertTrue(rg.check_permissions('login'))
        self.assertFalse(rg.check_permissions('view_admin'))
        self.assertFalse(rg.check_permissions('invalid'))
        self.assertTrue(rg.check_permissions('login', 'invalid'))

    def test_check__user__roles(self):
        u1 = MockUser(roles=['user'], permissions=[])
        rg = RoleGroup(user=u1)
        self.assertTrue(rg.check_permissions('login'))
        self.assertFalse(rg.check_permissions('view_admin'))
        self.assertFalse(rg.check_permissions('invalid'))
        self.assertTrue(rg.check_permissions('login', 'invalid'))
        self.assertTrue(rg.check_permissions('edit_user', obj=u1))


    def test_check__user__perms(self):
        u1 = MockUser(roles=[], permissions=['login'])
        rg = RoleGroup(user=u1)
        self.assertTrue(rg.check_permissions('login'))
        self.assertFalse(rg.check_permissions('view_admin'))
        self.assertFalse(rg.check_permissions('invalid'))
        self.assertTrue(rg.check_permissions('login', 'invalid'))
        self.assertFalse(rg.check_permissions('edit_user', obj=u1))

    def test_check__user__edit(self):
        user1 = MockUser(roles=['user'], permissions=[])
        user2 = MockUser(roles=['user'], permissions=[])
        admin1 = MockUser(roles=['administrator'], permissions=[])
        admin2 = MockUser(roles=['administrator'], permissions=[])
        sa1 = MockUser(roles=['superadmin'], permissions=[])
        sa2 = MockUser(roles=['superadmin'], permissions=[])

        user1.rolegroup = RoleGroup(user=user1)
        user2.rolegroup = RoleGroup(user=user2)
        admin1.rolegroup = RoleGroup(user=admin1)
        admin2.rolegroup = RoleGroup(user=admin2)
        sa1.rolegroup = RoleGroup(user=sa1)
        sa2.rolegroup = RoleGroup(user=sa2)

        self.assertFalse(RoleGroup().check_permissions('edit_user', 'edit_other_user', obj=user1))
        self.assertTrue(user1.rolegroup.check_permissions('edit_user', 'edit_other_user', obj=user1))
        self.assertFalse(user1.rolegroup.check_permissions('edit_user', 'edit_other_user', obj=user2))
        self.assertTrue(admin1.rolegroup.check_permissions('edit_user', 'edit_other_user', obj=admin1))
        self.assertTrue(admin1.rolegroup.check_permissions('edit_user', 'edit_other_user', obj=user1))
        self.assertFalse(admin1.rolegroup.check_permissions('edit_user', 'edit_other_user', obj=admin2))
        self.assertTrue(sa1.rolegroup.check_permissions('edit_user', 'edit_other_user', obj=user1))
        self.assertTrue(sa1.rolegroup.check_permissions('edit_user', 'edit_other_user', obj=admin1))
        self.assertTrue(sa1.rolegroup.check_permissions('edit_user', 'edit_other_user', obj=sa2))

    def test_for_user__anon(self):
        with mock_app({}) as app, app.app_context():
            rg1 = RoleGroup.for_user()
            rg2 = RoleGroup.for_user()
            self.assertTrue(rg1 is rg2)

        with mock_app({}) as app, app.app_context():
            rg3 = RoleGroup.for_user()
            self.assertTrue(rg3 is not rg1)

    def test_for_user__users(self):
        with mock_app({}) as app, app.app_context():
            user1 = MockUser(roles=['user'], permissions=[], id=1)
            user2 = MockUser(roles=['user'], permissions=[], id=2)

            rg1 = RoleGroup.for_user(user=user1)
            rg2 = RoleGroup.for_user(user=user1)
            rg3 = RoleGroup.for_user(user=user2)
            rg4 = RoleGroup.for_user(user=user2)
            self.assertTrue(rg1 is rg2)
            self.assertTrue(rg3 is rg4)
            self.assertFalse(rg1 is rg3)
