# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from flask import Blueprint, request, jsonify
from flask import current_app as app
from app.logic.search import DataPackageQuery

search_blueprint = Blueprint('search', __name__, url_prefix='/api/search')


@search_blueprint.route("/package", methods=["GET"])
def search_packages():
    """
        Data Package Search
        ---
        tags:
            - search
        parameters:
            - in: query
              name: q
              type: string
              required: true
              description: search query string e.g. q=query publisher=pub
        responses:
            500:
                description: Internal Server Error
            200:
                description: Success Message
                schema:
                    id: search_package_success
                    properties:
                        total_count:
                            type: integer
                            description: Total datapackage count
                        items:
                            type: list
                            properties:
                                type: object
        """
    q = request.args.get('q')
    if q is None:
        q = ''
    limit = request.args.get('limit')

    result = DataPackageQuery(query_string=q.strip(),
                              limit=limit).get_data()
    return jsonify(dict(items=result, total_count=len(result)))
