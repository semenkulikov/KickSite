from django.test import TestCase
from .models import KickAccount
from django.contrib.auth import get_user_model

# Create your tests here.

class KickAccountTest(TestCase):
    def test_create_kick_account(self):
        user = get_user_model().objects.create(username='testuser')
        acc = KickAccount.objects.create(login='kickuser', token='token', user=user)
        self.assertEqual(acc.login, 'kickuser')
