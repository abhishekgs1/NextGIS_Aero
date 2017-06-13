# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import sys
import json
import traceback
from collections import OrderedDict

from pyramid.response import Response

from ..env import env
from ..models import DBSession
from ..auth import User
from ..pyramid import viewargs

from .model import Resource
from .scope import ResourceScope
from .exception import ResourceError, ValidationError, ForbiddenError
from .serialize import CompositeSerializer
from .view import resource_factory
from .util import _


PERM_READ = ResourceScope.read
PERM_DELETE = ResourceScope.delete
PERM_MCHILDREN = ResourceScope.manage_children
PERM_CPERM = ResourceScope.change_permissions


@viewargs(renderer='json')
def child_get(request):
    # TODO: Security

    child_id = request.matchdict['child_id']
    child_id = None if child_id == '' else child_id

    query = Resource.query().with_polymorphic('*').filter_by(
        parent_id=request.context.id if request.context else None)

    if child_id is not None:
        query = query.filter_by(id=child_id)

    result = []

    for child in query:
        serializer = CompositeSerializer(child, request.user)
        serializer.serialize()

        if child_id is not None:
            return serializer.data
        else:
            result.append(serializer.data)

    return result


def child_put(request):
    child_id = request.matchdict['child_id']
    assert child_id != ''

    data = request.json_body

    child = Resource.query().with_polymorphic('*') \
        .filter_by(id=child_id).one()

    serializer = CompositeSerializer(child, request.user, data)

    with DBSession.no_autoflush:
        result = serializer.deserialize()

    DBSession.flush()
    return Response(
        json.dumps(result), status_code=200,
        content_type=b'application/json')


def child_post(request):
    child_id = request.matchdict['child_id']
    assert child_id == ''

    data = request.json_body

    data['resource']['parent'] = dict(id=request.context.id)

    cls = Resource.registry[data['resource']['cls']]
    child = cls(owner_user=request.user)

    deserializer = CompositeSerializer(child, request.user, data)
    deserializer.members['resource'].mark('cls')

    with DBSession.no_autoflush:
        deserializer.deserialize()

    child.persist()
    DBSession.flush()

    location = request.route_url(
        'resource.child',
        id=child.parent_id,
        child_id=child.id)

    data = OrderedDict(id=child.id)
    data['parent'] = dict(id=child.parent_id)

    return Response(
        json.dumps(data), status_code=201,
        content_type=b'application/json', headerlist=[
            (b"Location", bytes(location)), ])


def child_delete(request):
    child_id = request.matchdict['child_id']
    assert child_id != ''

    child = Resource.query().with_polymorphic('*') \
        .filter_by(id=child_id).one()

    def delete(obj):
        request.resource_permission(PERM_MCHILDREN, obj)
        for chld in obj.children:
            delete(chld)

        request.resource_permission(PERM_DELETE, obj)
        DBSession.delete(obj)

    with DBSession.no_autoflush:
        delete(child)

    DBSession.flush()

    return Response(
        json.dumps(None), status_code=200,
        content_type=b'application/json')


def exception_to_response(request, exc_type, exc_value, exc_traceback):
    data = dict(exception=exc_value.__class__.__name__)

    # Select more appropriate HTTP-codes, thought we don't really need it
    # right now - we could've used just one.

    scode = 500

    if isinstance(exc_value, ValidationError):
        scode = 400

    if isinstance(exc_value, ForbiddenError):
        scode = 403

    # General attributes to identify where the error has happened,
    # installed in CompositeSerializer and Serializer.

    if hasattr(exc_value, '__srlzr_cls__'):
        data['serializer'] = exc_value.__srlzr_cls__.identity

    if hasattr(exc_value, '__srlzr_prprt__'):
        data['attr'] = exc_value.__srlzr_prprt__

    if isinstance(exc_value, ResourceError):
        # For ResourceError children it is possible to send message to user
        # as is, for other cases it might not be secure as it can contain
        # SQL or some sensitive data.

        data['message'] = request.localizer.translate(exc_value.message)

    else:
        # For all others let's generate universal error message based
        # on class name of the exception.

        if 'serializer' in data and 'attr' in data:
            message = _("Unknown exception '%(exception)s' in serializer '%(serializer)s' attribute '%(attr)s'.")
        elif 'attr' in data:
            message = _("Unknown exception '%(exception)s' in serializer '%(serializer)s'.")
        else:
            message = _("Unknown exception '%(exception)s'.")

        data['message'] = request.localizer.translate(message % data)

        # Unexpected error, makes sense to write it down.

        env.resource.logger.error(
            exc_type.__name__ + ': ' + unicode(exc_value.message) + "\n"
            + ''.join(traceback.format_tb(exc_traceback)))

    return Response(
        json.dumps(data), status_code=scode,
        content_type=b'application/json')


def resexc_tween_factory(handler, registry):
    """ Tween factory для перехвата исключительных ситуаций API ресурса

    Exception can happen both during flush and commit. We can run flush explicitly,
    but commit is ran hidden through pyramid_tm. To track those 
    situations pyramid tween is used, that is registered on top of pyramid_tm (see setup_pyramid).

    After error intercept generate its JSON representation
    using exception_to_response. """

    def resource_exception_tween(request):
        try:
            response = handler(request)
        except:
            mroute = request.matched_route
            if mroute and mroute.name in (
                'resource.child',
                'resource.item',
                'resource.collection'
            ):
                return exception_to_response(request, *sys.exc_info())
            raise
        return response

    return resource_exception_tween


