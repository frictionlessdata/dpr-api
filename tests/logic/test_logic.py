import unittest
import json

from mock import patch
from app import create_app
from app.database import db
from app.package.models import *
from app.profile.models import *
import app.logic as logic
from app.utils import InvalidUsage

import pytest
import tests.base as base


class DataPackageShowTest(unittest.TestCase):

    @classmethod
    def setup_class(self):
        self.publisher = 'demo'
        self.package = 'demo-package'
        self.app = create_app()
        self.app.app_context().push()
        self.descriptor = json.loads(open('fixtures/datapackage.json').read())

        with self.app.test_request_context():
            db.drop_all()
            db.create_all()
            base.create_test_package(self.publisher, self.package, self.descriptor)

    def test_get_package(self):
        # result is a dict ready for passing to templates or API
        package = logic.Package.get(self.publisher, self.package)
        self.assertEqual(package['descriptor']['name'], self.package)
        self.assertEqual(package['descriptor']['owner'], self.publisher)
        self.assertTrue(package.get('bitstore_url'))
        self.assertEqual(package['short_readme'], '')

    def test_returns_none_if_package_not_found(self):
        package = logic.Package.get(self.publisher, 'unknown')
        self.assertIsNone(package)
        package = logic.Package.get('unknown', self.package)
        self.assertIsNone(package)
        package = logic.Package.get('unknown', 'unknown')
        self.assertIsNone(package)

    @classmethod
    def teardown_class(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

class PackageTest(unittest.TestCase):

    def setUp(self):
        self.publisher = 'demo'
        self.package = 'demo-package'
        self.app = create_app()
        self.app.app_context().push()
        self.descriptor = json.loads(open('fixtures/datapackage.json').read())
        self.datapackage_url = 'https://bits.datapackaged.com/metadata/' \
                          '{pub}/{pack}/_v/latest/datapackage.com'.\
            format(pub=self.publisher, pack=self.package)

        with self.app.test_request_context():
            db.drop_all()
            db.create_all()
            base.create_test_package(self.publisher, self.package, self.descriptor)


    @patch('app.logic.Package.create_or_update')
    @patch('app.bitstore.BitStore.get_metadata_body')
    @patch('app.bitstore.BitStore.get_readme_object_key')
    @patch('app.bitstore.BitStore.get_s3_object')
    @patch('app.bitstore.BitStore.change_acl')
    def test_finalize_package_publish_returns_queued_if_fine(
                                    self, change_acl, get_s3_object,
                                    get_readme_object_key,
                                    get_metadata_body, create_or_update):
        get_metadata_body.return_value = json.dumps(dict(name='package'))
        create_or_update.return_value = None
        get_readme_object_key.return_value = ''
        get_s3_object.return_value = ''
        change_acl.return_value = None
        status = logic.Package.finalize_publish(1, self.datapackage_url)
        self.assertEqual(status, 'queued')


    @patch('app.logic.Package.create_or_update')
    @patch('app.bitstore.BitStore.get_metadata_body')
    @patch('app.bitstore.BitStore.get_readme_object_key')
    @patch('app.bitstore.BitStore.get_s3_object')
    @patch('app.bitstore.BitStore.change_acl')
    def test_finalize_package_publish_throws_400_if_publisher_does_not_exist(
                                    self, change_acl, get_s3_object,
                                    get_readme_object_key,
                                    get_metadata_body, create_or_update):
        get_metadata_body.return_value = json.dumps(dict(name='package'))
        create_or_update.return_value = None
        get_readme_object_key.return_value = ''
        get_s3_object.return_value = ''
        change_acl.return_value = None
        with self.assertRaises(InvalidUsage) as context:
            logic.Package.finalize_publish(2, self.datapackage_url)
        self.assertEqual(context.exception.status_code, 400)


    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

class TestGetJwtToken(base.TestBase):

    def test_get_jwt_token(self):
        out = logic.get_jwt_token(username='demo', secret='supersecret')
        # token are this long!
        self.assertEqual(len(out), 161)

        out = logic.get_jwt_token(email='test@test.com', secret='supersecret')
        self.assertEqual(len(out), 161)

        with pytest.raises(InvalidUsage):
            out = logic.get_jwt_token(username='demo', secret='wrongsecret')

    def teardown_class(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()

class TestGetSignedUrl(unittest.TestCase):

    publisher = 'test_publisher'
    package = 'test_package'
    user_id = 1

    @classmethod
    def setup_class(self):
        self.app = create_app()
        self.client = self.app.test_client()
        with self.app.app_context():
            db.drop_all()
            db.create_all()
            base.make_fixtures(self.app, self.package, self.publisher, self.user_id)

    def test_generate_signed_url_is_ok(self):
        data = {
            'metadata': {
                "owner": self.publisher,
                "name": self.package
            },
            "filedata": {
                "datapackage.json": {
                    "name": "datapackage.json",
                    "md5": "12345y65uyhgfed23243y6"
                }
            }
        }
        file_data = logic.generate_signed_url(1, data)
        self.assertTrue('filedata' in file_data)

        file_info = file_data['filedata']['datapackage.json']
        self.assertEqual(file_info.get('name'), 'datapackage.json')

        upload_query = file_info.get('upload_query')
        self.assertEqual(upload_query.get('key'),
            'metadata/test_publisher/test_package/_v/latest/datapackage.json')
        self.assertEqual(upload_query.get('Content-Type'), 'text/plain')
        self.assertEqual(upload_query.get('acl'), 'public-read')

    def test_generate_signed_url_fails_if_not_an_owner(self):
        data = {
            'metadata': {
                "owner": self.publisher,
                "name": self.package
            },
            "filedata": {
                "datapackage.json": {
                    "name": "datapackage.json",
                    "md5": "12345y65uyhgfed23243y6"
                }
            }
        }
        with pytest.raises(InvalidUsage):
            out = logic.generate_signed_url(2, data)

    @classmethod
    def teardown_class(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()

class HelpersTest(unittest.TestCase):

    @classmethod
    def setup_class(self):
        self.descriptor = json.loads(open('fixtures/datapackage.json').read())


    def test_validate_for_jinja_returns_descriptor_if_no_licenses(self):
        descriptor = logic.validate_for_template(self.descriptor)
        self.assertEqual(self.descriptor, descriptor)

    def test_validate_for_jinja_returns_descriptor_if_licenses_is_list(self):
        self.descriptor['licenses'] = []
        descriptor = logic.validate_for_template(self.descriptor)
        self.assertEqual(self.descriptor, descriptor)

    def test_validate_for_jinja_modifies_descriptor_if_licenses_is_dict(self):
        self.descriptor['licenses'] = {'url': 'test/url', 'type': 'Test'}
        descriptor = logic.validate_for_template(self.descriptor)
        self.assertEqual(descriptor['license'], 'Test')

    def test_validate_for_not_errors_if_licenses_is_dict_and_has_no_type_key(self):
        self.descriptor['licenses'] = {'url': 'test/url'}
        descriptor = logic.validate_for_template(self.descriptor)
        self.assertEqual(descriptor['license'], None)

    def test_validate_for_jinja_removes_licenses_if_invalid_type(self):
        self.descriptor['licenses'] = 1
        descriptor = logic.validate_for_template(self.descriptor)
        self.assertEqual(descriptor.get('licenses'), None)
