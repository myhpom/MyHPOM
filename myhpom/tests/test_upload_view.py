from mock import patch
import os
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.test import TestCase, override_settings
from django.utils.timezone import now

from myhpom.models import AdvanceDirective
from myhpom.tests.factories import UserFactory

PDF_FILENAME = os.path.join(os.path.dirname(__file__), 'fixtures', 'afile.pdf')


class UploadMixin:
    def _setup_user_and_login(self):
        user = UserFactory()
        user.set_password('password')
        user.save()
        self.assertTrue(self.client.login(username=user.email, password='password'))
        return user

    def test_not_logged_in(self):
        # A user must be logged in to see their dashboard:
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(401, response.status_code)

    def test_non_ajax_get(self):
        # Renders the proper template on GET:
        self._setup_user_and_login()
        response = self.client.get(self.url)
        self.assertEqual(403, response.status_code)


class GETMixin(UploadMixin):
    def test_get(self):
        # Renders the proper template on GET:
        self._setup_user_and_login()
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed('myhpom/upload/requirements.html')


class UploadIndexTestCase(GETMixin, TestCase):
    def setUp(self):
        self.url = reverse('myhpom:upload_index')


class UploadCurrentAdTestCase(UploadMixin, TestCase):
    def setUp(self):
        self.url = reverse('myhpom:upload_current_ad')

    def test_get(self):
        # Users that don't yet have an AD are not allowed
        user = self._setup_user_and_login()
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(403, response.status_code)

        # When the user does have an advancedirective, they can visit the page.
        advancedirective = AdvanceDirective(user=user, valid_date=now(), share_with_ehs=False)
        advancedirective.save()


