# ayce — Extensión para VS Code

Soporte del lenguaje de programación ayce en VS Code. Estructura plana, lista para empaquetar como `.vsix`.

## Cómo instalar (local)

1. Asegurate de tener Node.js instalado.
2. Instalá `vsce` (una sola vez):
   ```cmd
   npm install -g @vscode/vsce
   ```
3. En la carpeta de la extensión (donde está `package.json`):
   ```cmd
   cd path\al\ayce_project\vscode
   vsce package
   ```
   Esto genera `ayce-0.5.0.vsix`.
4. En VS Code:
   - `Ctrl+Shift+P` → "Extensions: Install from VSIX..."
   - Seleccioná el `.vsix` generado.

O bien, instalalo desde la línea de comandos:
```cmd
code --install-extension ayce-0.5.0.vsix
```

## Cómo ejecutar un archivo `.ayce`

1. Abrí la carpeta `ayce_project/` completa en VS Code (no sólo la subcarpeta `vscode/`).
2. Abrí cualquier archivo `.ayce` (por ejemplo `templates/examples/hola.ayce`).
3. Presioná `Ctrl+Alt+R` (Win/Linux) o `Cmd+Alt+R` (Mac).
   - Se ejecuta en la terminal integrada de VS Code.
   - Si el programa usa `inlet(...)`, podés escribir en esa terminal.
4. Alternativa: `Ctrl+Alt+Shift+R` ejecuta en el panel de salida (no interactivo).

## Detección automática del intérprete

La extensión busca el intérprete en este orden:

1. Setting `ayce.interpreterPath` (si lo configuraste).
2. `tools/ayce_cli.py` dentro del workspace (la carpeta que abriste en VS Code).
3. `python3 -m ayce` (requiere `pip install -e sdk/`, **opcional**).

Si abrís la carpeta `ayce_project/` completa en VS Code, la opción 2 funciona sin que
tengas que configurar nada: la extensión encuentra `tools/ayce_cli.py` y lo usa.

## Code Runner (opcional)

Si tenés la extensión Code Runner instalada:

- `Ctrl+Shift+P` → "ayce: Configurar Code Runner automáticamente"
- Esto añade la entrada `"ayce": "python tools/ayce_cli.py $filePath"` a `code-runner.executorMap`.
- Después podés usar el botón ▶ de Code Runner con archivos `.ayce`.

## Atajos de teclado

| Atajo | Acción |
|-------|--------|
| `Ctrl+Alt+R` | Ejecutar en terminal (interactiva) |
| `Ctrl+Alt+Shift+R` | Ejecutar en panel de salida |

## Estructura de la extensión

```
vscode/
├── [Content_Types].xml          ← OPC content types (para .vsix)
├── extension.vsixmanifest       ← manifest del paquete VSIX
├── package.json                 ← manifest de la extensión
├── language-configuration.json  ← brackets, comentarios, indentación
├── extension.js                 ← código de los comandos
├── icons/
│   ├── ayce-file.svg            ← icono para archivos .ayce
│   ├── icon.svg                 ← icono de la extensión (vectorial)
│   └── icon.png                 ← icono de la extensión (128×128 PNG)
├── syntaxes/
│   └── ayce.tmLanguage.json     ← grammar TextMate para resaltado
└── snippets/
    └── ayce.json                ← snippets de código
```

## Empaquetar manualmente como .vsix (sin vsce)

Un `.vsix` es un ZIP con esta estructura. Si no querés usar `vsce`, podés
zipear el contenido de la carpeta `vscode/` y renombrar el `.zip` a `.vsix`:

```cmd
cd vscode
# En Windows, con 7-Zip instalado:
7z a -tzip ayce-0.5.0.vsix [Content_Types].xml extension.vsixmanifest package.json language-configuration.json extension.js icons syntaxes snippets
```

⚠️ Asegurate de que `[Content_Types].xml` y `extension.vsixmanifest` queden en la
**raíz** del ZIP, no dentro de una subcarpeta.

## Colores (paleta "Ayce Dusk")

La extensión trae su propia paleta de tonos apagados (no cansan la vista) en dos variantes,
clara y oscura, y elige sola según el tema que uses. Cambia en vivo si cambiás de tema.

- Setting `ayce.colors.mode`: `auto` (por defecto), `dark`, `light` u `off`.
- `ayce: Aplicar colores de sintaxis` — reaplica la paleta (y limpia colores viejos de ayce).
- `ayce: Quitar todos los colores de ayce` — borra todo color de ayce de tus settings.
- Las reglas de la extensión llevan el nombre `ayce-palette:*` en `editor.tokenColorCustomizations`.
  Si querés un color propio, agregá tu regla con otro nombre en `textMateRules`; no se toca.

### Cambiar un color sin tocar el código

En `settings.json`:

```json
"ayce.colors.overrides": {
  "variable": "#8FD68A",
  "operator": "#D9A0C8"
}
```

Nombres válidos: `variable`, `operator`, `none`, `string`, `int`, `float`, `bool`, `bytes`, `comment`,
`control`, `decl`, `error`, `io`, `builtin`, `fn`, `bracket`, `punct`, `constant`, `modifier`, `escape`,
`radix`, `collection`.

### Categorías con color propio (v0.6.3)

Todo token nuevo del lenguaje lleva un color que no comparte con ninguna otra categoría,
para que no se confundan entre sí:

- `radix` — literales con base `0x` (hexadecimal), `0o` (octal) y `0b` (binario).
  Coral: `#FF6B47` en oscuro, `#C13E1C` en claro.
- `collection` — tipos colección `list`, `dict`, `tuple`, `set`.
  Esmeralda: `#2ED573` en oscuro, `#11804C` en claro.

Los colores se eligieron por distancia perceptual (ΔE ≥ 13 contra cualquier otro
color de la misma variante) y con contraste ≥ 4.5:1 sobre el fondo.