def item_get(context, request):
    request.resource_permission(PERM_READ)

    serializer = CompositeSerializer(context, request.user)
    serializer.serialize()

    return Response(
        json.dumps(serializer.data), status_code=200,
        content_type=b'application/json')


def item_put(context, request):
    request.resource_permission(PERM_READ)

    serializer = CompositeSerializer(context, request.user, request.json_body)
    with DBSession.no_autoflush:
        result = serializer.deserialize()

    return Response(
        json.dumps(result), status_code=200,
        content_type=b'application/json')


def item_delete(context, request):

    def delete(obj):
        request.resource_permission(PERM_DELETE, obj)
        request.resource_permission(PERM_MCHILDREN, obj)

        for chld in obj.children:
            delete(chld)

        DBSession.delete(obj)

    if context.id == 0:
        raise ResourceError(_("Root resource could not be deleted."))

    with DBSession.no_autoflush:
        delete(context)

    DBSession.flush()

    return Response(
        json.dumps(None), status_code=200,
        content_type=b'application/json')


def collection_get(request):
    parent = request.params.get('parent')
    parent = int(parent) if parent else None

    query = Resource.query().with_polymorphic('*') \
        .filter_by(parent_id=parent)

    result = list()
    for resource in query:
        if resource.has_permission(PERM_READ, request.user):
            serializer = CompositeSerializer(resource, request.user)
            serializer.serialize()
            result.append(serializer.data)

    return Response(
        json.dumps(result), status_code=200,
        content_type=b'application/json')


def collection_post(request):
    data = dict(request.json_body)

    if 'resource' not in data:
        data['resource'] = dict()

    qparent = request.params.get('parent')
    if qparent is not None:
        data['resource']['parent'] = dict(id=int(qparent))

    cls = request.params.get('cls')
    if cls is not None:
        data['resource']['cls'] = cls

    if 'parent' not in data['resource']:
        raise ValidationError(_("Resource parent required."))

    if 'cls' not in data['resource']:
        raise ValidationError(_("Resource class required."))

    elif data['resource']['cls'] not in Resource.registry:
        raise ValidationError(_("Unknown resource class '%s'.") % data['resource']['cls'])

    cls = Resource.registry[data['resource']['cls']]
    resource = cls(owner_user=request.user)

    serializer = CompositeSerializer(resource, request.user, data)
    serializer.members['resource'].mark('cls')

    with DBSession.no_autoflush:
        serializer.deserialize()

    resource.persist()
    DBSession.flush()

    result = OrderedDict(id=resource.id)

    # TODO: Parent is returned only for compatibility
    result['parent'] = dict(id=resource.parent.id)

    return Response(
        json.dumps(result), status_code=201,
        content_type=b'application/json')


def permission(resource, request):
    request.resource_permission(PERM_READ)

    # In some cases it is convenient to pass empty string instead of 
    # user's identifier, that's why it so tangled.

    user = request.params.get('user', '')
    user = None if user == '' else user

    if user is not None:
        # To see permissions for arbitrary user additional permissions are needed
        request.resource_permission(PERM_CPERM)
        user = User.filter_by(id=user).one()

    else:
        # If it is not set otherwise, use current user
        user = request.user

    effective = resource.permissions(user)

    result = OrderedDict()
    for k, scope in resource.scope.iteritems():
        sres = OrderedDict()

        for perm in scope.itervalues(ordered=True):
            sres[perm.name] = perm in effective

        result[k] = sres

    return Response(
        json.dumps(result), status_code=200,
        content_type=b'application/json')


def setup_pyramid(comp, config):

    def _route(route_name, route_path, **kwargs):
        return config.add_route(
            'resource.' + route_name,
            '/resource/' + route_path,
            **kwargs)

    def _resource_route(route_name, route_path, **kwargs):
        return _route(
            route_name, route_path,
            factory=resource_factory,
            **kwargs)

    _resource_route('child', '{id:\d+|-}/child/{child_id:\d*}',
                    client=('id', 'child_id')) \
        .add_view(child_get, method=r'GET') \
        .add_view(child_put, method=(r'PUT', r'PATCH')) \
        .add_view(child_post, method=r'POST') \
        .add_view(child_delete, method=r'DELETE')

    config.add_route(
        'resource.item', '/api/resource/{id:\d+}',
        factory=resource_factory) \
        .add_view(item_get, request_method='GET') \
        .add_view(item_put, request_method='PUT') \
        .add_view(item_delete, request_method='DELETE')

    config.add_route(
        'resource.collection', '/api/resource/') \
        .add_view(collection_get, request_method='GET') \
        .add_view(collection_post, request_method='POST')

    config.add_route(
        'resource.permission', '/api/resource/{id}/permission',
        factory=resource_factory) \
        .add_view(permission, request_method='GET')

    config.add_tween(
        'nextgisweb.resource.api.resexc_tween_factory',
        over='pyramid_tm.tm_tween_factory')
