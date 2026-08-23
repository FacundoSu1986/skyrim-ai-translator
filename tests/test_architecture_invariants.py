"""Anclas estructurales para invariantes críticas del repositorio.

Estas pruebas no verifican solo un ejemplo: enumeran superficies completas para que
un nuevo camino de egress, una segunda fuente de glosario o una mutación accidental
del pipeline rompan CI hasta que se tome una decisión explícita.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src"
ENTRYPOINTS = [RAIZ / "api.py", RAIZ / "main.py"]

for entrypoint in ENTRYPOINTS:
    assert entrypoint.exists(), (
        f"Entrypoint productivo esperado no encontrado: {entrypoint}. "
        "Verifica cambios en el layout del proyecto antes de evaluar invariantes."
    )

ARCHIVOS_PRODUCTIVOS = [*ENTRYPOINTS, *sorted(SRC.rglob("*.py"))]

EGRESS_URLOPEN_ESPERADO = {
    "src/free_translator.py": 1,
    "src/translator.py": 1,
}


def _leer_ast(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _nombre_punteado(nodo: ast.AST) -> str | None:
    if isinstance(nodo, ast.Name):
        return nodo.id
    if isinstance(nodo, ast.Attribute):
        base = _nombre_punteado(nodo.value)
        return f"{base}.{nodo.attr}" if base else None
    return None


def _aliases_urlopen(arbol: ast.AST) -> tuple[dict[str, str], set[str]]:
    """Devuelve aliases de módulo y nombres directos que resuelven a urlopen."""
    modulos: dict[str, str] = {}
    directos: set[str] = set()

    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if alias.name == "urllib.request":
                    if alias.asname:
                        modulos[alias.asname] = "urllib.request"
                    else:
                        modulos["urllib"] = "urllib"
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.module == "urllib":
                for alias in nodo.names:
                    if alias.name == "request":
                        modulos[alias.asname or alias.name] = "urllib.request"
            elif nodo.module == "urllib.request":
                for alias in nodo.names:
                    if alias.name == "urlopen":
                        directos.add(alias.asname or alias.name)

    while True:
        nuevos: set[str] = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Assign):
                objetivos, valor = nodo.targets, nodo.value
            elif isinstance(nodo, ast.AnnAssign) and nodo.value is not None:
                objetivos, valor = [nodo.target], nodo.value
            else:
                continue
            if not _es_referencia_urlopen(valor, modulos, directos):
                continue
            nuevos.update(obj.id for obj in objetivos if isinstance(obj, ast.Name))
        if nuevos <= directos:
            break
        directos |= nuevos

    return modulos, directos


def _es_referencia_urlopen(valor: ast.AST, modulos: dict[str, str], directos: set[str]) -> bool:
    if isinstance(valor, ast.Name):
        return valor.id in directos
    nombre = _nombre_punteado(valor)
    if nombre == "urllib.request.urlopen":
        return True
    if not nombre:
        return False
    partes = nombre.split(".")
    base = partes[0]
    if base not in modulos:
        return False
    resuelto = ".".join([modulos[base], *partes[1:]])
    return resuelto == "urllib.request.urlopen"


def _contar_urlopen_en_arbol(arbol: ast.AST) -> int:
    modulos, directos = _aliases_urlopen(arbol)
    return sum(
        1
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call) and _es_referencia_urlopen(nodo.func, modulos, directos)
    )


def _contar_urlopen(fuente: str) -> int:
    return _contar_urlopen_en_arbol(ast.parse(fuente))


def _egress_urlopen_por_modulo() -> dict[str, int]:
    encontrados: Counter[str] = Counter()
    for path in ARCHIVOS_PRODUCTIVOS:
        cantidad = _contar_urlopen_en_arbol(_leer_ast(path))
        if cantidad:
            encontrados[path.relative_to(RAIZ).as_posix()] = cantidad
    return dict(encontrados)


def _definiciones_glosario() -> list[str]:
    encontrados: list[str] = []
    for path in ARCHIVOS_PRODUCTIVOS:
        for nodo in ast.walk(_leer_ast(path)):
            objetivos: list[ast.AST] = []
            if isinstance(nodo, ast.Assign):
                objetivos = list(nodo.targets)
            elif isinstance(nodo, ast.AnnAssign):
                objetivos = [nodo.target]
            if any(isinstance(obj, ast.Name) and obj.id == "SKYRIM_GLOSSARY" for obj in objetivos):
                encontrados.append(path.relative_to(RAIZ).as_posix())
    return sorted(encontrados)


def _aliases_time(arbol: ast.AST) -> tuple[set[str], set[str]]:
    modulos: set[str] = set()
    directos: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if alias.name == "time":
                    modulos.add(alias.asname or alias.name)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module == "time":
            for alias in nodo.names:
                if alias.name == "sleep":
                    directos.add(alias.asname or alias.name)
    return modulos, directos


class _BloqueoAsyncVisitor(ast.NodeVisitor):
    def __init__(self, modulos_time: set[str], sleep_directos: set[str]) -> None:
        self.en_async = False
        self.modulos_time = modulos_time
        self.sleep_directos = sleep_directos
        self.hallazgos: list[int] = []

    def visit_AsyncFunctionDef(self, nodo: ast.AsyncFunctionDef) -> None:
        anterior = self.en_async
        self.en_async = True
        for stmt in nodo.body:
            self.visit(stmt)
        self.en_async = anterior

    def visit_FunctionDef(self, nodo: ast.FunctionDef) -> None:
        if self.en_async:
            return
        self.generic_visit(nodo)

    def visit_Call(self, nodo: ast.Call) -> None:
        if self.en_async:
            nombre = _nombre_punteado(nodo.func)
            es_directo = isinstance(nodo.func, ast.Name) and nodo.func.id in self.sleep_directos
            es_modulo = nombre is not None and nombre.endswith(".sleep") and nombre.split(".")[0] in self.modulos_time
            if es_directo or es_modulo:
                self.hallazgos.append(nodo.lineno)
        self.generic_visit(nodo)


def _time_sleep_en_async() -> dict[str, list[int]]:
    encontrados: dict[str, list[int]] = {}
    for path in ARCHIVOS_PRODUCTIVOS:
        arbol = _leer_ast(path)
        modulos_time, sleep_directos = _aliases_time(arbol)
        visitante = _BloqueoAsyncVisitor(modulos_time, sleep_directos)
        visitante.visit(arbol)
        if visitante.hallazgos:
            encontrados[path.relative_to(RAIZ).as_posix()] = visitante.hallazgos
    return encontrados


def _translate_entries_ast() -> ast.AsyncFunctionDef:
    arbol = _leer_ast(SRC / "translator.py")
    funciones = [nodo for nodo in arbol.body if isinstance(nodo, ast.AsyncFunctionDef) and nodo.name == "translate_entries"]
    assert len(funciones) == 1, "translate_entries debe tener una única definición canónica"
    return funciones[0]


def _mutaciones_directas_de_entry(funcion: ast.AsyncFunctionDef) -> list[int]:
    lineas: list[int] = []
    for nodo in ast.walk(funcion):
        es_asignacion_atributo = (
            isinstance(nodo, ast.Attribute)
            and isinstance(nodo.ctx, ast.Store)
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "entry"
        )
        es_setattr = (
            isinstance(nodo, ast.Call)
            and isinstance(nodo.func, ast.Name)
            and nodo.func.id == "setattr"
            and bool(nodo.args)
            and isinstance(nodo.args[0], ast.Name)
            and nodo.args[0].id == "entry"
        )
        if es_asignacion_atributo or es_setattr:
            lineas.append(nodo.lineno)
    return sorted(set(lineas))


def _usa_replace_para_traduccion(funcion: ast.AsyncFunctionDef) -> bool:
    for nodo in ast.walk(funcion):
        if not isinstance(nodo, ast.Call) or _nombre_punteado(nodo.func) not in {"replace", "dataclasses.replace"}:
            continue
        if not nodo.args or not isinstance(nodo.args[0], ast.Name) or nodo.args[0].id != "entry":
            continue
        if any(keyword.arg == "translated_text" for keyword in nodo.keywords):
            return True
    return False


def test_detector_urlopen_reconoce_aliases_comunes() -> None:
    assert _contar_urlopen("import urllib.request\nurllib.request.urlopen('https://example.test')\n") == 1
    assert _contar_urlopen("import urllib.request as http\nhttp.urlopen('https://example.test')\n") == 1
    assert _contar_urlopen("from urllib import request as req\nreq.urlopen('https://example.test')\n") == 1
    assert _contar_urlopen("from urllib.request import urlopen as abrir\nabrir('https://example.test')\n") == 1
    assert _contar_urlopen("import urllib.request\nabrir = urllib.request.urlopen\nabrir('https://example.test')\n") == 1
    assert _contar_urlopen("import otra\notra.urlopen('x')\n") == 0


def test_detector_time_sleep_reconoce_aliases_comunes() -> None:
    fuentes = (
        "import time\nasync def f():\n    time.sleep(1)\n",
        "import time as reloj\nasync def f():\n    reloj.sleep(1)\n",
        "from time import sleep as pausa\nasync def f():\n    pausa(1)\n",
    )
    for fuente in fuentes:
        arbol = ast.parse(fuente)
        modulos_time, sleep_directos = _aliases_time(arbol)
        visitante = _BloqueoAsyncVisitor(modulos_time, sleep_directos)
        visitante.visit(arbol)
        assert visitante.hallazgos


def test_detector_time_sleep_ignora_casos_permitidos() -> None:
    fuentes = (
        "import time\ndef f():\n    time.sleep(1)\n",
        "import asyncio\nasync def f():\n    await asyncio.sleep(1)\n",
        "import asyncio, time\nasync def f():\n    def _bloqueante():\n        time.sleep(1)\n    await asyncio.to_thread(_bloqueante)\n",
    )
    for fuente in fuentes:
        arbol = ast.parse(fuente)
        modulos_time, sleep_directos = _aliases_time(arbol)
        visitante = _BloqueoAsyncVisitor(modulos_time, sleep_directos)
        visitante.visit(arbol)
        assert visitante.hallazgos == [], fuente


def test_detector_replace_reconoce_ambas_formas() -> None:
    fuentes = (
        "from dataclasses import replace\nasync def f(entry):\n    return replace(entry, translated_text='ok')\n",
        "import dataclasses\nasync def f(entry):\n    return dataclasses.replace(entry, translated_text='ok')\n",
    )
    for fuente in fuentes:
        arbol = ast.parse(fuente)
        funciones = [nodo for nodo in arbol.body if isinstance(nodo, ast.AsyncFunctionDef)]
        assert _usa_replace_para_traduccion(funciones[0]), fuente


def test_egress_http_directo_esta_congelado() -> None:
    assert _egress_urlopen_por_modulo() == EGRESS_URLOPEN_ESPERADO, (
        "Cambió el inventario de egress HTTP directo mediante urllib.request.urlopen. "
        "Un nuevo destino de red debe revisarse explícitamente por privacidad, secretos, "
        "términos del proveedor, timeouts y aislamiento de tests antes de actualizar el ancla."
    )


def test_skyrim_glossary_tiene_un_unico_dueno() -> None:
    assert _definiciones_glosario() == ["src/translator.py"], (
        "SKYRIM_GLOSSARY debe definirse una sola vez en src/translator.py. "
        "Los demás pipelines deben importarlo, no mantener una copia."
    )
    free_ast = _leer_ast(SRC / "free_translator.py")
    assert any(
        isinstance(nodo, ast.ImportFrom)
        and nodo.module == "src.translator"
        and any(alias.name == "SKYRIM_GLOSSARY" for alias in nodo.names)
        for nodo in ast.walk(free_ast)
    ), "free_translator debe consumir el glosario canónico desde src.translator"


def test_no_hay_time_sleep_dentro_de_async_productivo() -> None:
    assert _time_sleep_en_async() == {}, (
        "Se detectó time.sleep() dentro de código async productivo. "
        "Usar asyncio.sleep() o mover I/O bloqueante a asyncio.to_thread()."
    )


def test_translate_entries_no_muta_la_entrada_y_reemplaza_resultado() -> None:
    funcion = _translate_entries_ast()
    assert _mutaciones_directas_de_entry(funcion) == [], (
        "translate_entries no debe mutar atributos de StringEntry in-place; debe producir una nueva instancia."
    )
    assert _usa_replace_para_traduccion(funcion), (
        "translate_entries debe conservar el contrato de transformación mediante dataclasses.replace(entry, translated_text=...)."
    )
