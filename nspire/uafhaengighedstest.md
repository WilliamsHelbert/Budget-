# Guide: χ²-uafhængighedstest på TI-Nspire

**Formål:** Test om to kategoriske variable er uafhængige.
H0: variablene er uafhængige. H1: der er sammenhæng.

## 1. Indtast data (Lister & regneark eller Matrix)
- Opret en matrix med de **observerede** antal (kun tallene, ingen totaler).
- Fx 2×3: `[[20,30,50],[30,30,40]]` gemmes som variablen `obs`.

## 2. Udfør testen
1. Åbn en **Regner**-side.
2. `menu` → **6: Statistik** → **7: Stat-tests** → **8: χ² 2-vejs test…**
3. Vælg **Observeret matrix: obs**. Tryk OK.

## 3. Aflæs resultatet
| Output | Betydning |
|---|---|
| `χ²` | Teststørrelsen |
| `PVal` | p-værdi |
| `df` | Frihedsgrader = (rækker−1)(kolonner−1) |
| `ExpMatrix` | Forventede antal (gem som `exp`) |
| `CompMatrix` | Bidrag til χ² fra hver celle |

## 4. Tjek forudsætning
Alle forventede antal i `ExpMatrix` bør være ≥ 5.

## 5. Konklusion
- p < signifikansniveau (typisk 0,05): **forkast H0** – der er en sammenhæng.
- p ≥ signifikansniveau: **behold H0** – ingen dokumenteret sammenhæng.

## Alternativ: manuel udregning
- Forventet = (rækkesum · kolonnesum) / total
- `χ² = Σ (obs − forv)² / forv`
- p-værdi: `1 − χ²cdf(0, χ², df)` eller `χ²Cdf(χ², ∞, df)`
