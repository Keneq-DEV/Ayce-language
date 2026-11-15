# Harness de verificación contra CPython

Cada `t_*.ayce` imprime valores que se comparan con CPython:

    python3 tools/ayce_cli.py tests/t_math.ayce > out.txt
    python3 tests/ref_math.py > esperado.txt
    diff out.txt esperado.txt

- t_math / ref_math: math.ayce puro vs módulo math (tolerancia ~2e-15)
- t_random / ref_random: MT19937 bit-exacto vs random.Random(seed)
- t_hash: hashlib puro vs hashlib (16 vectores exactos)
- t_b64: base64/binascii/zlib(crc32,adler32)/struct vs CPython (exacto)
- t_hmu: hmac, uuid3/uuid5 (valores RFC), json round-trip, valid
- t_bitops: operadores bit a bit y literales 0x/0b
