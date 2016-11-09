import unittest
import json

from mock import patch

from app import create_app
from app.database import db
from app.mod_api.models import User, MetaDataDB


class AuthTokenTestCase(unittest.TestCase):
    auth_token_url = '/api/auth/token'

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            self.user = User()
            self.user.user_id = 'trial_id'
            self.user.email, self.user.user_name, self.user.secret = \
                'test@test.com', 'test_user', 'super_secret'
            db.session.add(self.user)
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_throw_400_if_user_name_and_email_is_none(self):
        rv = self.client.post(self.auth_token_url,
                              data=json.dumps({
                                  'username': None,
                                  'email': None
                              }),
                              content_type='application/json')
        data = json.loads(rv.data)
        assert rv.status_code == 400
        assert data['error_code'] == 'INVALID_INPUT'

    def test_throw_400_if_secret_is_none(self):
        rv = self.client.post(self.auth_token_url,
                              data=json.dumps({
                                  'username': 'test',
                                  'secret': None,
                              }),
                              content_type='application/json')
        assert rv.status_code == 400
        data = json.loads(rv.data)
        assert data['error_code'] == 'INVALID_INPUT'

    def test_throw_404_if_user_id_do_not_exists(self):
        rv = self.client.post(self.auth_token_url,
                              data=json.dumps({
                                  'username': "not_found_user",
                                  'email': None,
                                  'secret': 'super_secret'
                              }),
                              content_type='application/json')
        data = json.loads(rv.data)
        self.assertEqual(rv.status_code, 404)
        self.assertEqual(data['error_code'], 'USER_NOT_FOUND')

    def test_throw_404_if_user_email_do_not_exists(self):
        rv = self.client.post(self.auth_token_url,
                              data=json.dumps({
                                  'username': None,
                                  'email': 'test1@test.com',
                                  'secret': 'super_secret'
                              }),
                              content_type='application/json')
        data = json.loads(rv.data)
        self.assertEqual(rv.status_code, 404)
        self.assertEqual(data['error_code'], 'USER_NOT_FOUND')

    def test_throw_403_if_user_name_and_secret_key_does_not_match(self):
        rv = self.client.post(self.auth_token_url,
                              data=json.dumps({
                                  'username': 'test_user',
                                  'email': None,
                                  'secret': 'super_secret1'
                              }),
                              content_type='application/json')
        data = json.loads(rv.data)
        self.assertEqual(rv.status_code, 403)
        self.assertEqual(data['error_code'], 'SECRET_ERROR')

    def test_throw_403_if_email_and_secret_key_does_not_match(self):
        rv = self.client.post(self.auth_token_url,
                              data=json.dumps({
                                  'username': None,
                                  'email': 'test@test.com',
                                  'secret': 'super_secret1'
                              }),
                              content_type='application/json')
        data = json.loads(rv.data)
        self.assertEqual(rv.status_code, 403)
        self.assertEqual(data['error_code'], 'SECRET_ERROR')

    def test_throw_500_if_exception_occours(self):
        rv = self.client.post(self.auth_token_url,
                              data="'username': None,",
                              content_type='application/json')
        data = json.loads(rv.data)
        self.assertEqual(rv.status_code, 500)
        self.assertEqual(data['error_code'], 'GENERIC_ERROR')

    def test_return_200_if_email_and_secret_matches(self):
        rv = self.client.post(self.auth_token_url,
                              data=json.dumps({
                                  'username': None,
                                  'email': 'test@test.com',
                                  'secret': 'super_secret'
                              }),
                              content_type='application/json')
        self.assertEqual(rv.status_code, 200)

    def test_return_200_if_user_id_and_secret_matches(self):
        rv = self.client.post(self.auth_token_url,
                              data=json.dumps({
                                  'username': 'test_user',
                                  'email': None,
                                  'secret': 'super_secret'
                              }),
                              content_type='application/json')
        self.assertEqual(rv.status_code, 200)


class GetMetaDataTestCase(unittest.TestCase):
    def setUp(self):
        self.publisher = 'test_publisher'
        self.package = 'test_package'
        self.app = create_app()
        self.client = self.app.test_client()
        with self.app.app_context():
            db.drop_all()
            db.create_all()

    def test_throw_404_if_meta_data_not_found(self):
        response = self.client.get('/api/package/%s/%s' % (self.publisher, self.package))
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(data['error_code'], 'DATA_NOT_FOUND')

    def test_return_200_if_meta_data_found(self):
        descriptor = {'name': 'test description'}
        with self.app.app_context():
            metadata = MetaDataDB(self.package, self.publisher)
            metadata.descriptor = json.dumps(descriptor)
            db.session.add(metadata)
            db.session.commit()
        response = self.client.get('/api/package/%s/%s' % (self.publisher, self.package))
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['data']['name'], 'test description')

    def test_return_generic_error_if_descriptor_is_not_json(self):
        descriptor = 'test description'
        with self.app.app_context():
            metadata = MetaDataDB(self.package, 'pub')
            metadata.descriptor = descriptor
            db.session.add(metadata)
            db.session.commit()
        response = self.client.get('/api/package/%s/%s' % ('pub', self.package))
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(data['error_code'], 'GENERIC_ERROR')

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()


