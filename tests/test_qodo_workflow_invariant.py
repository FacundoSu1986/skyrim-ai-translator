"""Ancla de invariantes de seguridad y gobernanza de workflows de Qodo / PR-Agent.

Por qué existe:
Garantiza que todas las invocaciones de Codium-ai/pr-agent dentro de
.github/workflows/*.yml estén explícitamente inventariadas y congeladas
en:
1. Recetas de routing OpenRouter y tokens personalizados.
2. Pinning exacto de Action por commit SHA.
3. Bloqueo fail-closed de repositorios privados.
4. Restricción de PRs internos y bloqueo de forks (auto-review y comment-command).
5. Autorización estricta de comentarios (OWNER/MEMBER/COLLABORATOR y exclusión de bots).
6. Scope mínimo de secrets (OPENROUTER_API_KEY restringida exclusivamente al step PR-Agent, sin secretos en if).
7. Correspondencia exacta con la allowlist de modelos de la política de datos.

Cualquier invocación no inventariada, modificación de gates o exposición
indebida de credenciales romperá este test de forma determinista.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = RAIZ / ".github" / "workflows"
POLICY_FILE = RAIZ / ".github" / "AI_REVIEW_DATA_POLICY.md"

PINNED_ACTION_REF_ESPERADA = "4ebd5c5333c6ef21509e7304d27969eb825e6f22"
CANONICAL_ACTION_REPO = "Codium-ai/pr-agent"

CLAVES_ROUTING = (
    "OPENROUTER_API_KEY",
    "OPENROUTER__KEY",
    "CONFIG.MODEL",
    "CONFIG.CUSTOM_MODEL_MAX_TOKENS",
    "CONFIG.FALLBACK_MODELS",
    "LITELLM.DROP_PARAMS",
)

RECETA_ADVERSARIAL: dict[str, str] = {
    "OPENROUTER_API_KEY": "${{ secrets.OPENROUTER_API_KEY }}",
    "OPENROUTER__KEY": "${{ secrets.OPENROUTER_API_KEY }}",
    "CONFIG.MODEL": "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
    "CONFIG.CUSTOM_MODEL_MAX_TOKENS": "200000",
    "CONFIG.FALLBACK_MODELS": '["openrouter/minimax/minimax-m3:free", "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"]',
    "LITELLM.DROP_PARAMS": "true",
}

RECETAS_ESPERADAS: dict[tuple[str, str], dict[str, str]] = {
    ("qodo-merge-adversarial.yml", "auto-review"): RECETA_ADVERSARIAL,
    ("qodo-merge-adversarial.yml", "comment-command"): RECETA_ADVERSARIAL,
}


def parsear_todos_los_workflows(workflows_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """Lee y parsea todos los archivos YAML en el directorio de workflows."""
    directorio = workflows_dir or WORKFLOWS_DIR
    workflows: dict[str, dict[str, Any]] = {}
    archivos = sorted(list(directorio.glob("*.yml")) + list(directorio.glob("*.yaml")))
    for archivo in archivos:
        contenido = archivo.read_text(encoding="utf-8")
        data = yaml.safe_load(contenido)
        if isinstance(data, dict):
            workflows[archivo.name] = data
    return workflows


def descubrir_invocaciones_qodo(
    workflows_dir: Path | None = None,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Descubre dinámicamente todas las invocaciones de Codium-ai/pr-agent en .github/workflows/*.

    Normaliza el nombre de la Action de forma case-insensitive (owner/repo en GitHub no distinguen mayúsculas).
    Retorna un diccionario mapeando (workflow_filename, job_id) -> lista de steps encontrados con sus metadatos.
    """
    workflows = parsear_todos_los_workflows(workflows_dir)
    invocaciones: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for archivo_nombre, data in workflows.items():
        jobs = data.get("jobs", {})
        if not isinstance(jobs, dict):
            continue

        for job_id, job_data in jobs.items():
            if not isinstance(job_data, dict):
                continue
            steps = job_data.get("steps", [])
            if not isinstance(steps, list):
                continue

            job_if = str(job_data.get("if", "")).strip()

            for step in steps:
                if not isinstance(step, dict):
                    continue
                uses = str(step.get("uses", "")).strip()
                action_repo, _, action_ref = uses.partition("@")
                if action_repo.strip().casefold() == CANONICAL_ACTION_REPO.casefold():
                    clave = (archivo_nombre, job_id)
                    step_env = step.get("env", {}) if isinstance(step.get("env"), dict) else {}
                    invocaciones.setdefault(clave, []).append(
                        {
                            "uses": uses,
                            "action_repo": action_repo.strip(),
                            "action_ref": action_ref.strip(),
                            "job_if": job_if,
                            "env": step_env,
                            "step_data": step,
                        }
                    )

    return invocaciones


