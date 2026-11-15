#!/usr/bin/env python3
"""Referencia CPython para t_random.ayce — mismos calls en el mismo orden."""
import random

R = random.Random()
R.seed(42)
out = []
p = out.append
p(R.random())
p(R.random())
p(R.randint(1, 10))
p(R.choice([True, False]))
p(R.randint(0, 99))
p(R.uniform(-5.0, 5.0))
p(R.randrange(100))
p(R.randrange(10, 20))
p(R.randrange(10, 20, 3))
lst = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
lst2 = lst[:]
R.shuffle(lst2)
p(lst2)
p(R.sample(lst, 4))
p(R.choice(lst))
p(R.choices(lst, k=5))
p(R.gauss(2.0, 0.5))
p(R.gauss())
p(R.gauss(-1.5))
p(list(R.randbytes(8)))
p(list(R.randbytes(5)))
R.seed(12345)
p(R.random())
p(R.randint(0, 999999))
R.seed(-7)
p(R.random())
p(R.choice([True, False]))
R.seed(42)
p(R.random())
print("\n".join(str(v) for v in out))
