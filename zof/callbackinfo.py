import inspect


class CallbackInfo:
    """Concrete class encapsulating information about a callback function.

    This class supports callbacks that may be registered by a decorator. The
    callback can be normal function or a method that is bound to an object 
    later. A callback may be an asyncio coroutine function; the client is
    responsible for calling it correctly.

    Example:

        class Foo:
            def cb(self, arg):
                ...

        info = CallbackInfo(Foo.cb)
        assert info.arg_count == 1

        func = info.bind(Foo())
        func(1)
    """

    def __init__(self, callback):
        """Inspect callback function."""
        # Track type of original callback.
        func = callback
        orig_type = type(func).__name__
        assert orig_type in {'method', 'function', 'staticmethod', 'classmethod'}

        # Dereference staticmethod and classmethod wrappers. These appear when
        # invoked inside a decorator.
        if isinstance(func, (staticmethod, classmethod)):
            func = func.__func__

        # Obtain function's signature and qualified name.
        assert callable(func)
        sig = inspect.signature(func)
        qualname = func.__qualname__

        # A method will have a __self__ attribute that can tell us the class
        # name. For other types, parse the end of the qualified name.
        class_ = None
        if orig_type == 'method':
            cls = func.__self__.__class__
            if cls is type:  # class method
                class_ = func.__self__.__name__
            else:
                class_ = cls.__name__
        elif '.' in qualname:
            lhs, _ = qualname.split('.')[-2:]
            if lhs != '<locals>':
                class_ = lhs

        # Obtain list of parameters and check if instance is required.
        params = list(sig.parameters.values())
        instance_required = _instance_required(orig_type, class_, params)
        class_required = _class_required(orig_type, class_, params)

        # Count the number of required positional arguments.
        args_required = _args_required(params)
        if instance_required or class_required:
            args_required -= 1

        # If staticmethod passed in, dereference it here.
        if orig_type == 'staticmethod':
            callback = func

        self.name = '%s%s' % (qualname, sig)
        self.callback = callback
        self.class_ = class_
        self.args_required = args_required
        self.instance_required = instance_required
        self.class_required = class_required

    def bind(self, instance=None):
        """Return callback bound to instance."""
        callback = self.callback
        # Handle class binding and instance binding.
        if self.class_required or self.instance_required:
            if instance is None:
                raise ValueError('Callback %s requires an instance of class %s' % (self.name, self.class_))
            cls = instance.__class__
            if cls.__name__ != self.class_:
                raise ValueError('Callback %s requires an instance of class %s (not %s)' % (self.name, self.class_, cls.__name__))
            return callback.__get__(instance, cls)
        return callback

    @property
    def bind_required(self):
        """Return true if callback must be bound to an instance."""
        return self.class_required or self.instance_required


def _args_required(params):
    """Return count of positional arguments needed."""
    return len([param for param in params if param.default == inspect.Parameter.empty])


def _instance_required(type_, class_, params):
    """Return true if method requires `self` instance."""
    if not params or class_ is None or type_ != 'function':
        return False
    # Check that the first parameter is named "self" to distinguish an
    # unbound method from a dereferenced staticmethod.
    return params[0].name == 'self' and params[0].default == inspect.Parameter.empty


def _class_required(type_, class_, params):
    """Return true if method requires a `cls` instance."""
    if not params or class_ is None:
        return False
    return type_ == 'classmethod'