class UploadSharingTestCase(UploadMixin, TestCase):
    def setUp(self):
        self.url = reverse('myhpom:upload_sharing')

    def test_not_logged_in(self):
        response = self.client.get(self.url)
        self.assertEqual(403, response.status_code)

    def test_get(self):
        # When GETting, and the user has no advancedirective are forbidden
        user = self._setup_user_and_login()
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(403, response.status_code)

        # When the user has an advancedirective, show the sharing prefs:
        directive = AdvanceDirective(user=user, share_with_ehs=False, valid_date=now())
        directive.save()
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed('myhpom/upload/sharing.html')

    def test_post(self):
        # When POSTEDing - even no data is sufficient to succeed and redirect
        user = self._setup_user_and_login()
        directive = AdvanceDirective(user=user, share_with_ehs=False, valid_date=now())
        directive.save()
        response = self.client.post(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertRedirects(
            response, reverse('myhpom:upload_current_ad'), fetch_redirect_response=False
        )
        self.assertFalse(user.advancedirective.share_with_ehs)

        # Checking the share box saves the result.
        response = self.client.post(
            self.url, {'share_with_ehs': True}, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertRedirects(
            response, reverse('myhpom:upload_current_ad'), fetch_redirect_response=False
        )
        user.advancedirective.refresh_from_db()
        self.assertTrue(user.advancedirective.share_with_ehs)


class DirectiveUploadRequirementsTestCase(GETMixin, TestCase):
    def setUp(self):
        self.url = reverse('myhpom:upload_requirements')
        with open(PDF_FILENAME, 'rb') as f:
            self.pdfdata = f.read()

    @patch('myhpom.views.upload.CloudFactorySubmitDocumentRun')
    def test_POST_valid_date_for_unsupported_state(self, task_patch):
        user = self._setup_user_and_login()
        document = SimpleUploadedFile(os.path.basename(PDF_FILENAME), self.pdfdata)
        post_data = {'valid_date': '2018-01-01', 'document': document}
        response = self.client.post(
            self.url, data=post_data, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertRedirects(
            response, reverse('myhpom:upload_current_ad'), fetch_redirect_response=False
        )
        self.assertEqual(
            post_data['valid_date'], user.advancedirective.valid_date.strftime('%Y-%m-%d')
        )
        # On success the document, thumbnail & documenturl are created and CF
        # task are queued.
        self.assertIsNotNone(user.advancedirective.document)
        self.assertIsNotNone(user.advancedirective.thumbnail)
        self.assertEqual(1, user.advancedirective.documenturl_set.count())
        task_patch.delay.assert_called_once_with(
            user.advancedirective.documenturl_set.first().pk, 'testserver')

        # Subsequent posts do not cause more tasks/documents to be created
        response = self.client.post(
            self.url, data=post_data, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertRedirects(
            response, reverse('myhpom:upload_current_ad'), fetch_redirect_response=False
        )
        self.assertIsNotNone(user.advancedirective.document)
        self.assertIsNotNone(user.advancedirective.thumbnail)
        self.assertEqual(1, user.advancedirective.documenturl_set.count())
        task_patch.delay.assert_called_once_with(
            user.advancedirective.documenturl_set.first().pk, 'testserver')

    @patch('myhpom.views.upload.CloudFactorySubmitDocumentRun')
    def test_POST_valid_date_for_supported_state(self, task_patch):
        user = self._setup_user_and_login()
        user.userdetails.state.advance_directive_template = SimpleUploadedFile('ad.pdf', '')
        user.userdetails.state.save()
        document = SimpleUploadedFile(os.path.basename(PDF_FILENAME), self.pdfdata)
        post_data = {'valid_date': '2018-01-01', 'document': document}
        response = self.client.post(
            self.url, data=post_data, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertRedirects(
            response, reverse('myhpom:upload_sharing'), fetch_redirect_response=False
        )
        self.assertEqual(
            post_data['valid_date'], user.advancedirective.valid_date.strftime('%Y-%m-%d')
        )
        # On success the document, thumbnail & documenturl are created and CF
        # task are queued.
        self.assertIsNotNone(user.advancedirective.document)
        self.assertIsNotNone(user.advancedirective.thumbnail)
        self.assertEqual(1, user.advancedirective.documenturl_set.count())
        task_patch.delay.assert_called_with(
            user.advancedirective.documenturl_set.first().pk, 'testserver')

    @patch('myhpom.views.upload.CloudFactorySubmitDocumentRun')
    def test_POST_invalid_date(self, task_patch):
        user = self._setup_user_and_login()
        document = SimpleUploadedFile(os.path.basename(PDF_FILENAME), self.pdfdata)
        post_data = {'valid_date': '', 'document': document}
        response = self.client.post(
            self.url, data=post_data, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed('myhpom/upload/requirements.html')
        self.assertFalse(hasattr(user, 'advancedirective'))
        self.assertFalse(task_patch.delay.called)

    @patch('myhpom.views.upload.CloudFactorySubmitDocumentRun')
    def test__POST_invalid_filename(self, task_patch):
        user = self._setup_user_and_login()
        post_data = {
            'valid_date': '2018-01-01',
            'document': SimpleUploadedFile('afile.txt', 'binary_contents'),
        }
        response = self.client.post(
            self.url, data=post_data, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed('myhpom/upload/requirements.html')
        self.assertFalse(hasattr(user, 'advancedirective'))
        self.assertFalse(task_patch.delay.called)

    @patch('myhpom.views.upload.CloudFactorySubmitDocumentRun')
    @override_settings(MAX_AD_SIZE=10)
    def test_POST_invalid_filesize(self, task_patch):
        user = self._setup_user_and_login()
        document = SimpleUploadedFile(os.path.basename(PDF_FILENAME), self.pdfdata)
        post_data = {'valid_date': '2018-01-01', 'document': document}
        response = self.client.post(
            self.url, data=post_data, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed('myhpom/upload/requirements.html')
        self.assertFalse(hasattr(user, 'advancedirective'))
        self.assertFalse(task_patch.delay.called)

    @patch('myhpom.views.upload.CloudFactorySubmitDocumentRun')
    def test_POST_duplicate_filenames(self, task_patch):
        """
        Confirm that files are (as expected, not necessarily as desired)
        renamed to avoid name collisions on the filesystem but are available by
        their original names via the `filename` property.
        """
        og_name = os.path.basename(PDF_FILENAME)
        user = self._setup_user_and_login()
        document = SimpleUploadedFile(os.path.basename(PDF_FILENAME), self.pdfdata)
        post_data = {'valid_date': '2018-01-01', 'document': document}
        self.client.post(self.url, data=post_data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertIsNotNone(user.advancedirective.document)
        self.assertIsNotNone(user.advancedirective.thumbnail)
        self.assertEqual(og_name, user.advancedirective.filename)
        old_name = user.advancedirective.document.name

        user.advancedirective.delete()

        # We should be able to repeat this operation after clearing the
        # old AD and still see the correct filename value
        with open(PDF_FILENAME, 'rb') as f:
            new_file = SimpleUploadedFile(og_name, f.read())
        post_data = {'valid_date': '2018-01-01', 'document': new_file}
        self.client.post(self.url, data=post_data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        user = User.objects.get(pk=user.pk)
        self.assertIsNotNone(user.advancedirective.document)
        self.assertIsNotNone(user.advancedirective.thumbnail)
        self.assertNotEqual(old_name, user.advancedirective.document.name)
        self.assertEqual(og_name, user.advancedirective.filename)
        self.assertEqual(1, user.advancedirective.documenturl_set.count())
        task_patch.delay.assert_called_with(
            user.advancedirective.documenturl_set.first().pk, 'testserver')


class UploadDeleteTestCase(UploadMixin, TestCase):
    url = reverse('myhpom:upload_delete_ad')

    def test_not_logged_in(self):
        # A user must be logged in to see their dashboard:
        response = self.client.post(self.url)
        self.assertEqual(403, response.status_code)

    def test_non_ajax_get(self):
        self._setup_user_and_login()
        response = self.client.get(self.url)
        self.assertEqual(405, response.status_code)

    def test_not_ajax_post_rejected(self):
        user = self._setup_user_and_login()
        advancedirective = AdvanceDirective(user=user, valid_date=now(), share_with_ehs=False)
        advancedirective.save()
        response = self.client.post(self.url)
        self.assertEqual(403, response.status_code)

    def test_deletes_ad(self):
        user = self._setup_user_and_login()
        advancedirective = AdvanceDirective(user=user, valid_date=now(), share_with_ehs=False)
        advancedirective.save()
        self.assertTrue(hasattr(user, 'advancedirective'))
        self.assertEqual(advancedirective, user.advancedirective)

        response = self.client.post(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertRedirects(
            response, reverse('myhpom:upload_index'), fetch_redirect_response=False)
        user = User.objects.get(id=user.id)
        self.assertFalse(hasattr(user, 'advancedirective'))

        # doing this twice should be fine
        response = self.client.post(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertRedirects(
            response, reverse('myhpom:upload_current_ad'), fetch_redirect_response=False)
        user = User.objects.get(id=user.id)
        self.assertFalse(hasattr(user, 'advancedirective'))

    def test_deletes_ad_with_redirect(self):
        user = self._setup_user_and_login()

        # the redirect parameter doesn't get used if there is no AD
        response = self.client.post(
            self.url + '?redirect=/someotherurl', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertRedirects(
            response, reverse('myhpom:upload_current_ad'), fetch_redirect_response=False)

        advancedirective = AdvanceDirective(user=user, valid_date=now(), share_with_ehs=False)
        advancedirective.save()
        response = self.client.post(
            self.url + '?redirect=/someotherurl', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertRedirects(response, '/someotherurl', fetch_redirect_response=False)