def obtener_modelos_aprobados_politica(policy_path: Path | None = None) -> set[str]:
    """Extrae el conjunto de modelos aprobados delimitados en AI_REVIEW_DATA_POLICY.md."""
    archivo = policy_path or POLICY_FILE
    contenido = archivo.read_text(encoding="utf-8")

    patron_seccion = r"<!--\s*approved-models:start\s*-->(.*?)<!--\s*approved-models:end\s*-->"
    coincidencia = re.search(patron_seccion, contenido, re.DOTALL)
    assert coincidencia is not None, (
        f"No se encontró el bloque delimitado <!-- approved-models:start --> ... "
        f"<!-- approved-models:end --> en {archivo.name}"
    )

    bloque = coincidencia.group(1)
    modelos = set(re.findall(r"`(openrouter/[^`]+)`", bloque))
    assert len(modelos) > 0, f"No se extrajo ningún modelo aprobado del bloque en {archivo.name}"
    return modelos


def test_conjunto_de_invocaciones_qodo_es_exacto() -> None:
    """Verifica que el conjunto de jobs coincida exactamente y que cada uno tenga exactamente una invocación."""
    descubiertas = descubrir_invocaciones_qodo()
    conjunto_descubierto = set(descubiertas.keys())
    conjunto_esperado = set(RECETAS_ESPERADAS.keys())

    assert conjunto_descubierto == conjunto_esperado, (
        f"Invocaciones de Qodo divergentes. "
        f"Faltantes: {conjunto_esperado - conjunto_descubierto}, "
        f"Inesperadas: {conjunto_descubierto - conjunto_esperado}"
    )

    for (archivo, job_id), steps in descubiertas.items():
        assert len(steps) == 1, (
            f"El job {archivo} / {job_id} contiene {len(steps)} invocaciones de PR-Agent; se esperaba exactamente 1."
        )


def test_gate_repositorio_publico_en_todos_los_jobs() -> None:
    """Verifica que cada job que invoque Qodo tenga el gate explícito fail-closed github.event.repository.private == false."""
    descubiertas = descubrir_invocaciones_qodo()

    for (archivo, job_id), steps in descubiertas.items():
        for idx, step_metadata in enumerate(steps):
            job_if = step_metadata.get("job_if", "")
            assert "github.event.repository.private == false" in job_if, (
                f"El job {archivo} / {job_id} (step {idx}) no incluye la condición fail-closed "
                f"'github.event.repository.private == false' en su cláusula if.\n"
                f"Cláusula if actual: {job_if!r}"
            )


def test_pinning_de_accion_qodo_es_exacto() -> None:
    """Verifica que cada invocación use exactamente el SHA fijado y el repo canónico de Codium-ai/pr-agent."""
    descubiertas = descubrir_invocaciones_qodo()
    for (archivo, job_id), steps in descubiertas.items():
        for idx, step_metadata in enumerate(steps):
            action_ref = step_metadata.get("action_ref", "")
            action_repo = step_metadata.get("action_repo", "")
            assert action_repo.casefold() == CANONICAL_ACTION_REPO.casefold(), (
                f"Repo inesperado en {archivo} / {job_id} (step {idx}): {action_repo!r}"
            )
            assert action_ref == PINNED_ACTION_REF_ESPERADA, (
                f"Pinning inesperado en {archivo} / {job_id} (step {idx}): {action_ref!r} != {PINNED_ACTION_REF_ESPERADA!r}"
            )


def test_restricciones_de_seguridad_y_fork_gate() -> None:
    """Verifica los gates de fork en auto-review y autorización estricta de actores en comment-command."""
    workflows = parsear_todos_los_workflows()
    assert "qodo-merge-adversarial.yml" in workflows, "Falta qodo-merge-adversarial.yml"
    jobs = workflows["qodo-merge-adversarial.yml"].get("jobs", {})

    # 1. auto-review: bloqueo estricto de forks
    auto_review = jobs.get("auto-review", {})
    auto_if = str(auto_review.get("if", ""))
    assert "github.event.pull_request.head.repo.full_name == github.repository" in auto_if, (
        f"auto-review no contiene la validación estricta de PR interno contra forks: {auto_if!r}"
    )

    # 2. comment-command: autorización y exclusión de bots
    comment_cmd = jobs.get("comment-command", {})
    cmd_if = str(comment_cmd.get("if", ""))
    assert "github.event.comment.user.type != 'Bot'" in cmd_if, (
        f"comment-command no excluye bots en su cláusula if: {cmd_if!r}"
    )
    for role in ("OWNER", "MEMBER", "COLLABORATOR"):
        assert f"github.event.comment.author_association == '{role}'" in cmd_if, (
            f"comment-command no restringe ejecución a '{role}': {cmd_if!r}"
        )

    # 3. comment-command: fork gate step
    cmd_steps = comment_cmd.get("steps", [])
    fork_check_encontrado = False
    for step in cmd_steps:
        run_script = str(step.get("run", ""))
        if "headRepositoryOwner" in run_script and "HEAD_REPO" in run_script:
            fork_check_encontrado = True
            break
    assert fork_check_encontrado, "comment-command no contiene el paso de verificación de forks antes de PR-Agent"


