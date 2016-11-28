# -*- coding: utf-8 -*-
from __future__ import division
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import boto3
from urlparse import urlparse

from botocore.exceptions import ParamValidationError
from moto import mock_s3
import unittest
import json
from app import create_app
from app.database import db
from app.mod_api.models import BitStore, MetaDataDB, User, Publisher, PublisherUser


class BitStoreTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app()

    def test_metadata_s3_key(self):
        metadata = BitStore(publisher="pub_test", package="test_package")
        expected = "{t}/pub_test/test_package/_v/latest/datapackage.json".\
                   format(t=metadata.prefix)
        self.assertEqual(expected, metadata.build_s3_key('datapackage.json'))

    def test_metadata_s3_prefix(self):
        metadata = BitStore(publisher="pub_test", package="test_package")
        expected = "{t}/pub_test".format(t=metadata.prefix)
        self.assertEqual(expected, metadata.build_s3_prefix())

    @mock_s3
    def test_save(self):
        with self.app.app_context():
            s3 = boto3.client('s3')
            bucket_name = self.app.config['S3_BUCKET_NAME']
            s3.create_bucket(Bucket=bucket_name)
            metadata = BitStore(publisher="pub_test",
                                package="test_package",
                                body='hi')
            key = metadata.build_s3_key('datapackage.json')
            metadata.save()
            obs_list = list(s3.list_objects(Bucket=bucket_name, Prefix=key).\
                            get('Contents'))
            self.assertEqual(1, len(obs_list))
            self.assertEqual(key, obs_list[0]['Key'])

    @mock_s3
    def test_get_metadata_body(self):
        with self.app.app_context():
            s3 = boto3.client('s3')
            bucket_name = self.app.config['S3_BUCKET_NAME']
            s3.create_bucket(Bucket=bucket_name)
            metadata = BitStore(publisher="pub_test",
                                package="test_package",
                                body='hi')
            s3.put_object(
                Bucket=bucket_name,
                Key=metadata.build_s3_key('datapackage.json'),
                Body=metadata.body)
            self.assertEqual(metadata.body, metadata.get_metadata_body())

    @mock_s3
    def test_get_all_metadata_name_for_publisher(self):
        with self.app.app_context():
            s3 = boto3.client('s3')
            bucket_name = self.app.config['S3_BUCKET_NAME']
            s3.create_bucket(Bucket=bucket_name)
            metadata = BitStore(publisher="pub_test",
                                package="test_package",
                                body='hi')
            s3.put_object(
                Bucket=bucket_name,
                Key=metadata.build_s3_key('datapackage.json'),
                Body=metadata.body)
            self.assertEqual(1, len(metadata.get_all_metadata_name_for_publisher()))

    @mock_s3
    def test_get_empty_metadata_name_for_publisher(self):
        with self.app.app_context():
            s3 = boto3.client('s3')
            bucket_name = self.app.config['S3_BUCKET_NAME']
            s3.create_bucket(Bucket=bucket_name)
            metadata = BitStore(publisher="pub_test",
                                package="test_package",
                                body='hi')
            s3.put_object(Bucket=bucket_name,
                          Key='test/key.json',
                          Body=metadata.body)
            self.assertEqual(0, len(metadata.get_all_metadata_name_for_publisher()))

    @mock_s3
    def test_generate_pre_signed_put_obj_url(self):
        with self.app.app_context():
            s3 = boto3.client('s3')
            bucket_name = self.app.config['S3_BUCKET_NAME']
            s3.create_bucket(Bucket=bucket_name)

            metadata = BitStore(publisher="pub_test",
                                package="test_package",
                                body='hi')
            url = metadata.generate_pre_signed_put_obj_url('datapackage.json', 'm')
            parsed = urlparse(url)
            self.assertEqual(parsed.netloc, 's3-{region}.amazonaws.com'.format(region=self.app.config['AWS_REGION']))

    @mock_s3
    def test_get_readme_object_key(self):
        with self.app.app_context():
            bit_store = BitStore('test_pub', 'test_package')
            s3 = boto3.client('s3')
            bucket_name = self.app.config['S3_BUCKET_NAME']
            s3.create_bucket(Bucket=bucket_name)
            read_me_key = bit_store.build_s3_key('readme.md')
            s3.put_object(Bucket=bucket_name, Key=read_me_key, Body='')
            self.assertEqual(bit_store.get_readme_object_key(), read_me_key)

    @mock_s3
    def test_return_none_if_no_readme_found(self):
        with self.app.app_context():
            bit_store = BitStore('test_pub', 'test_package')
            s3 = boto3.client('s3')
            bucket_name = self.app.config['S3_BUCKET_NAME']
            s3.create_bucket(Bucket=bucket_name)
            read_me_key = bit_store.build_s3_key('test.md')
            s3.put_object(Bucket=bucket_name, Key=read_me_key, Body='')
            self.assertEqual(bit_store.get_readme_object_key(), None)

    @mock_s3
    def test_return_none_if_object_found(self):
        with self.app.app_context():
            bit_store = BitStore('test_pub', 'test_package')
            s3 = boto3.client('s3')
            bucket_name = self.app.config['S3_BUCKET_NAME']
            s3.create_bucket(Bucket=bucket_name)
            read_me_key = bit_store.build_s3_key('test.md')
            s3.put_object(Bucket=bucket_name, Key=read_me_key, Body='')
            self.assertEqual(bit_store.get_s3_object(read_me_key + "testing"), None)
            self.assertEqual(bit_store.get_s3_object(None), None)


