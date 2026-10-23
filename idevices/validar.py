#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validar.py — Suite de comprobación de un .elpx sin abrir eXeLearning.

Estructura + VALORES. La lección del piloto (2026-07-30) es que una validación que
solo compara *claves* da luz verde a un iDevice roto: el fallo de Clasifica era que
las dos categorías se llamaban igual, y la clave `groups` existía y era del tipo
correcto. Por eso aquí hay un bloque de aserciones de valor.
"""
import json
import re
from collections import Counter
from html import unescape
from xml.etree import ElementTree as ET

from . import codec

from .catalogo import ficha
from .elpx_io import NS, Elpx

__all__ = ['validar']

# textos que delatan que se clonó un esqueleto y no se sustituyó la carga
SOSPECHOSOS = re.compile(r'^(Grupo \d|Categoría \d|Texto de ejemplo|Lorem ipsum|'
                         r'Escribe aquí|Pregunta \d|Respuesta \d)$', re.I)

# ---------------------------------------------------------------- maqueta
# Los iDevices con `maqueta` guardan su contenido visible DOS VECES: en la
# configuración y en el HTML del htmlView (eXe lo usa para pintar antes de que
# arranque el JS y para repoblar el formulario del editor). Nada obliga a que
# las dos copias coincidan, así que un parcheo que toque solo el JSON deja el
# texto viejo dentro del bundle y del HTML publicado. Pasó dos veces
# —2026-08-04 y 2026-08-05, MATE-002— y las dos el validador dio OK porque solo
# miraba la configuración.
#
# AQUÍ HABÍA ESCRITO que esa copia «va en display:none, no se ve, pero viaja».
# Es FALSO, y salió caro: MC-087 heredó la frase y se quedó 26 días en P2 por
# parecer cosmético. Medido el 2026-09-08 sobre el HTML publicado de
# CYR_3ESO_SDA_06_BIGDATA: el div de instrucciones se sirve VISIBLE, ninguna
# regla CSS lo oculta, y ni `classify.js` ni `scrambled-list.js` mencionan
# «instructions», así que el JS tampoco lo reescribe al arrancar. Lo que queda
# en la maqueta es exactamente lo que lee el alumnado. Si algún tipo sí oculta
# su copia, habrá que decirlo POR TIPO y con la medida delante.
#
# clave de la configuración -> (etiqueta, clase) donde vive su copia en la maqueta
MAQUETA = {
    'scrambled-list': {
        'instructions': ('div', 'exe-sortableList-instructions'),
        'buttonText':   ('p',   'exe-sortableList-buttonText'),
        'rightText':    ('p',   'exe-sortableList-rightText'),
        'wrongText':    ('p',   'exe-sortableList-wrongText'),
        'options':      ('ul',  'exe-sortableList-list'),
    },
    'trueorfalse': {
        'eXeGameInstructions': ('div', 'TOFP-instructions'),
    },
    'classify': {
        'instructions': ('div', 'clasifica-instructions'),
    },
}

# campos de realimentación que se contrastan entre iDevices (olor a copiar-pegar)
FEEDBACK = ('wrongText', 'rightText')
# por debajo de esto son rótulos genéricos («¡Correcto!», «Comprobar»): repetirlos
# no dice nada
OLOR_MIN = 25


def _plano(html):
    """Texto visible de un fragmento HTML, normalizado para comparar."""
    s = re.sub(r'<br\s*/?>', ' ', html or '')
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', unescape(s)).strip()


def _interior(html, tag, clase):
    """Contenido de `<tag class="…clase…">…</tag>`, respetando el anidamiento.

    Un regex no perezoso se come el resto del documento y uno perezoso corta en
    la primera etiqueta de cierre, que con `div` anidados es la equivocada.
    """
    m = re.search(r'<%s\b[^>]*\bclass="[^"]*\b%s\b[^"]*"[^>]*>' % (tag, re.escape(clase)),
                  html or '')
    if not m:
        return None
    ini = m.end()
    prof = 1
    for t in re.finditer(r'<(/?)%s\b[^>]*?(/?)>' % tag, html[ini:]):
        if t.group(2) == '/':          # <tag/> no abre nada
            continue
        prof += -1 if t.group(1) else 1
        if prof == 0:
            return html[ini:ini + t.start()]
    return None


def validar(ruta, verbose=True, estricto=False):
    """Devuelve (ok, incidencias). `incidencias` es lista de strings.

    Los AVISOS (olor a copiar-pegar, huecos de cobertura) se imprimen aparte y no
    tumban la validación, salvo con `estricto=True`: son señales para mirar, no
    defectos demostrados, y un validador que falla por sospechas se acaba
    ignorando.
    """
    inc = []
    avisos = []
    repetidos = {}
    doc = Elpx(ruta)

    def di(msg):
        if verbose:
            print(msg)

    # 1. XML bien formado (Elpx ya lo parseó al abrir)
    di('1. content.xml bien formado ......... OK')

    # 2. inventario
    di('2. inventario por página:')
    for pag, tipos in doc.inventario().items():
        di('   %-42s %s' % (pag[:42], tipos))

    # 3. jsonProperties parseables
    malos = 0
    for e in doc._root.iter(NS + 'jsonProperties'):
        t = (e.text or '').strip()
        if not t:
            continue
        try:
            json.loads(t)
        except Exception as ex:
            malos += 1
            inc.append('jsonProperties no parseable: %s' % ex)
    di('3. jsonProperties parseables ........ %s' % ('OK' if not malos else 'FALLO (%d)' % malos))

    # 4. identificadores
    ids = [e.text for e in doc._root.iter(NS + 'odeIdeviceId')]
    dup = [k for k, v in Counter(ids).items() if v > 1]
    if dup:
        inc.append('odeIdeviceId duplicados: %s' % dup)
    di('4. odeIdeviceId únicos .............. %s' % ('OK' if not dup else 'FALLO'))
    bad = {k: v for k, v in Counter(e.text for e in doc._root.iter(NS + 'odeBlockId')).items() if v != 2}
    if bad:
        inc.append('odeBlockId con recuento != 2: %s' % bad)
    di('   odeBlockId x2 ..................... %s' % ('OK' if not bad else 'FALLO'))

    # 5. round-trip del codec sobre cada blob cifrado
    di('5. round-trip del codec:')
    for comp in doc.componentes():
        f = ficha(comp.tipo) if comp.tipo not in (None, 'text') else None
        if not f or f['cifrado'] is not True:
            continue
        blob = comp.blob_actual
        try:
            claro = codec.decrypt(blob)
            json.loads(claro)
            ok = codec.encrypt(claro) == blob
        except Exception as ex:
            ok = False
            inc.append('%s: blob ilegible (%s)' % (comp.idevice_id, ex))
        if not ok:
            inc.append('%s: round-trip no byte-exacto' % comp.idevice_id)
        di('   %-18s %-28s %s' % (comp.tipo, comp.pagina[:28], 'byte-exacto' if ok else 'FALLO'))

    # 6. ASERCIONES DE VALOR (lo que faltaba en el piloto)
    di('6. aserciones de valor:')
    for comp in doc.componentes():
        if comp.tipo in (None, 'text'):
            continue
        f = ficha(comp.tipo)
        if not f or not f['autocorregible']:
            continue
        try:
            cfg = comp.config
        except Exception as ex:
            inc.append('%s: no puedo leer la configuración (%s)' % (comp.idevice_id, ex))
            continue
        et = '%s/%s' % (comp.pagina[:20], comp.tipo)

        # 6a. ranuras fijas: los rótulos EN USO deben ser distintos entre sí y no
        #     pueden haberse quedado con el placeholder del esqueleto
        for clave, n in (f.get('ranuras') or {}).items():
            vals = cfg.get(clave)
            if not isinstance(vals, list):
                continue
            usados = vals[:cfg.get('numberGroups', len(vals))] if clave == 'groups' else vals
            planos = [v for v in usados if isinstance(v, str)]
            if planos:
                if len(set(planos)) != len(planos):
                    inc.append('%s: `%s` tiene rótulos repetidos: %s' % (et, clave, planos))
                for v in planos:
                    if SOSPECHOSOS.match(v.strip()):
                        inc.append('%s: `%s` conserva un placeholder del esqueleto: %r'
                                   % (et, clave, v))
            if len(vals) != n:
                inc.append('%s: `%s` tiene %d ranuras y el catálogo dice %d'
                           % (et, clave, len(vals), n))

        # 6a-bis. CENTINELA: las plantillas están saneadas, así que cualquier
        #   «SIN DEFINIR» que llegue al bundle significa que un builder olvidó
        #   escribir ese campo. Antes eso mismo se traducía en texto de la unidad
        #   de la que se aprendió la plantilla, y pasaba desapercibido.
        crudo = json.dumps(cfg, ensure_ascii=False) + (comp.html or '')
        if 'SIN DEFINIR' in crudo:
            inc.append('%s: quedan campos SIN DEFINIR — un builder no ha escrito '
                       'algún campo de contenido' % et)

        # 6b. hay ítems de contenido
        if f['items']:
            items = cfg.get(f['items'])
            if not items:
                inc.append('%s: `%s` vacío' % (et, f['items']))
            elif isinstance(items, list):
                textos = [i.get('eText') or i.get('quextion') for i in items
                          if isinstance(i, dict)]
                textos = [t for t in textos if isinstance(t, str) and t.strip()]
                if textos and len(set(textos)) != len(textos):
                    inc.append('%s: ítems con texto repetido' % et)

        # 6c. las tarjetas de Clasifica apuntan a una categoría existente
        if comp.tipo == 'classify':
            ncat = cfg.get('numberGroups', 0)
            fuera = [w.get('eText') for w in cfg.get('wordsGame', [])
                     if not isinstance(w.get('group'), int) or not 0 <= w['group'] < ncat]
            if fuera:
                inc.append('%s: tarjetas con categoría fuera de rango: %s' % (et, fuera))

        # 6d. las soluciones del Test caen dentro de las opciones
        if comp.tipo == 'quick-questions':
            for q in cfg.get('questionsGame', []):
                sol, ops = q.get('solution'), q.get('options') or []
                if isinstance(sol, int) and ops and not 0 <= sol < len(ops):
                    inc.append('%s: solución %s fuera de rango (%d opciones)'
                               % (et, sol, len(ops)))

        # 6e. MAQUETA ↔ CONFIGURACIÓN: las dos copias del contenido visible
        #     tienen que decir lo mismo. Se compara TEXTO PLANO: da igual que el
        #     marcado difiera, lo que no puede diferir es lo que lee el alumnado.
        mapa = MAQUETA.get(comp.tipo)
        if f.get('maqueta') and not mapa:
            avisos.append('%s: tipo con maqueta y sin mapa de contraste en '
                          'MAQUETA — su copia visible no se está comprobando' % et)
        # La línea de arriba se fía de la ficha del catálogo, y la ficha puede
        # mentir: `classify` declaró `maqueta=False` durante un mes teniendo un
        # <div class="clasifica-instructions"> con el enunciado duplicado, y por
        # eso 6e no lo miraba NI avisaba de que no lo miraba (MC-080). Así que
        # además se mira el HTML: si hay un div de instrucciones sin mapa que lo
        # cubra, el hueco sale por sí solo aunque el catálogo diga lo contrario.
        elif not mapa and re.search(r'class="[^"]*instructions', comp.html or ''):
            avisos.append('%s: el htmlView trae un div de instrucciones pero el '
                          'tipo no tiene mapa en MAQUETA (y su ficha dice '
                          'maqueta=%r) — copia visible sin comprobar' % (et, f.get('maqueta')))
        for clave, (tag, clase) in (mapa or {}).items():
            valor = cfg.get(clave)
            if valor in (None, '', []):
                continue
            dentro = _interior(comp.html, tag, clase)
            if dentro is None:
                inc.append('%s: `%s` está en la configuración pero su copia de la '
                           'maqueta (%s.%s) no aparece en el htmlView' % (et, clave, tag, clase))
                continue
            if isinstance(valor, list):
                en_maqueta = [_plano(x) for x in
                              re.findall(r'<li\b[^>]*>(.*?)</li>', dentro, re.S)]
                esperado = [_plano(x) for x in valor if isinstance(x, str)]
                if en_maqueta != esperado:
                    inc.append('%s: `%s` diverge entre configuración y maqueta — '
                               'config=%s maqueta=%s' % (et, clave, esperado, en_maqueta))
            else:
                a, b = _plano(valor), _plano(dentro)
                if a != b:
                    inc.append('%s: `%s` diverge entre configuración y maqueta — '
                               'config=%r maqueta=%r' % (et, clave, a[:90], b[:90]))

        # material para la comprobación de olor (6f)
        for clave in FEEDBACK:
            v = cfg.get(clave)
            if isinstance(v, str) and len(_plano(v)) >= OLOR_MIN:
                repetidos.setdefault((clave, _plano(v)), set()).add(comp.pagina)
    di('   %s' % ('OK' if not inc else '%d incidencia(s)' % len(inc)))

    # 6f. OLOR: la misma realimentación en iDevices de páginas distintas casi
    #     siempre es un copiar-pegar sin revisar. No es un fallo —puede ser una
    #     fórmula deliberada—, así que sale como aviso y no tumba la validación.
    for (clave, texto), pags in sorted(repetidos.items()):
        if len(pags) > 1:
            avisos.append('`%s` idéntico en %d páginas (%s): ¿copiar-pegar sin '
                          'revisar? — %r' % (clave, len(pags),
                                             ', '.join(sorted(p[:18] for p in pags)),
                                             texto[:70]))

    if estricto:
        inc.extend('AVISO: %s' % a for a in avisos)
        avisos = []

    if verbose:
        print()
        if avisos:
            print('AVISOS (no tumban la validación): %d' % len(avisos))
            for a in avisos:
                print('  ~ %s' % a)
            print()
        if inc:
            print('RESULTADO: %d incidencia(s)' % len(inc))
            for i in inc:
                print('  · %s' % i)
        else:
            print('RESULTADO: todo OK')
    return (not inc), inc