def test_scope_minimo_de_secrets_openrouter() -> None:
    """Verifica que OPENROUTER_API_KEY y OPENROUTER__KEY no existan a nivel job, no se usen en if, y solo estén en el step PR-Agent."""
    workflows = parsear_todos_los_workflows()

    for archivo_nombre, data in workflows.items():
        jobs = data.get("jobs", {})
        for job_id, job_data in jobs.items():
            # Aserción 1: Ningún job define variables directas de OpenRouter a nivel job
            job_env = job_data.get("env", {})
            if isinstance(job_env, dict):
                for secret_key in ("OPENROUTER_API_KEY", "OPENROUTER__KEY"):
                    assert secret_key not in job_env, (
                        f"Violación de least-privilege: '{secret_key}' expuesta a nivel de job en {archivo_nombre} / {job_id}"
                    )

            # Aserción 2: Ningún if de job ni de step usa el contexto secrets directamente (invalido en GitHub Actions runner)
            job_if = str(job_data.get("if", ""))
            assert "secrets." not in job_if, (
                f"Contexto 'secrets' no permitido en job.if en {archivo_nombre} / {job_id}: {job_if!r}"
            )

            steps = job_data.get("steps", [])
            for idx, step in enumerate(steps):
                step_if = str(step.get("if", ""))
                assert "secrets." not in step_if, (
                    f"Contexto 'secrets' no permitido en step.if (step {idx}) en {archivo_nombre} / {job_id}: {step_if!r}"
                )

                # Aserción 3: Los steps que NO invocan PR-Agent no reciben variables de OpenRouter
                uses = str(step.get("uses", "")).strip()
                action_repo, _, _ = uses.partition("@")
                step_env = step.get("env", {})
                if not isinstance(step_env, dict):
                    continue

                es_step_pr_agent = action_repo.strip().casefold() == CANONICAL_ACTION_REPO.casefold()
                if not es_step_pr_agent:
                    for secret_key in ("OPENROUTER_API_KEY", "OPENROUTER__KEY"):
                        assert secret_key not in step_env, (
                            f"Violación de least-privilege: '{secret_key}' expuesta en step no-PR-Agent "
                            f"(step {idx}: {step.get('name', '')!r}) en {archivo_nombre} / {job_id}"
                        )


def test_receta_routing_openrouter_por_invocacion() -> None:
    """Verifica que cada invocación congele exactamente su receta de routing OpenRouter a nivel de step."""
    descubiertas = descubrir_invocaciones_qodo()

    for (archivo, job_id), receta_esperada in RECETAS_ESPERADAS.items():
        assert (archivo, job_id) in descubiertas, f"Falta invocación {archivo} / {job_id}"
        steps = descubiertas[(archivo, job_id)]
        assert len(steps) == 1, f"Múltiples steps en {archivo} / {job_id}"
        env = steps[0]["env"]

        routing_actual = {k: str(env.get(k, "")) for k in CLAVES_ROUTING}

        assert routing_actual == receta_esperada, (
            f"Receta de routing divergente en {archivo} / {job_id}.\n"
            f"Actual:   {routing_actual}\n"
            f"Esperada: {receta_esperada}"
        )


def test_modelos_configurados_coinciden_con_allowlist_de_politica() -> None:
    """Verifica que el conjunto de todos los modelos (primarios y fallbacks) coincida exactamente con la allowlist de la política."""
    descubiertas = descubrir_invocaciones_qodo()
    modelos_aprobados = obtener_modelos_aprobados_politica()

    modelos_configurados: set[str] = set()
    for (archivo, job_id), steps in descubiertas.items():
        for idx, step_metadata in enumerate(steps):
            env = step_metadata.get("env", {})
            modelo_primario = env.get("CONFIG.MODEL")
            if modelo_primario:
                modelos_configurados.add(str(modelo_primario))

            fallbacks_raw = env.get("CONFIG.FALLBACK_MODELS")
            if fallbacks_raw:
                try:
                    fallbacks = json.loads(str(fallbacks_raw))
                    if isinstance(fallbacks, list):
                        for fb in fallbacks:
                            modelos_configurados.add(str(fb))
                except Exception as exc:
                    raise AssertionError(
                        f"Error al parsear CONFIG.FALLBACK_MODELS en {archivo} / {job_id} (step {idx}): {fallbacks_raw}"
                    ) from exc

    assert modelos_configurados == modelos_aprobados, (
        f"Discrepancia entre modelos configurados en workflows y allowlist en AI_REVIEW_DATA_POLICY.md.\n"
        f"No aprobados en política pero configurados en workflows: {modelos_configurados - modelos_aprobados}\n"
        f"Aprobados en política pero no configurados en workflows:  {modelos_aprobados - modelos_configurados}"
    )
