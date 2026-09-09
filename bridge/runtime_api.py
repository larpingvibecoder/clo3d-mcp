"""Live CLO reflection and structured invocation. Runs only on CLO's UI thread."""
import importlib
import inspect
import uuid

MODULES = ('import_api', 'export_api', 'fabric_api', 'pattern_api', 'utility_api', 'rest_api', 'ApiTypes')
_HANDLES = {}


def resolve(path):
    parts = path.split('.')
    if parts[0] not in MODULES or any(not p.isidentifier() or p.startswith('_') for p in parts):
        raise ValueError('Use a public, module-qualified CLO API name')
    value = importlib.import_module(parts[0])
    for part in parts[1:]:
        value = getattr(value, part)
    return value


def catalog(query='', module='', offset=0, limit=100):
    if module and module not in MODULES:
        raise ValueError('Unknown module: ' + module)
    if offset < 0 or not 1 <= limit <= 500:
        raise ValueError('offset >= 0 and limit 1..500 required')
    entries, errors = [], {}
    words = query.lower().split()
    for mod in ([module] if module else MODULES):
        try:
            obj = importlib.import_module(mod)
        except ImportError as exc:
            errors[mod] = str(exc)
            continue
        for name in sorted(dir(obj)):
            if name.startswith('_'):
                continue
            value = getattr(obj, name)
            doc = inspect.getdoc(value) or ''
            qualified = mod + '.' + name
            if not all(w in (qualified + ' ' + doc).lower() for w in words):
                continue
            try:
                signature = str(inspect.signature(value)) if callable(value) else None
            except (TypeError, ValueError):
                signature = None
            entries.append(dict(name=qualified, kind='type' if inspect.isclass(value) else 'function' if callable(value) else 'constant', signature=signature, summary=doc.split('\n')[0][:400]))
    return dict(total=len(entries), entries=entries[offset:offset+limit], next_offset=offset+limit if offset+limit < len(entries) else None, unavailable_modules=errors)


def describe(name):
    value = resolve(name)
    members = []
    if inspect.isclass(value):
        members = [dict(name=n, doc=inspect.getdoc(getattr(value, n)) or '') for n in dir(value) if not n.startswith('_')]
    return dict(name=name, doc=inspect.getdoc(value) or '', members=members)


def decode(value):
    if isinstance(value, list):
        return [decode(v) for v in value]
    if not isinstance(value, dict):
        return value
    if '$handle' in value:
        if set(value) != {'$handle'}:
            raise ValueError('Handle must be the only key')
        return _HANDLES[value['$handle']]
    if '$enum' in value:
        if set(value) != {'$enum'}:
            raise ValueError('Enum must be the only key')
        return resolve(value['$enum'])
    if '$type' in value:
        if set(value) - {'$type', 'args', 'fields'}:
            raise ValueError('Unknown typed object keys')
        constructor = resolve(value['$type'])
        if not inspect.isclass(constructor):
            raise ValueError('$type must name a CLO class')
        obj = constructor(*decode(value.get('args', [])))
        for key, val in value.get('fields', {}).items():
            if key.startswith('_') or not hasattr(obj, key) or callable(getattr(obj, key)):
                raise ValueError('Unknown or non-data field: ' + key)
            setattr(obj, key, decode(val))
        return obj
    return {k: decode(v) for k, v in value.items()}


def encode(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [encode(v) for v in value]
    if isinstance(value, dict):
        return {str(k): encode(v) for k, v in value.items()}
    if len(_HANDLES) >= 1000:
        raise RuntimeError('Handle storage full; release handles before another call. The call already ran.')
    key = uuid.uuid4().hex
    _HANDLES[key] = value
    return {'$handle': key, 'type': type(value).__name__, 'repr': repr(value)}


def invoke(name, args=None, kwargs=None):
    fn = resolve(name)
    if not callable(fn):
        return encode(fn)
    return encode(fn(*decode(args or []), **decode(kwargs or {})))


def release(handles):
    return {'released': sum(_HANDLES.pop(key, None) is not None for key in handles)}
