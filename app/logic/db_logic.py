# -*- coding: utf-8 -*-
from __future__ import division
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import os

from app.bitstore import BitStore
from app.database import db
from app.profile.models import User, Publisher, PublisherUser, UserRoleEnum
from app.package.models import Package, PackageStateEnum, PackageTag
from app.utils import InvalidUsage
import app.schemas as schema

def find_or_create_user(user_info, oauth_source='github'):
    """
    This method populates db when user sign up or login through external auth system
    :param user_info: User data from external auth system
    :param oauth_source: From which oauth source the user coming from e.g. github
    :return: User data from Database
    """
    user = User.query.filter_by(name=user_info['login']).one_or_none()
    if user is None:
        user = User()
        user.email = user_info.get('email', None)
        user.secret = os.urandom(24).encode('hex')
        user.name = user_info['login']
        user.full_name = user_info.get('name', None)
        user.oauth_source = oauth_source

        publisher = Publisher(name=user.name)
        association = PublisherUser(role=UserRoleEnum.owner)
        association.publisher = publisher
        user.publishers.append(association)

        db.session.add(user)
        db.session.commit()
    return user


def get_user_by_id(user_id):
    '''
    Returns user info by given id from DB
    '''
    user = User.query.filter_by(id=user_id).first()
    if not user:
        raise InvalidUsage("User not found", 404)
    user_schema = schema.UserSchema()
    user_info = user_schema.dump(user)

    return user_info.data


def get_publisher(publisher):
    '''
    Returns publisher info from DB
    '''

    publisher_info = Publisher.query.filter_by(name=publisher).first()
    if publisher_info is None:
        raise InvalidUsage("Publisher not found", 404)
    publisher_schema = schema.PublisherSchema()
    info = publisher_schema.dump(publisher_info)

    return info.data


def create_or_update_package_tag(publisher_name, package_name, tag):
    package = Package.query.join(Publisher)\
        .filter(Publisher.name == publisher_name,
                Package.name == package_name).one()

    data_latest = PackageTag.query.join(Package)\
        .filter(Package.id == package.id,
                PackageTag.tag == 'latest').one()

    tag_instance = PackageTag.query.join(Package) \
        .filter(Package.id == package.id,
                PackageTag.tag == tag).first()

    update_props = ['descriptor', 'readme', 'package_id']
    if tag_instance is None:
        tag_instance = PackageTag()

    for update_prop in update_props:
        setattr(tag_instance, update_prop, getattr(data_latest, update_prop))
    tag_instance.tag = tag

    db.session.add(tag_instance)
    db.session.commit()
    return True


def create_or_update_package(name, publisher_name, **kwargs):
    """
    This method creates data package or updates data package attributes
    :param name: package name
    :param publisher_name: publisher name
    :param kwargs: package attribute names
    """
    pub_id = Publisher.query.filter_by(name=publisher_name).one().id
    instance = Package.query.join(Publisher)\
        .filter(Package.name == name,
                Publisher.name == publisher_name).first()

    if not instance:
        instance = Package(name=name)
        instance.publisher_id = pub_id
        tag_instance = PackageTag()
        instance.tags.append(tag_instance)
    else:
        tag_instance = PackageTag.query.join(Package) \
            .filter(Package.id == instance.id,
                    PackageTag.tag == 'latest').one()
    for key, value in kwargs.items():
        if key not in ['descriptor', 'readme']:
            setattr(instance, key, value)
        else:
            setattr(tag_instance, key, value)
    db.session.add(instance)
    db.session.commit()


def change_package_status(publisher_name, package_name, status=PackageStateEnum.active):
    """
    This method changes status of the data package. This method used
    for soft delete the data package
    :param publisher_name: publisher name
    :param package_name: package name
    :param status: status of the package
    :return: If success True else False
    """
    data = Package.query.join(Publisher). \
        filter(Publisher.name == publisher_name,
               Package.name == package_name).one()
    data.status = status
    db.session.add(data)
    db.session.commit()
    return True


def delete_data_package(publisher_name, package_name):
    """
    This method deletes the data package. This method used
    for hard delete the data package
    :param publisher_name: publisher name
    :param package_name: package name
    :return: If success True else False
    """
    data = Package.query.join(Publisher). \
        filter(Publisher.name == publisher_name,
               Package.name == package_name).one()
    package_id = data.id
    Package.query.filter(Package.id == package_id).delete()
    db.session.commit()
    return True


def get_package(publisher_name, package_name):
    """
    This method returns certain data package belonging to a publisher
    :param publisher_name: publisher name
    :param package_name: package name
    :return: data package object based on the filter.
    """
    instance = Package.query.join(Publisher) \
        .filter(Package.name == package_name,
                Publisher.name == publisher_name).one_or_none()
    return instance


def package_exists(publisher_name, package_name):
    """
    This method will check package with the name already exists or not
    :param publisher_name: publisher name
    :param package_name: package name
    :return: True is data already exists else false
    """
    instance = Package.query.join(Publisher)\
        .filter(Package.name == package_name,
                Publisher.name == publisher_name).all()
    return len(instance) > 0


def get_metadata_for_package(publisher, package):
    '''
    Returns metadata for given package owned by publisher
    '''
    data = Package.query.join(Publisher).\
        filter(Publisher.name == publisher,
               Package.name == package,
               Package.status == PackageStateEnum.active).\
        first()
    if not data:
        return None

    metadata_schema = schema.PackageMetadataSchema()
    metadata = metadata_schema.dump(data).data

    return metadata


def get_package_names_for_publisher(publisher):
    metadata = Package.query.join(Publisher).\
        with_entities(Package.name).\
        filter(Publisher.name == publisher).all()
    if len(metadata) is 0:
        raise InvalidUsage('No Data Package Found For The Publisher', 404)
    keys = []
    for d in metadata:
        keys.append(d[0])
    return keys
