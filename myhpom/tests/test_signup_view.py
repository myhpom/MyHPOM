from django.contrib import auth
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.contrib.messages import get_messages, INFO
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from myhpom.models import State


class SignupTestCase(TestCase):
    """
    * GET retries page
    * POST invalid data returns to the page
    * POST valid data in non-supported state for non-existing user redirects to 'next_steps'
    * POST valid data in supported state for non-existing user redirects to 'choose_network'
    """

    def setUp(self):
        self.url = reverse('myhpom:signup')
        self.form_data = {
            'first_name': 'A',
            'middle_name': 'B',
            'last_name': 'C',
            'email': 'abc@example.com',
            'password': 'Abbbbbbb1@',
            'password_confirm': 'Abbbbbbb1@',
            'state': 'NC',  # a supported state
            'accept_tos': True,
        }
        State.objects.filter(name='NC') \
            .update(advance_directive_template=SimpleUploadedFile('afile.txt', ''))

    def test_get_signup(self):
        """GET the signup page should work"""
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed('myhpom/accounts/signup.html')

    def test_post_signup_invalid(self):
        """invalid signup should redisplay signup page and result in form errors"""
        data = {}  # empty signup data is certainly invalid!
        response = self.client.post(self.url, data=data)
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed('myhpom/accounts/signup.html')
        self.assertFalse(response.context['form'].is_valid())
        self.assertFalse(auth.get_user(self.client).is_authenticated())

    def test_post_signup_valid_supported(self):
        """valid signup with a supported state should:
        + redirect to choose_network
        + set message.info (don't test for the value of the message, which might change)
        + save userdetails.verification_code != None and .verification_completed = None
        """
        data = self.form_data
        data['state'] = State.objects.order_by_ad().first().name
        response = self.client.post(self.url, data=data)
        self.assertRedirects(
            response, reverse('myhpom:choose_network'), fetch_redirect_response=False
        )
        user = auth.get_user(self.client)
        self.assertTrue(user.is_authenticated())

        # test for the presence of User verification message and model values
        messages = [msg for msg in get_messages(response.wsgi_request) if msg.level == INFO]
        self.assertGreater(len(messages), 0)
        self.assertIsNotNone(user.userdetails.verification_code)
        self.assertIsNone(user.userdetails.verification_completed)

    def test_post_signup_valid_unsupported(self):
        """valid signup with an unsupported state should redirect to next_steps
        + same User verification results as in supported state
        """
        data = self.form_data
        data['state'] = State.objects.order_by_ad().last().name
        response = self.client.post(self.url, data=data)

        # test assertions
        self.assertRedirects(
            response, reverse('myhpom:next_steps'), fetch_redirect_response=False
        )
        user = auth.get_user(self.client)
        self.assertTrue(user.is_authenticated())

        # test for the presence of User verification message and model values
        messages = [msg for msg in get_messages(response.wsgi_request) if msg.level == INFO]
        self.assertGreater(len(messages), 0)
        self.assertIsNotNone(user.userdetails.verification_code)
        self.assertIsNone(user.userdetails.verification_completed)

    def test_post_signup_all_user_data(self):
        """valid signup should result in all user data being saved. (bug MH-100)"""
        data = self.form_data
        response = self.client.post(self.url, data=data)
        user = User.objects.get(email=data['email'])
        state = State.objects.get(name=data['state'])
        self.assertRedirects(
            response, reverse('myhpom:choose_network'), fetch_redirect_response=False
        )

        # User
        for key in ['first_name', 'last_name', 'email']:
            self.assertEqual(user.__getattribute__(key), data[key])
        self.assertTrue(user.check_password(data['password']))

        # UserDetails
        for key in ['middle_name', 'accept_tos']:
            self.assertEqual(user.userdetails.__getattribute__(key), data[key])
        self.assertEqual(user.userdetails.state, state)
