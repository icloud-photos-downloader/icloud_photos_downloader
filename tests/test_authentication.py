import unittest
from icloudpd.authentication import authenticate, TwoStepAuthRequiredError
import pyicloud

class AuthenticationTestCase(unittest.TestCase):
    def test_failed_authentication(self):
        with self.assertRaises(pyicloud.exceptions.PyiCloudFailedLoginException) as context:
            authenticate('bad_username', 'bad_password')

        self.assertTrue(
            'Invalid email/password combination.' in context.exception)


    # def test_2sa_required_authentication(self):
    #     with self.assertRaises(TwoStepAuthRequiredError) as context:
    #         authenticate('username', 'password', True)

    #     self.assertTrue(
    #         'Two-step/two-factor authentication is required!' in context.exception)