class MetaDataDBTestCase(unittest.TestCase):

    def setUp(self):
        self.publisher_one = 'test_publisher1'
        self.publisher_two = 'test_publisher2'
        self.package_one = 'test_package1'
        self.package_two = 'test_package2'
        self.app = create_app()
        self.app.app_context().push()

        with self.app.test_request_context():
            db.drop_all()
            db.create_all()

            user1 = User(name=self.publisher_one)
            publisher1 = Publisher(name=self.publisher_one)
            association1 = PublisherUser(role="OWNER")
            association1.publisher = publisher1
            user1.publishers.append(association1)

            user2 = User(name=self.publisher_two)
            publisher2 = Publisher(name=self.publisher_two)
            association2 = PublisherUser(role="OWNER")
            association2.publisher = publisher2
            user2.publishers.append(association2)

            metadata1 = MetaDataDB(name=self.package_one)
            metadata1.descriptor = json.dumps(dict(name='test_one'))
            publisher1.packages.append(metadata1)

            metadata2 = MetaDataDB(name=self.package_two)
            metadata2.descriptor = json.dumps(dict(name='test_two'))
            publisher1.packages.append(metadata2)

            metadata3 = MetaDataDB(name=self.package_one)
            metadata3.descriptor = json.dumps(dict(name='test_three'))
            publisher2.packages.append(metadata3)

            metadata4 = MetaDataDB(name=self.package_two)
            metadata4.descriptor = json.dumps(dict(name='test_four'))
            publisher2.packages.append(metadata4)

            db.session.add(user1)
            db.session.add(user2)

            db.session.commit()

    def test_composite_key(self):
        res = MetaDataDB.query.join(Publisher).filter(Publisher.name ==
                                                      self.publisher_one).all()
        self.assertEqual(2, len(res))

    def test_update_fields_if_instance_present(self):
        metadata = MetaDataDB.query.join(Publisher)\
            .filter(Publisher.name == self.publisher_one,
                    MetaDataDB.name == self.package_one).one()
        self.assertEqual(json.loads(metadata.descriptor)['name'], "test_one")
        MetaDataDB.create_or_update(self.package_one, self.publisher_one,
                                    descriptor=json.dumps(dict(name='sub')),
                                    private=True)
        metadata = MetaDataDB.query.join(Publisher) \
            .filter(Publisher.name == self.publisher_one,
                    MetaDataDB.name == self.package_one).one()
        self.assertEqual(json.loads(metadata.descriptor)['name'], "sub")
        self.assertEqual(metadata.private, True)

    def test_insert_if_not_present(self):
        pub = self.publisher_two
        name = "custom_name"

        metadata = MetaDataDB.query.join(Publisher) \
            .filter(Publisher.name == pub,
                    MetaDataDB.name == name).all()
        self.assertEqual(len(metadata), 0)
        MetaDataDB.create_or_update(name, pub,
                                    descriptor=json.dumps(dict(name='sub')),
                                    private=True)
        metadata = MetaDataDB.query.join(Publisher) \
            .filter(Publisher.name == pub,
                    MetaDataDB.name == name).all()
        self.assertEqual(len(metadata), 1)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()


class UserTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.app_context().push()
        with self.app.test_request_context():
            db.drop_all()
            db.create_all()

            user = User(id=11,
                        name='test_user_id',
                        secret='supersecret',
                        auth0_id="123|auth0")
            publisher = Publisher(name='test_pub_id')
            association = PublisherUser(role="OWNER")

            publisher1 = Publisher(name='test_pub')
            association1 = PublisherUser(role="MEMBER")
            association1.publisher = publisher1

            association.publisher = publisher
            user.publishers.append(association)
            user.publishers.append(association1)

            db.session.add(user)
            db.session.commit()

    def test_serialize(self):
        user = User.query.filter_by(name='test_user_id').one()\
            .serialize
        self.assertEqual('test_user_id', user['name'])

    def test_user_role_on_publisher(self):
        user = User.query.filter_by(name='test_user_id').one()
        self.assertEqual(len(user.publishers), 2)
        self.assertEqual(user.publishers[0].role, 'OWNER')

    def test_user_creation_from_outh0_response(self):
        user_info = dict(email="test@test.com",
                         username="test",
                         user_id="124|auth0")
        user = User.create_or_update_user_from_callback(user_info)
        self.assertEqual(user.name, 'test')

    def test_update_secret_if_it_is_supersecret(self):
        user_info = dict(email="test@test.com",
                         username="test",
                         user_id="123|auth0")
        user = User.create_or_update_user_from_callback(user_info)
        self.assertNotEqual('supersecret', user.secret)

    def test_get_userinfo_by_id(self):
        self.assertEqual(User.get_userinfo_by_id(11).name, 'test_user_id')
        self.assertIsNone(User.get_userinfo_by_id(2))

    def test_get_user_roles(self):
        role_one = User.get_user_role(11, 'test_pub_id')
        role_two = User.get_user_role(11, 'test_pub')
        role_three = User.get_user_role(12, 'test_pub_none')
        self.assertEqual(role_one, 'OWNER')
        self.assertEqual(role_two, 'MEMBER')
        self.assertIsNone(role_three)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
