from unittest import TestCase

from bc_fsf_user.mixins import CompareProperty


class TestComparePropMixin(TestCase):
    def test_compare_prop(self):
        class tc(CompareProperty('foo')):
            def __init__(self, v):
                self.foo = v

        t_one = tc(1)
        t_one_2 = tc(1)
        t_two = tc(2)

        self.assertFalse(t_one == None)
        self.assertTrue(t_one != None)

        with self.assertRaisesRegex(ValueError, 'Incompatible type'):
            _ = t_one < None
        with self.assertRaisesRegex(ValueError, 'Incompatible type'):
            _ = t_one <= None
        with self.assertRaisesRegex(ValueError, 'Incompatible type'):
            _ = t_one > None
        with self.assertRaisesRegex(ValueError, 'Incompatible type'):
            _ = t_one >= None

        self.assertTrue(t_one == t_one_2)
        self.assertFalse(t_one == t_two)

        self.assertTrue(t_one != t_two)
        self.assertFalse(t_one != t_one_2)

        self.assertTrue(t_one < t_two)
        self.assertFalse(t_two < t_one)

        self.assertTrue(t_one <= t_one_2)
        self.assertFalse(t_two <= t_one)

        self.assertTrue(t_two > t_one)
        self.assertFalse(t_one > t_two)

        self.assertTrue(t_one >= t_one_2)
        self.assertTrue(t_two >= t_one)
        self.assertFalse(t_one >= t_two)
