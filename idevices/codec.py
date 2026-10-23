#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""codec.py — Codificación de la configuración de los iDevices de eXeLearning 4.

El motor de juegos (QuExt y familia) guarda su JSON cifrado con una función
compartida que vive en `/dist/static/app/common/common.js` del app.asar de
eXeLearning 4. Cuerpo literal (leído del código fuente, 2026-07-30):

    encrypt: function (str = '') {
        const key = 146;
        return escape(str.split('').map(char =>
            String.fromCharCode(char.charCodeAt(0) ^ key)).join(''));
    },
    decrypt: function (str) {
        str = unescape(str);
        const key = 146;
        ... String.fromCharCode(key ^ str.charCodeAt(pos)) ...
    }

Es decir: XOR 146 (0x92) sobre el **code point** de cada carácter (NO sobre bytes)
y después `escape()` de JavaScript. Al ser una única función compartida, vale para
todos los iDevices que la invocan.

Excepciones conocidas del catálogo: `rubric` usa solo `escape()` sin XOR, y
`trivial` usa renombrado de claves + Base64 selectivo.

Verificado con round-trip byte-exacto contra .elpx reales (quick-questions, classify).
"""
import json
import random
import string
import time
import urllib.parse

# escape() de JavaScript deja sin codificar exactamente estos caracteres.
_JS_SEGUROS = set(string.ascii_letters + string.digits + '@*_+-./')

__all__ = ['js_escape', 'js_unescape', 'encrypt', 'decrypt',
           'dumps_cifrado', 'loads_cifrado', 'pc', 'nuevo_idevice_id',
           'nuevo_block_id']


def js_unescape(s):
    """Inverso de escape() de JavaScript."""
    out, i, n = [], 0, len(s)
    while i < n:
        if s[i] == '%' and i + 6 <= n and s[i + 1] in 'uU':
            out.append(chr(int(s[i + 2:i + 6], 16)))
            i += 6
        elif s[i] == '%' and i + 3 <= n:
            out.append(chr(int(s[i + 1:i + 3], 16)))
            i += 3
        else:
            out.append(s[i])
            i += 1
    return ''.join(out)


def js_escape(s):
    """escape() de JavaScript: <256 -> %XX · >=256 -> %uXXXX."""
    out = []
    for ch in s:
        o = ord(ch)
        if ch in _JS_SEGUROS:
            out.append(ch)
        elif o < 256:
            out.append('%%%02X' % o)
        else:
            out.append('%%u%04X' % o)
    return ''.join(out)


def decrypt(blob):
    """Blob del .elpx -> texto en claro."""
    return ''.join(chr(ord(c) ^ 0x92) for c in js_unescape(blob))


def encrypt(txt):
    """Texto en claro -> blob para el .elpx."""
    return js_escape(''.join(chr(ord(c) ^ 0x92) for c in txt))


def loads_cifrado(blob):
    """Blob -> objeto Python."""
    return json.loads(decrypt(blob))


def dumps_cifrado(obj):
    """Objeto Python -> blob, con round-trip comprobado."""
    txt = json.dumps(obj, ensure_ascii=False)
    blob = encrypt(txt)
    if decrypt(blob) != txt:
        raise ValueError('round-trip del codec no byte-exacto')
    return blob


def pc(txt):
    """Percent-encoding UTF-8, como usa Relaciona en sus campos eText."""
    return urllib.parse.quote(txt, safe='')


def _sufijo(n):
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(n))


def nuevo_idevice_id(pref='idevice'):
    """Identificador con la misma forma que los que genera eXe."""
    return '%s-%d-%s' % (pref, int(time.time() * 1000) + random.randint(0, 9999), _sufijo(9))


def nuevo_block_id():
    return 'block-%s-%s' % (_sufijo(8), _sufijo(9))
