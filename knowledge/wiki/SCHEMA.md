# AudioQual Wiki — Schema

Este archivo define las convenciones del wiki. Es leído por el LLM al inicio de cada sesión de mantenimiento.

## Estructura

```
knowledge/
├── wiki/                      Wiki mantenida por LLM
│   ├── SCHEMA.md              Este archivo (convenciones)
│   ├── index.md               Índice temático
│   ├── log.md                 Cronología del proyecto (append-only)
│   ├── algoritmo/             Detección espectral, STFT, codecs, calibración
│   ├── arquitectura/          Pipeline, GUI, threading, cache, distribución
│   ├── fuentes/               Resúmenes de papers, specs, herramientas externas
│   └── decisiones/            Decisiones clave y su razonamiento (estilo ADR)
├── sources/                   Fuentes crudas inmutables (PDFs, artículos)
├── ALGORITMO.txt              Archivos originales — fuentes internas
├── VERIFICACION.txt
└── ...
```

## Formato de páginas

```markdown
---
title: Nombre descriptivo
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: [archivo1.txt, paper.pdf]
tags: [tag1, tag2]
---

Contenido en markdown.

## Secciones con headers H2

Links a otras páginas: [texto descriptivo](../categoria/pagina.md)
```

- Links: markdown estándar con rutas relativas (`[texto](../ruta/pagina.md)`)
- Tags: lista en frontmatter, sin inventar tags nuevos sin necesidad
- Sources: archivos de `knowledge/` o `sources/` que alimentaron la página

## Tags válidos

| Tag | Uso |
|-----|-----|
| `algoritmo` | Detección de calidad, STFT, cutoff |
| `clasificacion` | Clasificación de calidad, umbrales |
| `brickwall` | Brickwall vs rolloff natural |
| `falsos-positivos` | Casos de falsos positivos |
| `gui` | Interfaz gráfica |
| `threading` | Concurrencia, event loop, macOS |
| `cache` | Sistema de caché |
| `testing` | Tests, verificación |
| `distribucion` | Build, empaquetado, plataformas |
| `rendimiento` | Optimización de velocidad/memoria |
| `codec` | MP3, AAC, FLAC, especificaciones |
| `herramientas` | Spek, MusicScope, librosa |
| `decision` | Decisión de diseño (ADR) |
| `tfg` | Relevante para la memoria del TFG |

## Formato del log

```markdown
## [YYYY-MM-DD] categoría | Título breve
Descripción de lo que ocurrió y por qué. 1-3 líneas.
```

Categorías: `inicio`, `algoritmo`, `gui`, `arquitectura`, `testing`, `distribucion`, `bugfix`, `investigacion`

El log es append-only. Nunca se editan entradas pasadas.

## Operaciones

### Ingest de fuente externa
1. Fuente va a `sources/` (inmutable)
2. Resumen en `fuentes/nombre-fuente.md`
3. Actualizar páginas del wiki que se enriquezcan con la fuente
4. Actualizar `index.md`
5. Añadir entrada al `log.md`

### Ingest de conocimiento interno
1. Después de una sesión de trabajo significativa
2. Actualizar/crear páginas relevantes del wiki
3. Añadir entrada al `log.md`

### Consulta con resultado valioso
1. Si una respuesta merece persistir, se guarda como página nueva
2. Se actualiza `index.md`

## Relación con otros sistemas

- **CLAUDE.md + rules/**: gobierno del LLM para desarrollo (no cambia)
- **memory/**: persistencia cross-conversación (no cambia)
- **knowledge/*.txt**: fuentes internas originales (inmutables, el wiki las referencia)
- **El wiki**: capa de síntesis, cross-referencing y narrativa
