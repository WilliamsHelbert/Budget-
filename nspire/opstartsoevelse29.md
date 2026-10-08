# Opstartsøvelse 29 – Skiferie (med hjælpemidler, TI-Nspire)

## Huskeliste (gælder alle opgaver)
- Skriv altid: hypoteser, teststørrelse, p-værdi, sammenligning med α, konklusion **i ord**.
- χ²-uafhængighedstest: df = (r−1)(k−1). Tjek at alle forventede ≥ 5.
- Konfidensinterval for andel: p̂ ± z·√(p̂(1−p̂)/n), z = 1,96 for 95 %.
- "Mindst 25" = P(X ≥ 25) = 1 − P(X ≤ 24). Husk **24**, ikke 25!
- Gem svar med afrunding 3-4 decimaler. Brug "=" hvis Nspire er i Auto/Approx.

## Opgave a – χ²-uafhængighedstest, α = 5 %
**H0:** Svar på destination er uafhængig af aldersgruppe.
**H1:** Svar på destination afhænger af aldersgruppe.

**Nspire:**
1. Ny Regner-side. Skriv `obs:=[12,8,4,5;11,7,7,11;5,6,10,5;18,17,6,7]` (kun tallene, 4×4, ingen totaler). Enter.
2. `menu` → 6 Statistik → 7 Stat-tests → 8 χ² 2-vejs test… → Observeret matrix: `obs` → OK.
3. Aflæs: χ² ≈ **13,92**, df = **9**, PVal ≈ **0,125**.
4. Forventede (`stat.expmatrix`): mindste ≈ 5,05 ≥ 5 → forudsætning OK.
   Største bidrag: Ved ikke/Andet, 50-59 år (≈ 4,85).

**Konklusion:** p = 0,125 > 0,05 → H0 forkastes ikke. Der er ikke dokumenteret en sammenhæng mellem
svar og aldersgruppe på 5 %-niveau.

## Opgave b – estimat og 95 %-konfidensinterval for andel til Østrig
- p̂ = 48/139 ≈ **0,345** (34,5 %)
- Spredning: √(0,345·0,655/139) ≈ 0,0403
- **Nspire:** `menu` → 6 Statistik → 6 Konfidensintervaller → 5: 1-prop z-interval. Succeser x = 48, n = 139, C-niveau 0,95.
- **95 %-KI: [0,266 ; 0,424]** → ca. [26,6 % ; 42,4 %]

## Opgave c – binomialfordeling, 100 danskere, mindst 25 svarer Østrig
Udfordring: tallet efter "andelen er" står som [Equation] i billedet. Her bruges p = 0,35
(ca. estimatet fra b). **Ret p, hvis opgaven angiver andet.**
- X ~ b(100; 0,35). Søgt: P(X ≥ 25) = 1 − P(X ≤ 24).
- **Nspire:** `1−binomCdf(100,0.35,0,24)` ≈ **0,988** (med p = 0,345: ≈ 0,984).
- Svar: Sandsynligheden er ca. **98,8 %** (≈ 99 %).
