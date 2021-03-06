# -*- coding: utf-8 -*-
# Copyright (c) 2011 Redomino srl (http://redomino.com)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.
import base64
from datetime import datetime
from persistent.dict import PersistentDict

from zope.interface import implements
from zope.component import adapts
from zope.annotation.interfaces import IAnnotations

from borg.localrole.interfaces import ILocalRoleProvider

from Products.ATContentTypes.utils import dt2DT

from redomino.tokenrole.interfaces import ITokenRolesAnnotate
from redomino.tokenrole.interfaces import ITokenInfoSchema
from redomino.tokenrole.interfaces import ITokenRolesProviding
from zope.component import getMultiAdapter

ANNOTATIONS_KEY = 'redomino.tokenrole.tokenrole_annotations'

class TokenRolesAnnotateAdapter(object):
    implements(ITokenRolesAnnotate)

    def __init__(self, context):
        self.annotations = IAnnotations(context).setdefault(ANNOTATIONS_KEY,
                                                           PersistentDict())

    @apply
    def token_dict():
        def get(self):
            return self.annotations.get('token_dict', {})
        def set(self, value):
            self.annotations['token_dict'] = value
        return property(get, set)


class TokenInfoSchema(object):
    implements(ITokenInfoSchema)
    adapts(ITokenRolesProviding)

    def __init__(self, context):
        self.context = context
        self.annotation = ITokenRolesAnnotate(self.context)

    def setter(self, name, value):
        if not self.annotation.token_dict:
            self.annotation.token_dict = PersistentDict()
        token_id = self.annotation.token_dict.setdefault(self.token_id, PersistentDict())
        token_id[name] = value

    @apply
    def token_id():
        def getter(self):
            return self.context.REQUEST.get('form.widgets.token_id')
        def setter(self, value):
            pass
        return property(getter, setter)

    @apply
    def token_end():
        def getter(self):
            return self.annotation.token_dict.get(self.token_id, {}).get('token_end')
        def setter(self, value):
            self.setter('token_end', value)
        return property(getter, setter)

    @apply
    def token_roles():
        def getter(self):
            return self.annotation.token_dict.get(self.token_id, {}).get('token_roles')
        def setter(self, value):
            self.setter('token_roles', value)
        return property(getter, setter)


class TokenRolesLocalRolesProviderAdapter(object):
    implements(ILocalRoleProvider)

    def __init__(self, context):
        self.context = context

    def getRoles(self, principal_id):
        """Returns the roles for the given principal in context"""
        request = self.context.REQUEST
        response = request.RESPONSE
        parent = self.context

        token = request.get('token', None)
        if not token:
            token = request.cookies.get('token', None)

        if token and '|' in token:
            token = token.split('|')[0]

        tr_annotate = ITokenRolesAnnotate(self.context, None)
        if tr_annotate and (not tr_annotate.token_dict.has_key(token)):
            cookie = request.cookies.get('token', None)
            if cookie and '|' in cookie:
                path = base64.b64decode(cookie.split('|')[1])
                portal_state = getMultiAdapter((self.context, request),
                    name=u'plone_portal_state')
                navigation_root = portal_state.navigation_root()
                parent = navigation_root.unrestrictedTraverse(path.replace(
                    '/'.join(navigation_root.getPhysicalPath()), '')[1:])
                tr_annotate = ITokenRolesAnnotate(parent, None)

        if tr_annotate and tr_annotate.token_dict.has_key(token):
            expire_date = tr_annotate.token_dict[token].get('token_end')
            roles_to_assign = tr_annotate.token_dict[token].get('token_roles', ('Reader',))
            if expire_date.replace(tzinfo=None) > datetime.now():
                if not request.cookies.has_key('token'):
                    physical_path = parent.getPhysicalPath()
                    # Is there a better method for calculate the url_path?
                    url_path = '/' + '/'.join(request.physicalPathToVirtualPath(physical_path))
                    response.setCookie(name='token',
                                       value="{0}|{1}".format(
                                            token,
                                            base64.b64encode(url_path)
                                       ),
                                       expires=dt2DT(expire_date).toZone('GMT').rfc822(),
                                       path=url_path)
                return roles_to_assign
        return ()

    def getAllRoles(self):
        """Returns all the local roles assigned in this context:
        (principal_id, [role1, role2])"""
        return ()
