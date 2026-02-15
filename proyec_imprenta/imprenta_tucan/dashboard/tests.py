from django.test import TestCase

class BasicTest(TestCase):
    def test_suma_basica(self):
        self.assertEqual(1 + 1, 2)
