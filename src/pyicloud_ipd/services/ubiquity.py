from datetime import datetime
import sys


class UbiquityService(object):
    """ The 'Ubiquity' iCloud service."""

    def __init__(self, service_root, session, params):
        self.session = session
        self.params = params
        self._root = None

        self._service_root = service_root
        self._node_url = '/ws/%s/%s/%s'

    def get_node_url(self, id, variant='item'):
        return self._service_root + self._node_url % (
            self.params['dsid'],
            variant,
            id
        )

    def get_node(self, id):
        request = self.session.get(self.get_node_url(id))
        return UbiquityNode(self, request.json())

    def get_children(self, id):
        request = self.session.get(
            self.get_node_url(id, 'parent')
        )
        items = request.json()['item_list']
        return [UbiquityNode(self, item) for item in items]

    def get_file(self, id, **kwargs):
        request = self.session.get(
            self.get_node_url(id, 'file'),
            **kwargs
        )
        return request

    @property
    def root(self):
        if not self._root:
            self._root = self.get_node(0)
        return self._root

    def __getattr__(self, attr):
        return getattr(self.root, attr)

    def __getitem__(self, key):
        return self.root[key]


class UbiquityNode(object):
    def __init__(self, conn, data):
        self.data = data
        self.connection = conn

    @property
    def item_id(self):
        return self.data.get('item_id')

    @property
    def name(self):
        return self.data.get('name')

    @property
    def type(self):
        return self.data.get('type')

    def get_children(self):
        if not hasattr(self, '_children'):
            self._children = self.connection.get_children(self.item_id)
        return self._children

    @property
    def size(self):
        try:
            return int(self.data.get('size'))
        except ValueError:
            return None

    @property
    def modified(self):
        return datetime.strptime(
            self.data.get('modified'),
            '%Y-%m-%dT%H:%M:%SZ'
        )

    def dir(self):
        return [child.name for child in self.get_children()]

    def open(self, **kwargs):
        return self.connection.get_file(self.item_id, **kwargs)

    def get(self, name):
        return [
            child for child in self.get_children() if child.name == name
        ][0]

    def __getitem__(self, key):
        try:
            return self.get(key)
        except IndexError:
            raise KeyError('No child named %s exists' % key)

    def __unicode__(self):
        return self.name

    def __str__(self):
        as_unicode = self.__unicode__()
        if sys.version_info[0] >= 3:
            return as_unicode
        else:
            return as_unicode.encode('ascii', 'ignore')

    def __repr__(self):
        return "<%s: '%s'>" % (
            self.type.capitalize(),
            self
        )
