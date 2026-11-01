# Propuestas de mejora — noviembre 2026

Propuestas 4, 5 y 6 de la revisión del plugin. Solo análisis: ninguna toca código.
Rama de trabajo: `review-improvements` (los puntos 1–3 ya están aplicados allí).

Esfuerzo: **S** ≤ 1 día · **M** 2–4 días · **L** ≥ 1 semana (incluye tests y docs).

---

## 4. Separar el plugin en tres dentro del mismo marketplace

### Inventario actual (34 skills, 4 agentes)

| Grupo | Skills / agentes | Peso SKILL.md |
|---|---|---|
| Pipeline | start, spec, plan, implement, commit, mr, close, auto, state, whatnext, handoff, pause, restore, resync, undo, test-design, test-impl, code-review, mr-review, mr-address (20) | ~29 600 palabras |
| Registro de documentación | doc-catalog(-query), doc-adr(-query), doc-spec(-query), doc-investigation(-query), ask, doc-ingest (10) | ~14 500 palabras |
| Packs Java | jpa-patterns, concurrency-review, api-contract-review, logging-patterns (4) | ~7 100 palabras |
| Agentes | `sdd:java:{quality,security}-reviewer`, `sdd:ui:{quality,a11y}-reviewer` | ~7 200 tokens de cuerpo |

Lo que cuesta en **cada sesión** (aunque no se invoque nada) son las descripciones:
~2 300 tokens las de skills y ~1 800 las de agentes (las de los agentes llevan
ejemplos completos en el frontmatter). Separar plugins ahorra eso solo a quien no
instala la parte; el cuerpo de los SKILL.md ya se carga bajo demanda.

### Dependencias cruzadas

| De → a | Tipo | Qué pasa si falta la otra parte |
|---|---|---|
| `/sdd:commit` → `/sdd:code-review` (auditor high-risk, paso 3.6) | invocación | **Ambos quedan en el pipeline** — no cruza |
| `/sdd:code-review`, `/sdd:mr-review` → agentes `sdd:java:*`, `sdd:ui:*` | invocación (Task) | Sin agentes no hay review; es el acoplamiento más fuerte |
| `/sdd:code-review`, `/sdd:mr-review` → packs Java (tabla de "deeper review") | sugerencia en texto | Sugeriría comandos inexistentes |
| `/sdd:mr` → `lib/spec-publish.sh` → `spec-registry/` | escritura | El registro es un directorio; funciona sin el plugin de docs |
| `/sdd:mr` → hint `/sdd:doc-adr open-questions` | sugerencia | Sugeriría un comando inexistente |
| `/sdd:whatnext` → lista todos los `/sdd:doc-*` y `/sdd:ask` | sugerencia | Ídem |
| `/sdd:doc-spec`, `/sdd:doc-spec-query` → `/sdd:mr`, `/sdd:spec` | texto | Solo documentación |
| `lib/service-name.sh` | compartido por mr y doc-* | Hay que duplicarlo o publicarlo en ambos |
| `api-contract-review`, `jpa-patterns`, `logging-patterns` → `sdd:java:security-reviewer` | texto | Remite a un agente de otro plugin |

### El costo oculto: el nombre del plugin es el prefijo

Claude Code namespacea por nombre de plugin. Si el registro va a un plugin
`sdd-docs`, `/sdd:doc-adr` pasa a ser `/sdd-docs:doc-adr`, y los agentes pasan a
`sdd-java:…`. Es un **renombre de comandos visible**: rompe memoria muscular,
docs, la referencia en `/sdd:mr` y, en el registro compartido, cualquier nota que
cite el comando. Según AGENTS/las instrucciones de esta revisión, renombrar skills
requiere decisión explícita.

### Opciones

**A. Tres plugins: `sdd` (pipeline + code-review + agentes), `sdd-docs` (10 skills), `sdd-java` (4 packs).**
- Los agentes quedan en `sdd` porque `/sdd:code-review` los necesita siempre; así
  el auditor de `/sdd:commit` sigue autocontenido.
- Las sugerencias cruzadas (`/sdd:mr` → doc-adr, code-review → packs, whatnext → doc-*)
  pasan a ser condicionales: el skill comprueba si el comando existe (o el
  directorio del plugin hermano) antes de sugerirlo.
- `service-name.sh` se duplica en `sdd-docs` con un test que verifique que ambas
  copias son idénticas.