class GetAllMetaDataTestCase(unittest.TestCase):
    def setUp(self):
        self.publisher = 'test_publisher'
        self.package1 = 'test_package1'
        self.package2 = 'test_package2'
        self.app = create_app()
        self.client = self.app.test_client()
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            metadata1 = MetaDataDB(self.package1, self.publisher)
            metadata2 = MetaDataDB(self.package2, self.publisher)
            db.session.add(metadata1)
            db.session.add(metadata2)
            db.session.commit()

    def test_throw_404_if_publisher_not_found(self):
        response = self.client.get('/api/package/%s' % ('fake_publisher',))
        self.assertEqual(response.status_code, 404)

    def test_return_200_if_data_found(self):
        response = self.client.get('/api/package/%s' % (self.publisher,))
        data = json.loads(response.data)
        self.assertEqual(len(data['data']), 2)
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()


class GetS3SignedUrlTestCase(unittest.TestCase):
    url = '/api/auth/bitstore_upload'

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_throw_400_if_package_is_None(self):
        rv = self.client.post(self.url,
                              data=json.dumps({
                                  'publisher': 'test_publisher',
                                  'package': None
                              }),
                              content_type='application/json')
        self.assertEqual(400, rv.status_code)

    def test_throw_400_if_publisher_is_None(self):
        rv = self.client.post(self.url,
                              data=json.dumps({
                                  'publisher': None,
                                  'package': 'test_package'
                              }),
                              content_type='application/json')
        self.assertEqual(400, rv.status_code)

    @patch('app.mod_api.models.MetaDataS3.generate_pre_signed_put_obj_url')
    def test_200_if_all_right(self, signed_url):
        signed_url.return_value = 'https://trial_url'
        response = self.client.post(self.url,
                                    data=json.dumps({
                                        'publisher': 'test_publisher',
                                        'package': 'test_package'
                                    }),
                                    content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual('https://trial_url', data['key'])


class SaveMetaDataTestCase(unittest.TestCase):
    publisher = 'test_publisher'
    package = 'test_package'
    user_id = 'trial_id'
    url = '/api/package/%s/%s' % (publisher, package)
    jwt_url = '/api/auth/token'

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            self.user = User()
            self.user.user_id = self.user_id
            self.user.email, self.user.user_name, self.user.secret = \
                'test@test.com', self.publisher, 'super_secret'
            db.session.add(self.user)
            db.session.commit()
        response = self.client.post(self.jwt_url,
                                    data=json.dumps({
                                        'username': self.publisher,
                                        'secret': 'super_secret'
                                    }),
                                    content_type='application/json')
        data = json.loads(response.data)
        self.jwt = data['token']

    def test_should_throw_error_if_auth_header_missing(self):
        response = self.client.put(self.url)
        self.assertEqual(401, response.status_code)

    def test_should_throw_error_if_auth_header_not_starts_with_bearer(self):
        response = self.client.put(self.url, headers=dict(Authorization='auth 123'))
        self.assertEqual(401, response.status_code)

    def test_should_throw_error_if_auth_header_malformed(self):
        response = self.client.put(self.url, headers=dict(Authorization='bearer123'))
        self.assertEqual(401, response.status_code)

        response = self.client.put(self.url, headers=dict(Authorization='bearer 123 231'))
        self.assertEqual(401, response.status_code)

    @patch('app.mod_api.models.MetaDataS3.save')
    def test_return_200_if_all_right(self, save):
        save.return_value = None
        auth = "bearer %s" % self.jwt
        response = self.client.put(self.url, headers=dict(Authorization=auth), data=json.dumps({'name': 'package'}))
        self.assertEqual(200, response.status_code)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()


class CallbackHandlingTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    @patch('app.mod_api.controllers.get_user_info_with_code')
    def test_throw_500_if_error_getting_user_info_from_auth0(self, get_user):
        get_user.return_value = None

        response = self.client.get('/api/auth/callback?code=123')
        self.assertTrue(get_user.called)

        data = json.loads(response.data)

        self.assertEqual(data['error_code'], 'GENERIC_ERROR')
        self.assertEqual(response.status_code, 500)

    @patch('app.mod_api.controllers.get_user_info_with_code')
    @patch('app.mod_api.controllers.update_user_secret_from_user_info')
    @patch('app.mod_api.controllers.get_user')
    @patch('app.mod_api.models.User.create_or_update_user_from_callback')
    def test_return_200_if_all_right(self, get_user_with_code, update_user_secret,
                                     get_user, create_user):
        get_user_with_code('123').side_effect = {'user_id': "test_id", "user_metadata": {"secr": "tt"}}
        response = self.client.get('/api/auth/callback?code=123')
        self.assertEqual(update_user_secret.call_count, 1)
        self.assertEqual(get_user.call_count, 1)
        self.assertEqual(create_user.call_count, 1)

        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
