# ayce — Intérprete v0.3.1

Intérprete del lenguaje de programación ayce, escrito en Python.

## Novedades de v0.3.1

- **Fix BOM UTF-8**: los archivos guardados con BOM ya no rompen el lexer
- **Fix concatenación**: `+` con string autoconvierte cualquier operando
- `Template`, `Shape`, `Variant` (de v0.3)

## Instalación

1. Entrá a la carpeta `sdk/`
2. Abrí PowerShell ahí
3. Ejecutá:

```powershell
python -m pip install -e .
```

## Uso

```powershell
python -m ayce archivo.ayce
```
