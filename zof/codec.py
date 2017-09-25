import os
import codecs
from ctypes import cdll, c_void_p, c_size_t, c_uint32, create_string_buffer
from zof.connection import Connection
from zof.objectview import to_json, ObjectView
from zof.exception import CodecError

OFTR_DLL = None

OFTR_ENCODE = 1
OFTR_DECODE = 2


def _dll():
    global OFTR_DLL  # pylint: disable=global-statement
    if OFTR_DLL is not None:
        return OFTR_DLL

    executable = Connection.find_oftr_path(os.getenv('ZOF_OFTR_PATH'))
    if not executable or executable[0] != '/':
        raise RuntimeError('Unable to locate oftr executable')

    OFTR_DLL = cdll.LoadLibrary(executable)
    OFTR_DLL.oftr_call.argtypes = [
        c_uint32, c_void_p, c_size_t, c_void_p, c_size_t
    ]
    return OFTR_DLL


def _oftr_call(opcode, data, buflen=2048):
    assert isinstance(data, bytes)

    dll = _dll()
    buf = create_string_buffer(buflen)

    result = dll.oftr_call(opcode, data, len(data), buf, buflen)
    if result < -buflen:
        # Result buffer is not big enough.
        buflen = -result
        buf = create_string_buffer(buflen)
        result = dll.oftr_call(opcode, data, len(data), buf, buflen)

    if result >= 0:
        # Buffer contains result.
        return buf[:result]

    if result >= -buflen:
        # Buffer contains error message.
        raise CodecError(buf[:-result].decode('utf-8'))

    # Result buffer is not big enough; this shouldn't happen.
    raise CodecError('_oftr_call failed: %r bytes needed' % result)


def encode(text, version=4):
    """Encode source code as binary.
    """

    if isinstance(text, (dict, ObjectView)):
        text = to_json(text)

    opcode = OFTR_ENCODE + (version << 24)
    return _oftr_call(
        opcode, text.encode('utf-8'), buflen=max(len(text), 1024))


def decode(binary):
    """Decode binary as source code.
    """

    return _oftr_call(OFTR_DECODE, bytes(binary), buflen=1024).decode('utf-8')


#-------------------------------------------------------------------------------


def _of_encode(text, errors='strict'):
    if errors != 'strict':
        raise CodecError('invalid errors argument: %s' % errors)
    return encode(text), len(text)


def _of_decode(binary, errors='strict'):
    if errors != 'strict':
        raise CodecError('invalid errors argument: %s' % errors)
    return decode(binary), len(binary)


def search(name):
    """Search function registered for codecs.

    Args:
        name (str): Codec name.

    Returns:
        CodecInfo: Encode/decode information or None if not found.
    """
    if name == 'openflow':
        return codecs.CodecInfo(
            name=name, encode=_of_encode, decode=_of_decode)
    return None


codecs.register(search)
