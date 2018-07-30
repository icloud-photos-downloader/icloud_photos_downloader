import unittest
from vcr import VCR
from icloudpd.authentication import authenticate, TwoStepAuthRequiredError
import pyicloud_ipd

vcr = VCR(decode_compressed_response=True)

class AuthenticationTestCase(unittest.TestCase):
    def test_failed_auth(self):
        with vcr.use_cassette('tests/vcr_cassettes/failed_auth.yml'):
            with self.assertRaises(pyicloud_ipd.exceptions.PyiCloudFailedLoginException) as context:
                authenticate('bad_username', 'bad_password',
                             client_id='EC5646DE-9423-11E8-BF21-14109FE0B321')

        self.assertTrue(
            'Invalid email/password combination.' in context.exception)

    def test_2sa_required(self):
        with vcr.use_cassette('tests/vcr_cassettes/auth_requires_2sa.yml'):
            with self.assertRaises(TwoStepAuthRequiredError) as context:
                # To re-record this HTTP request,
                # delete ./tests/vcr_cassettes/auth_requires_2sa.yml,
                # put your actual credentials in here, run the test,
                # and then replace with dummy credentials.
                authenticate('jdoe@gmail.com',
                             'password1',
                             raise_error_on_2sa=True,
                             client_id='EC5646DE-9423-11E8-BF21-14109FE0B321')

            self.assertTrue(
                'Two-step/two-factor authentication is required!' in context.exception)

    def test_successful_auth(self):
        with vcr.use_cassette('tests/vcr_cassettes/successful_auth.yml'):
            authenticate('jdoe@gmail.com',
                         'password1',
                         client_id='EC5646DE-9423-11E8-BF21-14109FE0B321')
