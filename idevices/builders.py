#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""builders.py — De la definición en YAML a la configuración de cada iDevice.

Cada builder recibe la **plantilla** (el esqueleto real de ese tipo, aprendido de un
.elpx de Pepe) y la definición del YAML, y devuelve `(config, html)`. Solo sustituye
la carga de contenido: msgs, flags y versión del motor se heredan de la plantilla, que
es lo que hace que eXeLearning los reconozca como propios.

Implementados y verificados en eXe: los cinco del piloto del 2026-07-30. Para los
demás tipos del catálogo hace falta (a) una plantilla aprendida y (b) un builder aquí;
el catálogo ya documenta el mecanismo y las trampas de cada uno.
"""
import copy
import json
import re

from . import codec
from .catalogo import ficha
from .elpx_io import extraer_datagame

__all__ = ['construir', 'BUILDERS']


# ------------------------------------------------------------------ utilidades
def _sustituye_div(html, clase, contenido, tag='div'):
    """Reescribe el interior del elemento con esa clase.

    ⚠️ `tag` importa: no todo lo que hay que reescribir es un <div>. La lista del
    iDevice «Ordena» es un <ul>, y con el patrón de <div> la sustitución no casaba
    y **fallaba en silencio** (count=1 sin coincidencias no es un error): el iDevice
    se generaba con los pasos de la unidad de la que se aprendió la plantilla.
    Incidencia del 2026-08-03, SdA 01 de 1º TECI.
    """
    pat = re.compile(r'(<' + tag + r' class="' + re.escape(clase) + r'[^"]*">)(.*?)(</' + tag + r'>)',
                     re.S)
    nuevo, n = pat.subn(lambda m: m.group(1) + contenido + m.group(3), html, count=1)
    if n == 0:
        raise ValueError('no encuentro <%s class="%s"> en la maqueta: la sustitución '
                         'habría fallado en silencio' % (tag, clase))
    return nuevo


def _pon_datagame(html, clase, blob):
    return re.sub(r'(class="' + re.escape(clase) + r'[^"]*"\s*>).*?(</div>)',
                  lambda m: m.group(1) + blob + m.group(2), html, count=1, flags=re.S)


def _config_de_plantilla(pl):
    """Configuración base tal cual está en la plantilla."""
    f = ficha(pl['tipo'])
    if f['mecanismo'] == 'jsonProperties':
        return json.loads(pl['jsonProperties'] or '{}')
    blob = extraer_datagame(pl['htmlView'], f['clase'])
    return codec.loads_cifrado(blob) if f['cifrado'] is True else json.loads(blob)


def _texto_plano(html):
    return re.sub(r'<[^>]+>', '', html or '').strip()


def _envuelve(txt):
    """Los campos de texto de varios iDevices esperan HTML con su <p>."""
    txt = (txt or '').strip()
    if not txt or txt.startswith('<'):
        return txt
    return '<p>%s</p>' % txt


def _ranuras(nombres, n=9, patron='Grupo %d'):
    """Rellena hasta `n` ranuras con los placeholders que usa eXe.

    Trampa que rompió el piloto: estas listas son de STRINGS, no de dicts, y tienen
    número fijo de posiciones aunque solo se usen las primeras.
    """
    g = list(nombres)
    g += [patron % i for i in range(len(g) + 1, n + 1)]
    return g


# Tiempo por pregunta de los juegos QuExt: el campo `time` es un ÍNDICE de esta lista de
# segundos (common.js, gamification.helpers.getTimeSeconds). La plantilla trae 0 = 15 s, que
# no deja calcular nada: con `tiempo: 180` en el YAML cada pregunta tiene 3 min. Si falta la
# clave, se hereda el de la plantilla (comportamiento anterior). DOCA-113, 2026-10-17.
TIEMPOS_QUEXT = [15, 30, 60, 180, 300, 600]


def _indice_tiempo(segundos):
    if segundos is None:
        return None
    if segundos not in TIEMPOS_QUEXT:
        raise ValueError('tiempo %r no válido: usa uno de %s (segundos)' % (segundos, TIEMPOS_QUEXT))
    return TIEMPOS_QUEXT.index(segundos)


# ------------------------------------------------------------------- builders
def build_quick_questions(pl, d):
    """Test. Realimentación por pregunta (no por opción)."""
    cfg = _config_de_plantilla(pl)
    modelo = copy.deepcopy(cfg['questionsGame'][0])
    tiempo = _indice_tiempo(d.get('tiempo'))
    nuevas = []
    for p in d['preguntas']:
        q = copy.deepcopy(modelo)
        q['quextion'] = p['enunciado']
        q['options'] = list(p['opciones'])
        q['numberOptions'] = len(p['opciones'])
        q['solution'] = p['solucion']
        q['msgHit'] = p.get('acierto', '')
        q['msgError'] = p.get('error', '')
        if tiempo is not None:
            q['time'] = tiempo
        nuevas.append(q)
    cfg['questionsGame'] = nuevas
    cfg['instructions'] = _texto_plano(d.get('instrucciones', ''))
    # `instructionsExe` es la MISMA instrucción percent-codificada. Nadie la
    # escribía, así que cada Test generado se quedaba con la de la unidad de
    # la que se aprendió la plantilla. Lo destapó el centinela (2026-08-06).
    cfg['instructionsExe'] = codec.pc(d.get('instrucciones', ''))
    cfg['id'] = codec.nuevo_idevice_id()
    html = _pon_datagame(pl['htmlView'], 'quext-DataGame', codec.dumps_cifrado(cfg))
    html = _sustituye_div(html, 'quext-instructions', d.get('instrucciones', ''))
    html = re.sub(r'data-id="[^"]*"', 'data-id="%s"' % cfg['id'], html)
    return cfg, html


def build_classify(pl, d):
    """Clasifica. OJO: `groups` es lista de strings con 9 ranuras fijas."""
    cfg = _config_de_plantilla(pl)
    cats = list(d['categorias'])
    modelo = copy.deepcopy(cfg['wordsGame'][0])
    cfg['wordsGame'] = []
    for t in d['tarjetas']:
        w = copy.deepcopy(modelo)
        w['eText'] = t['texto']
        w['group'] = cats.index(t['categoria'])
        cfg['wordsGame'].append(w)
    cfg['groups'] = _ranuras(cats, 9)
    cfg['numberGroups'] = len(cats)
    cfg['instructions'] = d.get('instrucciones', '')
    cfg['id'] = codec.nuevo_idevice_id()
    html = _pon_datagame(pl['htmlView'], 'clasifica-DataGame', codec.dumps_cifrado(cfg))
    html = _sustituye_div(html, 'clasifica-instructions', d.get('instrucciones', ''))
    html = re.sub(r'data-id="[^"]*"', 'data-id="%s"' % cfg['id'], html)
    return cfg, html


def build_relate(pl, d):
    """Relaciona. JSON en claro, pero los textos van percent-encoded."""
    cfg = _config_de_plantilla(pl)
    modelo = copy.deepcopy(cfg['cardsGame'][0])
    cfg['cardsGame'] = []
    for par in d['pares']:
        c = copy.deepcopy(modelo)
        c['eText'] = codec.pc(par['a'])
        c['eTextBk'] = codec.pc(par['b'])
        cfg['cardsGame'].append(c)
    cfg['instructions'] = d.get('instrucciones', '')
    # Nivel: en «básico» (type 0) eXe solo deja conectar las parejas buenas y la
    # actividad no evalúa; en «avanzado» (type 2) se conecta libremente y al final se
    # revelan aciertos y errores. Decisión de Pepe (2026-10-09): avanzado siempre,
    # salvo que el YAML pida `nivel: basico`. Valor leído de un Relaciona que Pepe
    # pasó a avanzado en eXe (SdA 07 de 1.º TECI).
    cfg['type'] = 0 if str(d.get('nivel', 'avanzado')).lower() in ('basico', 'básico') else 2
    cfg['id'] = codec.nuevo_idevice_id()
    html = _pon_datagame(pl['htmlView'], 'relaciona-DataGame',
                         json.dumps(cfg, ensure_ascii=False))
    html = _sustituye_div(html, 'relaciona-instructions', d.get('instrucciones', ''))
    return cfg, html


def build_trueorfalse(pl, d):
    """Verdadero o falso. jsonProperties + maqueta HTML.

    ⚠️ Sus claves NO son las del Test, aunque el array se llame igual. Aquí son
    `question` / `feedback` / `suggestion`, los textos van envueltos en <p>, la
    solución es 1/0 (verdadero/falso) y las instrucciones viven en
    `eXeGameInstructions`, no en `instructions`. Verificado sobre .elpx real.
    """
    cfg = _config_de_plantilla(pl)
    modelo = copy.deepcopy(cfg['questionsGame'][0])
    cfg['questionsGame'] = []
    for a in d['afirmaciones']:
        q = copy.deepcopy(modelo)
        q['question'] = _envuelve(a['texto'])
        q['solution'] = 1 if a['verdadero'] else 0
        q['feedback'] = _envuelve(a.get('retroalimentacion', ''))
        q['suggestion'] = _envuelve(a.get('pista', ''))
        cfg['questionsGame'].append(q)
    cfg['eXeGameInstructions'] = d.get('instrucciones', '')
    ide = codec.nuevo_idevice_id()
    cfg['id'] = ide
    html = _sustituye_div(pl['htmlView'], 'TOFP-instructions', d.get('instrucciones', ''))
    # la maqueta cuelga los ids del ideviceId: hay que reescribirlos todos
    viejo = pl.get('idevice_id') or _id_de_plantilla(pl)
    if viejo:
        html = html.replace(viejo, ide)
    return cfg, html


def build_scrambled_list(pl, d):
    """Lista desordenada. `options` en el ORDEN CORRECTO + <ul> de la maqueta."""
    cfg = _config_de_plantilla(pl)
    cfg['options'] = list(d['pasos'])
    cfg['instructions'] = d.get('instrucciones', '')
    # Feedback: si el YAML no lo define, un texto GENÉRICO sin materia. Nunca se
    # hereda de la plantilla — es lo que metió el texto de otra unidad en la SdA 01
    # (2026-08-05) y otra vez en la SdA 02 (2026-08-06).
    cfg['rightText'] = d.get('correctText') or '¡Correcto!'
    cfg['wrongText'] = (d.get('wrongText')
                        or 'Ese no es el orden. Repasa el material y prueba otra vez.')
    ide = codec.nuevo_idevice_id()
    cfg['id'] = ide
    lis = '\n'.join('<li data-orig-index="%d">%s</li>' % (i, p)
                    for i, p in enumerate(d['pasos']))
    html = _sustituye_div(pl['htmlView'], 'exe-sortableList-list', lis, tag='ul')
    html = _sustituye_div(html, 'exe-sortableList-instructions', d.get('instrucciones', ''))
    # la maqueta lleva su propia copia del feedback: si solo se escribe el JSON, el
    # texto viejo sigue visible y eXe puede repoblar el formulario desde ahí
    html = _sustituye_div(html, 'exe-sortableList-rightText', cfg['rightText'], tag='p')
    html = _sustituye_div(html, 'exe-sortableList-wrongText', cfg['wrongText'], tag='p')
    viejo = pl.get('idevice_id') or _id_de_plantilla(pl)
    if viejo:
        html = html.replace(viejo, ide)
    return cfg, html


def _id_de_plantilla(pl):
    m = re.search(r'data-id="([^"]+)"', pl['htmlView'])
    if m:
        return m.group(1)
    m = re.search(r'id="sl?idevice-([^"]+)"', pl['htmlView'])
    return None


BUILDERS = {
    'quick-questions': build_quick_questions,
    'classify': build_classify,
    'relate': build_relate,
    'trueorfalse': build_trueorfalse,
    'scrambled-list': build_scrambled_list,
}


def construir(pl, definicion):
    """Punto de entrada: (plantilla, definición del YAML) -> (config, html)."""
    tipo = definicion['tipo']
    if tipo not in BUILDERS:
        f = ficha(tipo)
        pista = ('' if not f else
                 ' El catálogo dice: mecanismo=%s, clase=%s, cifrado=%s, items=%s, '
                 'ranuras=%s. %s' % (f['mecanismo'], f['clase'], f['cifrado'],
                                     f['items'], f['ranuras'], f['notas']))
        raise NotImplementedError(
            'no hay builder para %r. Tipos listos: %s.%s'
            % (tipo, ', '.join(sorted(BUILDERS)), pista))
    return BUILDERS[tipo](pl, definicion)
