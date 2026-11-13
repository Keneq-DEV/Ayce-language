# ayce — Guía de instalación 

## Paso 1 — Instalar el intérprete

1. Descomprimí `ayce_project_v.x.x.zip`
2. Entrá a la carpeta `sdk/`
3. Abrí PowerShell ahí
4. **PRIMERO** desinstalá la versión vieja si la tienes:

```powershell
python -m pip uninstall -y ayce
```

5. **DESPUÉS** instalá la nueva en sdk con cmd:

```powershell
python -m pip install -e .
```

### Verificar que el fix esté presente

```powershell
python -c "import ayce; print(ayce.__version__)"
```

Tiene que decir: `x.x.x`

### Probar

```powershell
python -m ayce "<ruta>\ayce_project\templates\examples\hola.ayce"
```

---

## Paso 2 — Instalar la extensión VS Code

1. Abrí VS Code
2. `Ctrl + Shift + P`
3. Escribí: `Install from VSIX`
4. Seleccioná `ayce-x.x.x.vsix`
5. Recargá VS Code

---

## Paso 3 — Configurar Code Runner

instala la extension code runner..

`Ctrl + Shift + P` → `Open Settings (JSON)`. Añade:

```json
"code-runner.executorMap": {
    "ayce": "python -m ayce \"$filePath\""
},
"code-runner.runInTerminal": true,
"code-runner.clearPreviousOutput": true,
"code-runner.saveFileBeforeRun": true
```

---

## Importante

Si después de instalar te sigue fallando algo que a mí me funciona, verificá:

```powershell
python -c "import ayce; print(ayce.__file__)"
```

La ruta tiene que apuntar a tu carpeta `ayce_project\sdk\ayce\__init__.py`. Si apunta a otra (como `site-packages`), hay una instalación vieja dando vueltas. Desinstalá con `pip uninstall -y ayce` y volvé a instalar.
