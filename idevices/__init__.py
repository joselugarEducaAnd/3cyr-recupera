# -*- coding: utf-8 -*-
"""Generación y parcheo de iDevices interactivos de eXeLearning 4.

Piezas:
  codec.py     el cifrado del motor de juegos (XOR 0x92 + escape())
  catalogo.py  cómo guarda su configuración cada uno de los 51 iDevices base
  elpx_io.py   lectura, parcheo quirúrgico y biblioteca de plantillas
  builders.py  de la definición en YAML a la configuración de cada tipo
  validar.py   comprobación estructural Y de valores, sin abrir eXeLearning

Regla que gobierna todo esto: **el .elpx en el que Pepe ha trabajado es la fuente de
verdad y no se regenera**. Se parchea in situ, y se valida siempre antes de entregar.
"""
from . import builders, catalogo, codec, elpx_io, validar  # noqa: F401

__all__ = ['codec', 'catalogo', 'elpx_io', 'builders', 'validar']
