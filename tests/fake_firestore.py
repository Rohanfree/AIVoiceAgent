"""Minimal in-memory Firestore fake (collections, documents, equality queries) for tests."""
from google.cloud.firestore import FieldFilter  # noqa: F401  (imported for parity with app code)


class FakeSnap:
    def __init__(self, ref, data):
        self.reference = ref
        self.id = ref.name
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class FakeRef:
    def __init__(self, db, coll, name):
        self.db, self.coll, self.name = db, coll, name

    @property
    def _store(self):
        return self.db.data.setdefault(self.coll, {})

    def get(self, transaction=None):
        return FakeSnap(self, self._store.get(self.name))

    def set(self, data):
        self._store[self.name] = dict(data)

    def update(self, data):
        self._store[self.name].update(data)

    def delete(self):
        self._store.pop(self.name, None)


class FakeQuery:
    def __init__(self, db, coll, filters, limit_count=None):
        self.db, self.coll, self.filters = db, coll, filters
        self.limit_count = limit_count

    def where(self, filter):
        return FakeQuery(self.db, self.coll, self.filters + [(filter.field_path, filter.value)], self.limit_count)

    def limit(self, count):
        return FakeQuery(self.db, self.coll, self.filters, count)

    def stream(self):
        store = self.db.data.get(self.coll, {})
        docs = [
            FakeSnap(FakeRef(self.db, self.coll, n), d)
            for n, d in list(store.items())
            if all(d.get(f) == v for f, v in self.filters)
        ]
        return docs if self.limit_count is None else docs[:self.limit_count]


class FakeCollection(FakeQuery):
    def __init__(self, db, coll):
        super().__init__(db, coll, [])

    def document(self, name):
        return FakeRef(self.db, self.coll, name)


class FakeDB:
    def __init__(self):
        self.data = {}

    def collection(self, name):
        return FakeCollection(self, name)
