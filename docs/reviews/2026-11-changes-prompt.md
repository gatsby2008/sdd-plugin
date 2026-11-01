# Prompt — cambios del 2026-11-01

Encargo que reproduce, desde `c7e2311`, los cambios hechos el 2026-11-01: dos
features en `main` (#1, #2) y los 10 commits de la branch `review-improvements`.

````markdown
Trabajás sobre el plugin de Claude Code `sdd` en este repo. Partí de `c7e2311` (docs: point the install snippet at the public repo URL).

Restricciones (no se discuten):
- Ya están decididos y no se discuten: el triage de 4 niveles (trivial / focused / standard / high-risk), los gates deterministas en Python + hooks, los hooks fail-open limitados a `.specwork/`, las OQ bloqueantes y los comandos standalone sin spec.
- No toques el gate de cobertura por nombre de archivo.
- Consultame antes de borrar archivos, renombrar skills o cambiar el formato de un artefacto de `.specwork/`.
- Si un cambio contradice AGENTS.md o docs/concepts.md, detenete y preguntame.
- No uses /sdd:* sobre el propio plugin: modificalo directamente.
- Antes de cada commit tienen que pasar `bash commands/check.sh` (tests unitarios + smoke).
- Un commit por punto, con mensaje semántico y el trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Sin push y sin MR.

## Parte A — en main

### A1. Conformidad con el spec y promoción de reglas (feat, #1)
- Templates de spec (`templates/spec.md`, `templates/spec-frontend.md`): cada Behavior lleva un id estable `**B1**`, `**B2**`, … `/sdd:spec` asigna los ids y nunca renumera.
- `/sdd:implement` etiqueta cada test con los Behaviors que cubre (`// spec: B2`, `# spec: B1, B3`, `@DisplayName("spec: B2 - …")`). Además deja de leer secciones del spec que el template no tiene.
- `lib/conformance.py`: chequeo advisory y sin tokens que corre `/sdd:commit`. Lista los Behaviors que no tienen ningún test etiquetado entre las líneas agregadas en la branch. Tests en `lib/tests/test_conformance.py`.
- `lib/promote.py` + `/sdd:close` Step 6.5 (solo en modo interactivo):
  - Lee del spec solo `## Safe Constraints` y las OQ resueltas.
  - Propone como máximo 4 reglas durables y las presenta en un AskUserQuestion multi-select.
  - Agrega solo las aprobadas a `.claude/rules/*.md` o a `.claude/service-rules.md`, con la marca `_(from spec <slug>, <fecha>)_`.
  - Se niega a escribir (exit 1) si cambiaría alguna línea existente.
  - Se salta si `SDD_NON_INTERACTIVE=1`, si el MR está cerrado o si no hay spec.
  - Tests en `lib/tests/test_promote.py`.
- `commands/check.sh`: suite unitaria + script smoke como quality gate del propio plugin.

### A2. Auditor high-risk advisory (feat, #2)
- En pipelines clasificados high-risk, `/sdd:commit` corre `/sdd:code-review` en modo auditor (solo reporta).
- Después guarda un recibo en `.specwork/_review/<slug>-audit.json` con el SHA-256 del diff staged de la branch y el veredicto (PASS | PASS WITH WARNINGS | FAIL).
- Un diff staged que no cambió no se revisa dos veces.
- FAIL se muestra pero nunca bloquea, y `/sdd:auto` no se pausa.
- Los demás niveles no gastan tokens extra.
- `lib/audit.py` (CLI `required <slug>` / `record <slug> <verdict>`) es fail-open ante cualquier error. Tests en `lib/tests/test_audit.py`.
- Actualizá concepts.md, pipeline.md y code-review/SKILL.md.

## Parte B — branch `review-improvements` (desde ce7215b)

### B1. docs: corregir el conteo de gates, nombres de comandos y referencias cruzadas
- `docs/concepts.md`:
  - "Seven gates": cinco estrictos (OQ, plan-required, plan staleness, test coverage, quality check.sh) que abortan sin escribir, y dos *(advisory)* (spec conformance, high-risk auditor).
  - Fila "Plan required" que mencione `/sdd:spec --tier`.
  - Agregá `path.json`, `validated.json` y `audit.json` a la lista de artefactos.
  - La sección permanente apunta a docs/specs + el registry central (sin docs/adr).
- `docs/sdd-overview.md`:
  - URL pública de instalación.
  - Fuera `--check`, `--prune` y `--uninstall`; en su lugar `/plugin update sdd` y `/plugin uninstall sdd`.
  - Todos los comandos con prefijo `/sdd:doc-*`, y `/sdd:ask`.
  - Links a setup.md, pipeline.md, concepts.md y doc-overview.md.
- `docs/pipeline.md`:
  - Sin referencia a README#the-pipeline.
  - Agregá /sdd:ask y /sdd:doc-ingest.
  - Los gates de implement incluyen plan-required.
  - La entrada de spec documenta `--tier`.
- README.md: agregá `/sdd:mr-review` a los helpers standalone y sdd-overview + doc-overview a la línea de Docs.
- Corregí los punteros en los READMEs de commit, doc-adr-query, doc-catalog-query, implement y start/REFERENCE.

### B2. feat(triage): override explícito del nivel con `/sdd:spec --tier`
- En `lib/triage.py`:
  - `apply_override(classification, tier, reason)`:
    - Valida el tier y exige un reason no vacío; si falta, sale con exit 2 sin escribir.
    - Reescribe ticket_type, complexity, path, `plan_required` (= tier == high-risk), next y why ("override: <reason>").
    - Agrega un bloque `override: {tier, reason, auto_tier, auto_why}` en path.json.
  - `read_override`.
  - El override es sticky: sin `--tier`, el que ya existe se vuelve a aplicar. `--tier auto` lo elimina.
  - `render_summary` muestra "Override: forced X (auto: Y — why)".
- `lib/gates.py plan_required`: si existe `override.tier`, manda en ambas direcciones; si no, se usa `plan_required`.
- Tests en `lib/tests/test_triage.py`:
  - `TestTierOverride`: forzar más bajo, forzar más alto, reason obligatorio, tier desconocido, sticky, auto, forma de path.json sin cambios, summary.
  - `TestPlanGateRespectsOverride`: bajar el nivel levanta el gate, high-risk lo activa, el bloque override gana, exit code de la CLI.
- `skills/spec/SKILL.md`:
  - argument-hint `--tier <trivial|focused|standard|high-risk|auto> "<reason>"`.
  - Step 2.5: un refine que solo trae `--tier` salta al Step 9.
  - Fila nueva en la tabla del Step 4.
  - Step 9 "(draft mode, or any mode with --tier)" con la subsección "Forcing the tier".
  - Ejemplos en el README.

### B3. refactor(implement): mover el detalle bajo demanda a REFERENCE.md (piloto de adelgazamiento)
- Medí palabras y tokens (chars/4) de todos los SKILL.md.
- Bajá `skills/implement/SKILL.md` al menos un 40% (de 3576 a ~1940 palabras) sin cambiar el comportamiento:
  - Conservá todos los steps y los gates.
  - Las Central Rules absorben Requirements.
  - Usá punteros "REF §".
- Mové a `REFERENCE.md` las secciones: Abort messages, Slug examples, Gate rationale, Cache fields, Discovery guidance, Running individual tests, Retry and escalation detail, Simplicity checklist, Related skills.
- Verificá con un diff contra el original que no se perdió ninguna regla. Ojo con estas dos: "Apply contextual judgment only within the matched phase" y "lines added on this branch … token-free conformance check".
- Listá a qué sección fue a parar cada parte.

### B4. docs: check.sh bloquea el push, no el commit
- AGENTS.md (Quality Gates): "`bash commands/check.sh` must pass before pushing (`/sdd:mr`). It is not required before committing — `/sdd:commit` does not run it." … "do not push on failure". El puntero va a docs/setup.md §5.
- Reflejalo en setup.md §5, en los encabezados de `commands/check.sh` y `templates/check.sh.example` ("consumed by /sdd:mr (before push)") y en mr/SKILL.md.

### B5–B6. fix(implement) / fix(handoff): slug desde la branch
- Step 1 de implement y handoff: derivá el slug con `python3 ${CLAUDE_PLUGIN_ROOT}/lib/slug.py` (campo `slug`), nunca a mano. Tiene que coincidir con el prefijo bajo `.specwork/_state/`.
- Los ejemplos van en minúsculas (`feature/IR-45 -> ir-45`).
- Fallback: si no hay coincidencia exacta, aceptá un state file que difiera solo en mayúsculas/minúsculas (pipelines viejos) y nunca otro archivo.
- En handoff, un argumento explícito se usa tal cual.

### B7. feat(start): derivar el slug con lib/slug.py, como resync
- En `lib/start.py` (main): si `args.slug != slug.normalize_slug(args.slug)`, salí con exit 2 sin escribir nada e indicá el slug esperado y el comando `lib/slug.py "<branch>"`. Rechazá en vez de normalizar, porque la ruta de Jira escribe source.md antes de que corra start.py.
- Tests en `lib/tests/test_start.py`:
  - Rechaza PROJ-123, IR-70.1, my_slug y -.
  - Acepta proj-123.
- `skills/start/SKILL.md`: calculá SLUG con slug.py apenas se confirma la branch, antes de escribir source.md. Ejemplos: `feature/PROJ-123 → proj-123`, `feature/IR-70.1 → ir-70-1`.
- Pasá a minúsculas los ejemplos de start/REFERENCE, state, whatnext y plan/README.

### B8. docs(reviews): trackear las notas de review y agregar las propuestas 2026-11
- Sacá `docs/reviews/` del .gitignore. Si hace falta, ajustá `test_self_contained.py`.
- Creá `docs/reviews/2026-11-improvements.md` con opciones, recomendación, trade-off y esfuerzo para:
  - (4) separar en 3 plugins;
  - (5) specs que sobrevivan a la feature (vs OpenSpec);
  - (6) review en dos etapas.

### B9. docs(doc-overview): ejemplo del registry en minúsculas
- Usá `proj-17499-spec.md`. Los ADR quedan en mayúsculas porque se basan en tickets.

### B10. docs(reviews): anexo a la propuesta 4
- Agregá "Anexo — Repensar la familia de docs antes de separarla":
  - Los 4 skills `*-query` (~4250 palabras) quedan reemplazados por /sdd:ask. Antes hay que mover a ask el índice topic/queue de catalog-query y la detección del servicio objetivo.
  - doc-spec es trivial.
  - Forma objetivo: ~6 skills (catalog, adr, investigation, spec, ask, ingest).
- Plan en 3 pasos:
  1. Consolidar en ask (M; no rompe nada).
  2. Borrar los query skills dejando stubs (S; requiere OK).
  3. Separarlo en su propio plugin, con el formato del registry como contrato (M; implica renombrar).
- Recomendación: "consolidar y separar el registro, en ese orden".

## Entrega
- Para cada punto: un commit, con check.sh en verde.
- Informe final:
  - palabras y tokens de los SKILL.md antes y después (total ~52 447 → ~51 248 palabras; implement 3576 → 1939);
  - el destino de cada sección movida;
  - pendientes:
    - ADR warnings en state/SKILL.md que apuntan a docs/adr/;
    - MIGRATION.md dice "35 flat skills";
    - slugs legacy con puntos o guiones bajos requieren /sdd:resync;
    - el bloque override es un agregado al schema de path.json.
````