- Trade-off: comandos de docs y packs cambian de prefijo; dos plugins más que
  versionar. Ganancia: quien solo quiere pipeline no carga ~1 400 tokens de
  descripciones de docs+packs por sesión.

**B. Dos plugins: `sdd` (pipeline + agentes + packs Java) y `sdd-docs`.**
- Los packs Java son pequeños (4 skills, ~600 tokens de descripción) y están
  ligados a code-review; separarlos aporta poco.
- Un solo renombre (los doc-*), y el registro es la parte con identidad propia
  (se usa en repos ajenos, sin pipeline).

**C. No separar; adelgazar.** Aplicar el patrón del piloto (SKILL.md → REFERENCE.md)
a los 8 skills > 2 000 palabras y recortar las descripciones de los agentes
(mover los `<example>` al cuerpo). Sin renombres ni migración.

### Recomendación

**C ahora, B después si el registro gana usuarios propios.** El problema que motiva
la separación es el peso, y el peso por sesión está en las descripciones, no en
cuántos plugins hay; C lo ataca sin romper nombres. Si más adelante el registro se
usa sin pipeline (otros equipos), B es la separación con mejor relación
beneficio/ruptura: un solo renombre y ningún acoplamiento de invocación
(solo sugerencias y un script).

### Migración (si se elige A o B)

1. Publicar `sdd-docs` (y `sdd-java`) en el marketplace `gatsby` **sin** quitar
   todavía los skills de `sdd`.
2. Versión puente de `sdd`: los skills movidos quedan como stubs de 5 líneas
   ("se movió a `/sdd-docs:doc-adr`; `/plugin install sdd-docs@gatsby`") — sin
   lógica, para que el nombre viejo no falle en silencio.
3. El registro (`$CLAUDE_DOC_HOME`) no cambia de formato ni de ruta: no hay datos que migrar.
4. Siguiente versión: borrar los stubs.
5. Usuario: `/plugin marketplace update gatsby` → `/plugin install sdd-docs@gatsby`
   → `/plugin update sdd`. Documentarlo en `MIGRATION.md`.

### Esfuerzo
A: **L** · B: **M** · C: **M** (8 skills × medio día, mecánico, mismo método que el piloto).

### Anexo — Repensar la familia de docs antes de separarla

Revisión posterior de la recomendación. Mover los 10 skills de docs tal como
están a otro plugin cambia el prefijo de 10 comandos y conserva su redundancia.
El renombre debería ocurrir **una sola vez, con la forma final**.

**Por qué el registro merece un plugin propio**

- Tiene identidad propia: se usa en cualquier repo (incluso ajeno, sin pipeline),
  se comparte en equipo vía `$CLAUDE_DOC_HOME` y su ciclo de vida no es el de una
  feature.
- El acoplamiento con el pipeline es débil: ningún skill del pipeline *invoca* a un
  `doc-*`. Los une una escritura en disco (`/sdd:mr` → `lib/spec-publish.sh` →
  `spec-registry/`), dos sugerencias en texto (`/sdd:mr` → `/sdd:doc-adr`,
  `/sdd:whatnext`) y `lib/service-name.sh`.
- Esa unión se resuelve tratando el **formato del registro como contrato**
  documentado (ruta, nombre de archivo, clave de servicio), que ambos plugins
  respetan sin depender uno del otro.

**Redundancia actual**

| Skill | Palabras | Situación |
|---|---:|---|
| `doc-catalog-query` | 1 024 | `/sdd:ask` declara que lo reemplaza ("Supersedes the per-registry doc-*-query commands") y ya tiene `type:catalog`. Capacidad propia: índice de topics/colas (Step 2.5) para "¿quién consume X?" |
| `doc-adr-query` | 971 | Reemplazado por `ask type:adr`. Capacidad propia: detección del servicio objetivo |
| `doc-spec-query` | 1 078 | Reemplazado por `ask type:spec`. Ídem |
| `doc-investigation-query` | 1 174 | Reemplazado por `ask type:investigation`. Ídem |
| `doc-spec` | 1 112 | Solo copia un archivo al registro o lo lista; candidato a modo de otro comando |

Los cuatro `*-query` suman ~4 250 palabras y cuatro descripciones que se cargan
en cada sesión, para una función que `ask` ya cubre. Antes de quitarlos, sus
capacidades propias deben pasar a `ask` (un REFERENCE.md por tipo, con el método
del piloto de `implement`).

