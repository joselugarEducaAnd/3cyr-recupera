#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""elpx_io.py — Lectura, parcheo quirúrgico y biblioteca de plantillas de .elpx.

Principio de diseño (regla del sistema): **desde que Pepe añade interactividad a un
.elpx, ese .elpx es la fuente de verdad y NO se regenera**. Este módulo por eso no
reescribe el content.xml con un serializador XML (que reordenaría atributos y
reescaparía CDATA), sino que hace **sustitución exacta de strings** sobre el texto
original y copia el resto del ZIP byte a byte.

Comprobado en el piloto del 2026-07-30: al parchear un campo, de las 207 entradas del
bundle solo cambia content.xml, y dentro de él un único tramo.
"""
import json
import os
import random
import re
import string
import time
import zipfile
from xml.etree import ElementTree as ET

from . import codec
from .catalogo import ficha

NS = '{http://www.intef.es/xsd/ode}'

__all__ = ['Elpx', 'extraer_datagame', 'biblioteca_plantillas', 'aprender_plantillas']


# ------------------------------------------------------------------ inserción
def _nuevo_id(prefijo):
    """Id con el mismo formato que genera eXeLearning: <prefijo>-<ms>-<9 alfanum>."""
    ms = int(time.time() * 1000) + random.randint(0, 999)
    suf = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(9))
    return '%s-%d-%s' % (prefijo, ms, suf)


def _id_de_plantilla(pl):
    """El idevice_id con el que se guardó el esqueleto, para reescribirlo."""
    if pl.get('idevice_id'):
        return pl['idevice_id']
    for texto in (pl.get('jsonProperties') or '', pl.get('htmlView') or ''):
        m = re.search(r'idevice-\d+-[a-z0-9]+', texto)
        if m:
            return m.group(0)
    return None


class _Elem(object):
    """Mínimo imprescindible para que Componente lea una plantilla suelta."""

    def __init__(self, campos):
        self._c = campos

    def findtext(self, clave):
        return self._c.get(clave.replace(NS, ''), '')


def _componente_ficticio(tipo, html, jprops):
    return _Elem({'odeIdeviceTypeName': tipo, 'odeIdeviceId': '',
                  'htmlView': html, 'jsonProperties': jprops})


_BLOQUE = """        <odePagStructure>
          <odePageId>%(pid)s</odePageId>
          <odeBlockId>%(bid)s</odeBlockId>
          <blockName>%(nombre)s</blockName>
          <iconName></iconName>
          <odePagStructureOrder>%(orden)d</odePagStructureOrder>
          <odePagStructureProperties>
            <odePagStructureProperty><key>visibility</key><value>true</value></odePagStructureProperty>
            <odePagStructureProperty><key>teacherOnly</key><value>false</value></odePagStructureProperty>
            <odePagStructureProperty><key>allowToggle</key><value>true</value></odePagStructureProperty>
            <odePagStructureProperty><key>minimized</key><value>false</value></odePagStructureProperty>
            <odePagStructureProperty><key>cssClass</key><value></value></odePagStructureProperty>
          </odePagStructureProperties>
          <odeComponents>
            <odeComponent>
              <odePageId>%(pid)s</odePageId>
              <odeBlockId>%(bid)s</odeBlockId>
              <odeIdeviceId>%(iid)s</odeIdeviceId>
              <odeIdeviceTypeName>%(tipo)s</odeIdeviceTypeName>
              <htmlView><![CDATA[%(html)s]]></htmlView>
              <jsonProperties><![CDATA[%(json)s]]></jsonProperties>
              <odeComponentsOrder>0</odeComponentsOrder>
              <odeComponentsProperties>
                <odeComponentsProperty><key>visibility</key><value>true</value></odeComponentsProperty>
                <odeComponentsProperty><key>teacherOnly</key><value>false</value></odeComponentsProperty>
                <odeComponentsProperty><key>cssClass</key><value></value></odeComponentsProperty>
              </odeComponentsProperties>
            </odeComponent>
          </odeComponents>
        </odePagStructure>
