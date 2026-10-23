#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""catalogo.py — Cómo guarda su configuración cada iDevice de eXeLearning 4.

Fuente: lectura del código de los 51 iDevices «base» del app.asar de eXeLearning 4
(`config.xml` + `edition/*.js`), 2026-07-30. Mapa narrativo completo, con las
trampas de cada tipo, en el informe `mapa_idevices.md` del piloto.

Estados de verificación (campo `verificado`):
  'elpx'   round-trip byte-exacto contra un .elpx real Y comprobado en eXe por Pepe
  'codigo' leído en el JS del iDevice, pero sin ejemplar real todavía
  'no'     no determinado

Discriminador general hallado en los config.xml:
  <component-type>json</component-type>  -> la configuración va en `jsonProperties`
  (sin ese tag)                          -> va en un <div class="XXX-DataGame"> del htmlView
"""

__all__ = ['CATALOGO', 'ficha', 'tipos_verificados', 'tipos_autocorregibles']

# mecanismo: 'jsonProperties' | 'datagame'
# cifrado:   True | False | 'escape' (solo escape, sin XOR) | 'base64' (esquema propio)
# maqueta:   ¿el htmlView lleva HTML renderizado que también hay que reescribir?
# ranuras:   claves con número fijo de posiciones (la trampa que rompió el piloto)
CATALOGO = {
    # ---------------------------------------------------------------- verificados
    'quick-questions': dict(
        titulo='Test', categoria='Assessment and tracking', autocorregible=True,
        mecanismo='datagame', clase='quext-DataGame', cifrado=True, maqueta=False,
        items='questionsGame', ranuras={}, verificado='elpx',
        notas='Realimentación por pregunta (msgHit/msgError), no por opción.'),
    'classify': dict(
        titulo='Clasifica', categoria='Interactive activities', autocorregible=True,
        mecanismo='datagame', clase='clasifica-DataGame', cifrado=True, maqueta=True,
        items='wordsGame', ranuras={'groups': 9}, verificado='elpx',
        notas='`groups` es lista PLANA DE STRINGS con 9 ranuras; el rótulo de categoría '
              'vive SOLO en la configuración. `numberGroups` = categorías usadas. '
              'Cada tarjeta apunta a su categoría con `group` = índice 0-based. '
              'OJO: `maqueta` era False y ERA FALSO (corregido 2026-09-07, MC-080). Los '
              'rótulos de categoría y las tarjetas sí viven solo en el blob, pero el '
              'ENUNCIADO se duplica en `<div class="clasifica-instructions">` del '
              'htmlView, así que un parcheo que toque solo la configuración deja el '
              'enunciado viejo a la vista. Es el tipo donde ya falló tres veces.'),
    'relate': dict(
        titulo='Relaciona', categoria='Interactive activities', autocorregible=True,
        mecanismo='datagame', clase='relaciona-DataGame', cifrado=False, maqueta=False,
        items='cardsGame', ranuras={}, verificado='elpx',
        notas='JSON en claro, pero los campos de texto (eText/eTextBk) van '
              'percent-encoded UTF-8.'),
    'trueorfalse': dict(
        titulo='Verdadero o falso', categoria='Assessment and tracking', autocorregible=True,
        mecanismo='jsonProperties', clase=None, cifrado=False, maqueta=True,
        items='questionsGame', ranuras={}, verificado='elpx',
        notas='Lleva maqueta HTML además de la configuración. Realimentación y pista '
              'por afirmación.'),
    'scrambled-list': dict(
        titulo='Lista desordenada', categoria='Interactive activities', autocorregible=True,
        mecanismo='jsonProperties', clase=None, cifrado=False, maqueta=True,
        items='options', ranuras={}, verificado='elpx',
        notas='`options` es un array plano de strings EN EL ORDEN CORRECTO. La maqueta '
              'HTML es una <ul> con <li data-orig-index="N">: hay que reescribirla también.'),

    # ------------------------------------------------- leídos en código, sin ejemplar
    'complete': dict(
        titulo='Completa', categoria='Interactive activities', autocorregible=True,
        mecanismo='datagame', clase='completa-DataGame', cifrado=True, maqueta=True,
        items=None, ranuras={}, verificado='codigo',
        notas='Sin array: un texto único con los huecos marcados @@respuesta@@. Además '
              'duplica el texto SIN cifrar en un div `completa-text-game`: hay que '
              'escribir los dos o quedan descuadrados.'),
    'quick-questions-multiple-choice': dict(
        titulo='Selecciona', categoria='Assessment and tracking', autocorregible=True,
        mecanismo='datagame', clase='selecciona-DataGame', cifrado=True, maqueta=False,
        items='selectsGame', ranuras={'options': 4}, verificado='codigo', notas=''),
    'sort': dict(
        titulo='Ordena', categoria='Interactive activities', autocorregible=True,
        mecanismo='datagame', clase='ordena-DataGame', cifrado=True, maqueta=False,
        items='phrasesGame', ranuras={}, verificado='codigo', notas=''),
    'dragdrop': dict(
        titulo='Arrastra y suelta', categoria='Interactive activities', autocorregible=True,
        mecanismo='datagame', clase='dragdrop-DataGame', cifrado=False, maqueta=False,
        items='cardsGame', ranuras={}, verificado='codigo',
        notas='Campos `type`/`correct` presentes pero muertos en el editor.'),
    'identify': dict(
        titulo='Identifica', categoria='Interactive activities', autocorregible=True,
        mecanismo='datagame', clase='identifica-DataGame', cifrado=True, maqueta=False,
        items='questionsGame', ranuras={'clues': 8}, verificado='codigo', notas=''),
    'adaptative-quiz': dict(
        titulo='Cuestionario adaptativo', categoria='Assessment and tracking',
        autocorregible=True, mecanismo='jsonProperties', clase=None, cifrado=False,
        maqueta=None, items='questionsGame', ranuras={'options': 6}, verificado='codigo',
        notas='Da mensaje de acierto/error por pregunta.'),
    'quick-questions-video': dict(
        titulo='Test de vídeo', categoria='Assessment and tracking', autocorregible=True,
        mecanismo='datagame', clase='vquext-DataGame', cifrado=True, maqueta=False,
        items='questionsGame', ranuras={'options': 4}, verificado='codigo',
        notas='Las preguntas se ordenan por el campo `time`.'),
    'guess': dict(
        titulo='Adivina', categoria='Assessment and tracking', autocorregible=True,
        mecanismo='datagame', clase='adivina-DataGame', cifrado=True, maqueta=False,
        items='wordsGame', ranuras={}, verificado='codigo', notas=''),
    'crossword': dict(
        titulo='Crucigrama', categoria='Games', autocorregible=True,
        mecanismo='datagame', clase='crucigrama-DataGame', cifrado=True, maqueta=False,
        items='wordsGame', ranuras={}, verificado='codigo',
        notas='El JSON no lleva coordenadas: la rejilla se calcula en runtime.'),
    'word-search': dict(
        titulo='Sopa de letras', categoria='Games', autocorregible=True,
        mecanismo='datagame', clase='sopa-DataGame', cifrado=True, maqueta=False,
        items='wordsGame', ranuras={}, verificado='codigo',
        notas='Sin rejilla en el JSON; el campo `solution` está muerto.'),
    'hidden-image': dict(
        titulo='Imagen oculta', categoria='Games', autocorregible=True,
        mecanismo='datagame', clase='hiddenimage-DataGame', cifrado=True, maqueta='parcial',
        items='questionsGame', ranuras={'options': 4}, verificado='codigo', notas=''),
    'discover': dict(
        titulo='Descubre', categoria='Games', autocorregible=True,
        mecanismo='datagame', clase='descubre-DataGame', cifrado=True, maqueta='parcial',
        items='wordsGame', ranuras={'data': 4}, verificado='codigo', notas=''),
    'challenge': dict(
        titulo='Desafío', categoria='Games', autocorregible=True,
        mecanismo='datagame', clase='desafio-DataGame', cifrado=True, maqueta='parcial',
        items='challengesGame', ranuras={'clues': 3}, verificado='codigo', notas=''),
    'puzzle': dict(
        titulo='Puzle', categoria='Games', autocorregible=True,
        mecanismo='datagame', clase='puzzle-DataGame', cifrado=True, maqueta='parcial',
        items='puzzlesGame', ranuras={}, verificado='codigo', notas=''),
    'az-quiz-game': dict(
        titulo='Rosco A-Z', categoria='Games', autocorregible=True,
        mecanismo='datagame', clase='rosco-DataGame', cifrado=True, maqueta=False,
        items='wordsGame', ranuras={'wordsGame': 26}, verificado='codigo',
        notas='26 ranuras fijas, una por letra del alfabeto.'),
    'flipcards': dict(
        titulo='Cartas de memoria', categoria='Interactive activities', autocorregible=False,
        mecanismo='datagame', clase='flipcards-DataGame', cifrado=False, maqueta=False,
        items='cardsGame', ranuras={}, verificado='codigo',
        notas='Campos `type`/`correct` presentes pero muertos.'),
    'beforeafter': dict(
        titulo='Antes/Después', categoria='Interactive activities', autocorregible=False,
        mecanismo='datagame', clase='beforeafter-DataGame', cifrado=False, maqueta=False,
        items='cardsGame', ranuras={}, verificado='codigo', notas=''),

    # ------------------------------------------------------ excepciones del codec
    'rubric': dict(
        titulo='Rúbrica', categoria='Assessment and tracking', autocorregible=False,
        mecanismo='datagame', clase='exe-rubrics-DataGame', cifrado='escape', maqueta=False,
        items=None, ranuras={}, verificado='codigo',
        notas='EXCEPCIÓN: solo escape(), sin XOR. Matriz categories × scores.'),
    'trivial': dict(
        titulo='TriviExt', categoria='Games', autocorregible=True,
        mecanismo='datagame', clase='trivial-DataGame', cifrado='base64', maqueta=False,
        items='temas', ranuras={'temas': 6, 'options': 4}, verificado='codigo',
        notas='EXCEPCIÓN: renombrado de claves + Base64 selectivo, sin XOR.'),
}


def ficha(tipo):
    """Datos del tipo, o None si no está catalogado."""
    return CATALOGO.get(tipo)


def tipos_verificados():
    return sorted(k for k, v in CATALOGO.items() if v['verificado'] == 'elpx')


def tipos_autocorregibles():
    return sorted(k for k, v in CATALOGO.items() if v['autocorregible'])