**Forma propuesta: ~6 skills en lugar de 10.** `catalog`, `adr`,
`investigation`, `spec`, `ask`, `ingest`. Con un prefijo de plugin propio el
`doc-` del nombre sobra: `/<plugin>:adr` en vez de `/sdd:doc-adr`. El nombre del
plugin queda por decidir.

**Plan en tres pasos**

| Paso | Qué | Rompe algo | Esfuerzo |
|---|---|---|---|
| 1. Consolidar dentro de `sdd` | Llevar a `ask` el índice de topics/colas y la detección de servicio objetivo; comparar respuestas de `ask` vs cada `*-query` con preguntas reales | No | **M** |
| 2. Quitar los cuatro `*-query` | Stubs de una versión que redirigen a `/sdd:ask type:…` | Borra skills (requiere OK) | **S** |
| 3. Separar el registro | Mover los ~6 skills al plugin nuevo; documentar el contrato del registro; sugerencias condicionales en `/sdd:mr` y `/sdd:whatnext`; stubs en `sdd` que indican dónde se movió cada comando | Renombra comandos | **M** |

**Riesgos**

- *Renombre visible* (`/sdd:doc-adr` → `/<plugin>:adr`): memoria muscular, docs
  y notas del registro que citen comandos. Se mitiga con los stubs del paso 3.
- *Calidad de `ask`*: si una pregunta de catálogo responde peor que con
  `doc-catalog-query`, quitarlo es una regresión. El paso 1 debe demostrar
  paridad antes del paso 2.
- *`service-name.sh` duplicado*: si las dos copias derivan claves distintas, los
  specs del pipeline y los ADR del mismo servicio caen en carpetas distintas del
  registro. Requiere un test de paridad entre ambas copias.

**Recomendación revisada.** Reemplaza a "C ahora, B después": **consolidar y
separar el registro, en ese orden.** El paso 1 se puede hacer ya sin romper nada;
los pasos 2 y 3 borran o renombran comandos y necesitan decisión explícita. Las
mejoras de C (adelgazar SKILL.md grandes y las descripciones de los agentes)
siguen valiendo para el pipeline.

---

## 5. Specs que sobreviven a la feature

### Situación

- `.specwork/` se borra en `/sdd:close`. Sobrevive `docs/specs/<slug>-spec.md` si
  `/sdd:mr` lo publicó (lo hace siempre que hay pipeline y se usa `/sdd:mr`), y la
  copia en `spec-registry/`.
- `/sdd:close` paso 6.5 ya promueve reglas durables a `.claude/rules/` /
  `service-rules.md`.
- **Hallazgo adicional:** el tag `spec: B3` no nombra el spec. Los ids `B<n>` son
  por spec, así que dos features distintas tienen cada una su `B3`; dentro del
  branch el conformance check acierta (mira solo líneas agregadas en el branch),
  pero meses después `spec: B3` es ambiguo aunque el archivo exista.

### Opciones

**A. Modelo OpenSpec: specs vivos por capacidad + deltas.**
Cada cambio escribe un delta (ADDED/MODIFIED/REMOVED Behaviors) contra
`docs/specs/<capability>/spec.md`; al archivar, el delta se integra.
- Pro: un spec actual por capacidad; los tags apuntan a algo que se mantiene.
- Contra: hay que definir y mantener una taxonomía de capacidades por servicio;
  la integración del delta es un merge semántico (LLM) con conflictos entre
  features paralelas; cambia el formato de `spec.md` (secciones delta) y la
  semántica de `/sdd:close` — rompería pipelines en curso. Duplica parcialmente lo
  que hoy hacen las reglas promovidas.

**B. Explícito: el spec es de un cambio; lo durable son las reglas promovidas y el archivo.**
- Documentar en `concepts.md` que `spec.md` es un contrato de cambio, no
  documentación viva; los invariantes durables viven en las reglas (`/sdd:close` 6.5)
  y el histórico en `docs/specs/` + registro.
- Tags con slug: `spec: <slug>#B3` (aceptando también `spec: B3` dentro del branch,
  para no romper specs en curso). `lib/conformance.py` aceptaría ambas formas.
- `/sdd:close` paso 5: si **no** existe `docs/specs/<slug>-spec.md`, advertir
  (hoy calla) — el tag quedará colgando.

**C. B + spec por capacidad opcional, solo de lectura.**
Un índice generado (`/sdd:doc-spec` o `/sdd:ask`) que agrupe los specs archivados
por clase/endpoint tocado, sin merge. Da "qué features tocaron X" sin el costo de
mantener un spec vivo.