"""


def extraer_datagame(html, clase):
    """Devuelve el contenido del <div class="XXX-DataGame">.

    No vale un regex `[^<]*`: el JSON puede contener '<' (las `instructions` van en
    HTML). Se busca el cierre del div a partir de la apertura.
    """
    i = html.find('class="%s' % clase)
    if i < 0:
        return None
    j = html.index('>', i) + 1
    return html[j:html.index('</div>', j)]


class Componente(object):
    """Un iDevice dentro de una página."""

    def __init__(self, elem, pagina):
        self.elem = elem
        self.pagina = pagina
        self.tipo = elem.findtext(NS + 'odeIdeviceTypeName')
        self.idevice_id = elem.findtext(NS + 'odeIdeviceId')
        self.html = elem.findtext(NS + 'htmlView') or ''
        self.json_props_raw = elem.findtext(NS + 'jsonProperties') or ''

    # -- configuración ----------------------------------------------------
    @property
    def config(self):
        """Configuración del iDevice, ya descifrada y parseada."""
        f = ficha(self.tipo)
        if f is None:
            raise KeyError('tipo %r no catalogado' % self.tipo)
        if f['mecanismo'] == 'jsonProperties':
            return json.loads(self.json_props_raw or '{}')
        blob = extraer_datagame(self.html, f['clase'])
        if blob is None:
            raise ValueError('no encuentro el div %s en %s' % (f['clase'], self.idevice_id))
        if f['cifrado'] is True:
            return codec.loads_cifrado(blob)
        if f['cifrado'] is False:
            return json.loads(blob)
        raise NotImplementedError(
            'el codec %r de %s no está implementado' % (f['cifrado'], self.tipo))

    @property
    def blob_actual(self):
        """El string exacto que hay hoy en el .elpx (para sustituirlo)."""
        f = ficha(self.tipo)
        if f['mecanismo'] == 'jsonProperties':
            return self.json_props_raw
        return extraer_datagame(self.html, f['clase'])

    def blob_para(self, cfg):
        """Serializa una configuración al formato que toca este tipo."""
        f = ficha(self.tipo)
        if f['mecanismo'] == 'jsonProperties' or f['cifrado'] is False:
            return json.dumps(cfg, ensure_ascii=False)
        return codec.dumps_cifrado(cfg)

    def __repr__(self):
        return '<Componente %s %s en %r>' % (self.tipo, self.idevice_id, self.pagina)


class Elpx(object):
    """Un bundle .elpx abierto para inspección y parcheo."""

    def __init__(self, ruta):
        self.ruta = ruta
        self.zip = zipfile.ZipFile(ruta)
        self.xml = self.zip.read('content.xml').decode('utf-8')
        self._root = ET.fromstring(self.xml)
        self._pendientes = []          # [(viejo, nuevo)]
        self._inserciones = []         # [(posicion, bloque_xml)]

    # -- inspección -------------------------------------------------------
    def paginas(self):
        return [n.findtext(NS + 'pageName') for n in self._root.findall('.//' + NS + 'odeNavStructure')]

    def componentes(self, pagina=None, tipo=None):
        out = []
        for nav in self._root.findall('.//' + NS + 'odeNavStructure'):
            nombre = nav.findtext(NS + 'pageName') or ''
            if pagina is not None and pagina not in nombre:
                continue
            for c in nav.findall('.//' + NS + 'odeComponent'):
                comp = Componente(c, nombre)
                if tipo is not None and comp.tipo != tipo:
                    continue
                out.append(comp)
        return out

    def inventario(self):
        from collections import Counter
        return {p: dict(Counter(c.tipo for c in self.componentes(pagina=p)))
                for p in self.paginas()}

    # -- parcheo ----------------------------------------------------------
    def parchear(self, comp, cfg_nueva):
        """Encola la sustitución de la configuración de UN componente.

        No escribe nada hasta `guardar()`. Falla en vez de adivinar si el string a
        sustituir no es único en content.xml.
        """
        viejo = comp.blob_actual
        if viejo is None:
            raise ValueError('no localizo la configuración de %r' % comp)
        nuevo = comp.blob_para(cfg_nueva)
        if self.xml.count(viejo) != 1:
            raise ValueError('el blob de %r aparece %d veces en content.xml; esperaba 1'
                             % (comp, self.xml.count(viejo)))
        self._pendientes.append((viejo, nuevo))
        return self

    # -- inserción --------------------------------------------------------
    def insertar(self, pagina, tipo, cfg, plantilla=None, nombre_bloque=None,
                 html_maqueta=None):
        """Encola la creación de un iDevice NUEVO al final de una página.

        Sin esto había que abrir eXeLearning e insertar el iDevice a mano solo para
        que existiera un `odeIdeviceId` al que apuntar, que es justo el trabajo
        manual que este módulo viene a quitar. El esqueleto sale de la biblioteca de
        plantillas (`aprender`), así que se heredan msgs, flags y versión del motor
        igual que al parchear.

        Respeta el principio del módulo: **no reserializa**. Compone el bloque como
        texto y lo empalma justo antes del `</odePagStructures>` de esa página.

        Devuelve el `idevice_id` generado.
        """
        pl = plantilla or cargar_plantilla(tipo)
        f = ficha(tipo)
        if f is None:
            raise KeyError('tipo %r no catalogado' % tipo)

        # localizar la página en el XML crudo y su punto de inserción
        nav = None
        for n in self._root.findall('.//' + NS + 'odeNavStructure'):
            if pagina in (n.findtext(NS + 'pageName') or ''):
                nav = n
                break
        if nav is None:
            raise ValueError('no encuentro la página %r. Páginas: %s' % (pagina, self.paginas()))
        pid = nav.findtext(NS + 'odePageId')
        i, cierre = self._tramo_pagina(self.xml, pid)
        # nº de bloques que ya tiene + los que ya hemos encolado para esta misma página
        orden = (self.xml.count('<odePagStructure>', i, cierre)
                 + sum(1 for p, _ in self._inserciones if p == pid))

        iid = _nuevo_id('idevice')
        bid = _nuevo_id('block')

        # El HTML de partida. Los tipos con MAQUETA (trueorfalse, scrambled-list…)
        # llevan el contenido visible dentro del htmlView, no solo en la config: si
        # se parte de la plantilla en crudo, el iDevice se crea con los textos de la
        # unidad de la que se aprendió el esqueleto. La configuración quedaba bien y
        # la validación daba OK, pero en pantalla salía otra cosa. Por eso el builder
        # nos pasa su maqueta ya reescrita. (Incidencia del 2026-08-03, SdA 01 de
        # 1º TECI: los «Ordena» mostraban las fases del aprendizaje supervisado.)
        html = pl['htmlView'] if html_maqueta is None else html_maqueta
        jprops = pl.get('jsonProperties') or ''

        # el esqueleto trae los ids de su origen: hay que reescribirlos todos.
        # Si viene maqueta del builder, esa lleva ADEMÁS el id que él generó.
        viejos = {_id_de_plantilla(pl)}
        m = re.search(r'idevice-\d+-[a-z0-9]+', html)
        if m:
            viejos.add(m.group(0))
        for viejo_iid in sorted(v for v in viejos if v and v != iid):
            html = html.replace(viejo_iid, iid)
            jprops = jprops.replace(viejo_iid, iid)
            # tipos con maqueta usan además el prefijo slidevice-
            html = html.replace(viejo_iid.replace('idevice-', 'slidevice-'),
                                iid.replace('idevice-', 'slidevice-'))
            jprops = jprops.replace(viejo_iid.replace('idevice-', 'slidevice-'),
                                    iid.replace('idevice-', 'slidevice-'))
        # que la config apunte al mismo id que la maqueta, no al del builder
        if isinstance(cfg, dict) and cfg.get('id'):
            cfg = dict(cfg)
            cfg['id'] = iid

        # meter la configuración pedida en el esqueleto
        tmp = Componente(_componente_ficticio(tipo, html, jprops), pagina)
        viejo_blob = tmp.blob_actual
        nuevo_blob = tmp.blob_para(cfg)
        if f['mecanismo'] == 'jsonProperties':
            jprops = nuevo_blob
        else:
            if viejo_blob is None:
                raise ValueError('la plantilla de %r no trae su bloque de datos' % tipo)
            html = html.replace(viejo_blob, nuevo_blob, 1)

        bloque = _BLOQUE % {
            'pid': pid, 'bid': bid, 'iid': iid, 'tipo': tipo,
            'nombre': nombre_bloque or (f.get('titulo') or tipo),
            'orden': orden,
            'html': html, 'json': jprops,
        }
        self._inserciones.append((pid, bloque))
        return iid

    @staticmethod
    def _tramo_pagina(xml, pid):
        """(inicio, posición del `</odePagStructures>`) de la página `pid`.

        Se recalcula sobre el texto VIGENTE, nunca sobre offsets guardados: los
        parches previos cambian la longitud del XML y cualquier posición cacheada
        dejaría de apuntar donde debe. (Ese fue el fallo del primer intento: los
        bloques nuevos acababan anidados dentro del componente anterior; el XML
        seguía bien formado y la validación daba OK, pero eXe no los vería como
        bloques de la página.)
        """
        marca = '<odePageId>%s</odePageId>' % pid
        i = xml.find(marca)
        if i < 0:
            raise ValueError('no localizo la página %r en el content.xml' % pid)
        cierre = xml.find('</odePagStructures>', i)
        if cierre < 0:
            raise ValueError('la página %r no tiene <odePagStructures>' % pid)
        return i, cierre

    def _comprobar_inserciones(self, xml):
        """Que cada bloque insertado sea HIJO DIRECTO del `<odePagStructures>` de su página.

        No basta con que el XML esté bien formado: un bloque mal empalmado puede quedar
        anidado dentro del componente anterior y seguir siendo XML válido. Una búsqueda
        por descendencia (`.//odeComponent`) tampoco lo detecta. Hay que mirar el nivel.
        """
        if not self._inserciones:
            return
        raiz = ET.fromstring(xml)
        esperados = {}
        for pid, bloque in self._inserciones:
            m = re.search(r'<odeIdeviceId>([^<]+)</odeIdeviceId>', bloque)
            esperados.setdefault(pid, []).append(m.group(1))
        for nav in raiz.findall('.//' + NS + 'odeNavStructure'):
            pid = nav.findtext(NS + 'odePageId')
            if pid not in esperados:
                continue
            cont = nav.find(NS + 'odePagStructures')
            directos = set()
            for blq in (cont.findall(NS + 'odePagStructure') if cont is not None else []):
                comps = blq.find(NS + 'odeComponents')
                for c in (comps.findall(NS + 'odeComponent') if comps is not None else []):
                    directos.add(c.findtext(NS + 'odeIdeviceId'))
            faltan = [i for i in esperados[pid] if i not in directos]
            if faltan:
                raise ValueError(
                    'los iDevices %s no han quedado como bloque de la página %s. '
                    'El XML está bien formado pero mal anidado: NO guardes este archivo.'
                    % (', '.join(faltan), pid))

    def guardar(self, destino):
        """Aplica lo encolado y escribe el .elpx, copiando el resto byte a byte."""
        if not self._pendientes and not self._inserciones:
            raise ValueError('no hay nada que guardar')
        nuevo_xml = self.xml
        for viejo, nuevo in self._pendientes:
            if nuevo_xml.count(viejo) != 1:
                raise ValueError('un blob dejó de ser único al aplicar los parches')
            nuevo_xml = nuevo_xml.replace(viejo, nuevo, 1)
        # cada inserción se localiza sobre el texto ya modificado, no sobre offsets
        for pid, bloque in self._inserciones:
            _, cierre = self._tramo_pagina(nuevo_xml, pid)
            nuevo_xml = nuevo_xml[:cierre] + bloque + nuevo_xml[cierre:]
        ET.fromstring(nuevo_xml)       # sigue bien formado
        self._comprobar_inserciones(nuevo_xml)
        with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as zout:
            for info in self.zip.infolist():
                datos = self.zip.read(info.filename)
                if info.filename == 'content.xml':
                    datos = nuevo_xml.encode('utf-8')
                zout.writestr(info, datos)
        return destino


# ---------------------------------------------------------------- plantillas
def biblioteca_plantillas():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plantillas')


def aprender_plantillas(ruta_elpx, destino=None, verbose=True):
    """Extrae de un .elpx un esqueleto por cada tipo de iDevice que contenga.

    Así el generador «aprende» el andamiaje real de un tipo nuevo la primera vez que
    Pepe lo usa en eXeLearning, en vez de tener que inventarlo. Se guarda el htmlView
    y el jsonProperties íntegros: al construir, solo se sustituye la carga de
    contenido y se heredan msgs, flags y versión del motor.
    """
    destino = destino or biblioteca_plantillas()
    os.makedirs(destino, exist_ok=True)
    doc = Elpx(ruta_elpx)
    nuevos = []
    for comp in doc.componentes():
        if comp.tipo in (None, 'text'):
            continue
        dst = os.path.join(destino, comp.tipo + '.json')
        if os.path.exists(dst):
            continue
        with open(dst, 'w', encoding='utf-8') as fh:
            json.dump({'tipo': comp.tipo,
                       'htmlView': comp.html,
                       'jsonProperties': comp.json_props_raw,
                       'origen': os.path.basename(ruta_elpx)},
                      fh, ensure_ascii=False, indent=1)
        nuevos.append(comp.tipo)
        if verbose:
            print('  aprendido: %s' % comp.tipo)
    if verbose and not nuevos:
        print('  (ningún tipo nuevo)')
    return nuevos


def cargar_plantilla(tipo, destino=None):
    ruta = os.path.join(destino or biblioteca_plantillas(), tipo + '.json')
    if not os.path.exists(ruta):
        raise FileNotFoundError(
            'no hay plantilla para %r. Monta uno a mano en eXeLearning, guarda el .elpx '
            'y pásalo por `gen_idevices.py aprender <archivo.elpx>`.' % tipo)
    with open(ruta, encoding='utf-8') as fh:
        return json.load(fh)
