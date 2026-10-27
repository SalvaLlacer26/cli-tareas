---
description: Añade una acción nueva a acciones.json y, si hace falta, el código que la soporta
agent: build
---

Quiero añadir la acción: $ARGUMENTS

1. Carga la skill acciones-json.
2. Propón primero la entrada JSON y espera mi visto bueno.
3. Si el tipo ya existe, solo edita acciones.json. Si no, añade la clase en src/tareas/acciones.py siguiendo el patrón de las demás.
4. Termina ejecutando `uv run tareas validar` y dime qué orden con --simular debo probar yo.

Estado actual del repo:
!`git status --short`