### Recomendación

**B ya; C cuando el registro tenga volumen.** El pipeline está construido sobre
"un spec, un cambio" (staleness por fingerprint, OQ append-only, ids estables por
spec), y la pieza que OpenSpec resuelve con specs vivos —conocimiento durable—
ya la cubren las reglas promovidas, que además son lo que el modelo lee en cada
sesión. A cambiaría el formato de un artefacto de `.specwork/` y añadiría un merge
LLM en cada archivo: mucho costo para un beneficio que se solapa.

### Trade-off
B acepta que no hay "el spec actual de la capacidad X"; quien necesite esa vista
la arma con `/sdd:ask` sobre el archivo. A da esa vista a cambio de una taxonomía
y merges permanentes.

### Esfuerzo
A: **L** · B: **S** (doc + regex de conformance + un aviso en close + tests) · C: **M**.

---

## 6. Review en dos etapas por tarea (spec primero, calidad después)

### Situación

- **Conformance** (`lib/conformance.py`, en `/sdd:commit`): grep de tags
  `spec: B<n>`. Gratis, pero solo prueba que *existe* un test etiquetado, no que el
  diff cumpla el Behavior.
- **Auditor high-risk** (`/sdd:commit` 3.6): corre `/sdd:code-review` (calidad +
  seguridad) una vez por diff distinto, solo en tier high-risk; advisory.
- No hay ninguna revisión que lea el spec contra el diff.

### Dónde encajaría

| Lugar | Pro | Contra |
|---|---|---|
| `/sdd:implement` (por paso) | Detecta desvíos antes de acumular pasos | Se paga N veces por feature (N = pasos); en `batch` repite contexto |
| `/sdd:commit` (por diff) | Una vez por diff; reutiliza el fingerprint y el recibo del auditor (`audit.json`); el diff ya está completo | Detecta tarde si hubo muchos pasos |
| `/sdd:code-review` | Reutilizable standalone | Sin spec en modo standalone la etapa 1 no aplica; mezcla responsabilidades |

### Costo estimado (tokens por ejecución, aproximado)

- Etapa 1 — revisor de conformidad (subagente, sin herramientas de escritura):
  prompt ~1 000 + spec ~1 500–3 000 + diff 2 000–20 000 + salida ~800
  → **~5 000–25 000**.
- Etapa 2 — ya existe (`/sdd:code-review`): 2 agentes en paralelo, cada uno
  ~1 800–2 000 de prompt + diff → **~8 000–45 000**.
- Por paso en `/sdd:implement`: multiplicar la etapa 1 por N (típico 3–5) →
  15 000–125 000 por feature. En `/sdd:commit`: una sola vez.

### Opciones

**A. Etapa 1 en `/sdd:implement`, cada paso, todos los tiers.** Máxima detección, máximo costo; contradice el objetivo de liviandad.

**B. Etapa 1 en `/sdd:commit` como parte del auditor, solo high-risk; etapa 2 solo si la 1 no falla.**
- El auditor pasa a ser: (1) conformidad spec↔diff por Behavior `B<n>`
  (cumple / no cumple / no verificable, con línea del diff), (2) `/sdd:code-review`.
- Si la etapa 1 marca un Behavior incumplido, se informa y se **salta** la etapa 2
  (revisar la calidad de un diff que no cumple el spec es gasto perdido).
- Mismo recibo con fingerprint: no se repite para un diff ya auditado.
- Sigue siendo advisory — hacerlo bloqueante contradiría "never blocks" del auditor
  en `concepts.md` y requiere decisión explícita.

**C. B + opt-in para otros tiers** (`/sdd:commit --spec-review`, o flag en `state.json`).

### Recomendación

**B, con C como flag opcional.** La etapa 1 aporta lo que hoy falta (el grep de
conformance no lee el diff), y ponerla en `/sdd:commit` cuesta una ejecución por
diff en vez de N. Limitarla a high-risk mantiene el principio "los otros tiers no
pagan tokens extra". Combina bien con la propuesta 5B: con tags `slug#B<n>` el
revisor puede señalar además tests que dicen cubrir un Behavior que el diff no toca.

### Trade-off
Detección más tardía que por paso (A); a cambio, costo acotado y sin tocar el
flujo de `implement` recién adelgazado.

### Esfuerzo
A: **M** · B: **M** (un agente nuevo + cambios en `/sdd:commit` y `lib/audit.py` para el recibo de dos etapas + tests) · C: **S** sobre B.
