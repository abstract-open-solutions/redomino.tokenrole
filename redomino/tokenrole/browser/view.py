import base64
from AccessControl.unauthorized import Unauthorized
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.permissions import View
from Products.CMFPlone.PloneBatch import Batch
from Products.Five.browser import BrowserView
from Products.ZCatalog.Lazy import LazyCat
from zope.security import checkPermission
from zope.component import getMultiAdapter
from redomino.tokenrole.interfaces import ITokenRolesAnnotate


class PrivateTokenListingView(BrowserView):

    @property
    def canView(self):
        return checkPermission('zope2.View', self.context)

    def split_cookie(self):
        request = self.context.REQUEST

        token = request.get('token', '')
        if not token:
            token = request.cookies.get('token', '')

        value = token.split('|')
        if len(value) == 2:
            return value
        return value[0], ''

    def __call__(self):
        request = self.context.REQUEST
        token, path = self.split_cookie()

        tr_annotate = ITokenRolesAnnotate(self.context, None)
        if tr_annotate and (not tr_annotate.token_dict.has_key(token)):
            if path:
                path = base64.b64decode(path)
                portal_state = getMultiAdapter(
                    (self.context, request), name=u'plone_portal_state')
                navigation_root = portal_state.navigation_root()
                parent = navigation_root.unrestrictedTraverse(path.replace(
                    '/'.join(navigation_root.getPhysicalPath()), '')[1:])
                tr_annotate = ITokenRolesAnnotate(parent, None)

        if self.canView or (tr_annotate and tr_annotate.token_dict.has_key(token)):
            return self.index()
        raise Unauthorized(self.__name__)

    @property
    def macros(self):
        return self.index.macros

    @property
    def members(self):
        return getToolByName(self.context, name="portal_membership")

    @property
    def catalog(self):
        return getToolByName(self.context, name="portal_catalog")

    def privateQueryCatalog(self, REQUEST=None, batch=False, b_size=None,
                            full_objects=False, **kw):
        if REQUEST is None:
            REQUEST = self.context.REQUEST
        b_start = REQUEST.get('b_start', 0)
        related = [i for i in self.context.getRelatedItems()
                   if self.members.checkPermission(View, i)]

        if not full_objects:
            uids = [r.UID() for r in related]
            query = dict(UID=uids)
            related = self.catalog(query)
        related = LazyCat([related])

        limit = self.context.getLimitNumber()
        max_items = self.context.getItemCount()
        # Batch based on limit size if b_size is unspecified
        if max_items and b_size is None:
            b_size = int(max_items)
        else:
            b_size = b_size or 20

        q = self.context.buildQuery()
        if q is None:
            results = LazyCat([[]])
        else:
            # Allow parameters to further limit existing criterias
            q.update(kw)
            if not batch and limit and max_items and \
               self.context.hasSortCriterion():
                q.setdefault('sort_limit', max_items)
            if batch:
                q['b_start'] = b_start
                q['b_size'] = b_size
            __traceback_info__ = (self.context, q)
            results = self.catalog.unrestrictedSearchResults(q)

        if limit and not batch:
            if full_objects:
                return related[:max_items] + [
                    b._unrestrictedGetObject()
                    for b in results[:max_items-len(related)]
                ]
            return related[:max_items] + results[:max_items-len(related)]
        elif full_objects:
            results = related + LazyCat([
                [b._unrestrictedGetObject() for b in results]
            ])
        else:
            results = related + results
        if batch:
            batch = Batch(results, b_size, int(b_start), orphan=0)
            return batch
        return results

    def private_listing(self, contentFilter=None,
                        batch=False, b_size=100, full_objects=False):
        contentFilter = self.request.get('contentFilter', contentFilter)
        batch = self.request.get('batch', batch)
        b_size = self.request.get('batch', b_size)
        full_objects = self.request.get('full_objects', full_objects)
        b_start = self.context.REQUEST.get('b_start', 0)

        cur_path = '/'.join(self.context.getPhysicalPath())
        path = {}

        if not contentFilter:
            contentFilter = {}
        else:
            contentFilter = dict(contentFilter)

        if not contentFilter.get('sort_on', None):
            contentFilter['sort_on'] = 'getObjPositionInParent'

        if contentFilter.get('path', None) is None:
            path['query'] = cur_path
            path['depth'] = 1
            contentFilter['path'] = path

        show_inactive = self.members.checkPermission(
            'Access inactive portal content', self.context)

        # Provide batching hints to the catalog
        b_start = int(b_start)
        contentFilter['b_start'] = b_start
        if batch:
            contentFilter['b_size'] = b_size

        contents = self.catalog.unrestrictedSearchResults(
            contentFilter, show_all=1, show_inactive=show_inactive, )

        if full_objects:
            contents = [b._unrestrictedGetObject() for b in contents]

        if batch:
            from Products.CMFPlone import Batch
            batch = Batch(contents, b_size, b_start, orphan=0)
            return batch

        return contents
