# Endelige regler (oktober 2026)

Besluttet ud fra backtest 20/6/2023 – 11/9/2026 (NQ/ES 15s) og dine journaler.
Kun ændringer der hjælper over hele perioden er taget med.

## Fælles (SMT og Vergence)
- Handelsvindue 15:30–16:00 dansk tid (09:30–10:00 NY).
- SL 10–30 point (over 30 = ugyldig), TP 35–75 point, 1R = 10 point.
- **Tid close:** entry på den første 15s-candle der tager niveauet eller den næste.
  3. candle eller senere = ugyldig. (`TID_CLOSE = 2`, `TID_REF = 'first'`, `TID_REF_SMT = 'first'`)
- Ingen BE i de første 2 15s-candles efter entry.
- EQ før open ramt i entry-minuttet = ugyldig; EQ før open fortsætter med at vokse efter open.
- Ét trade pr. minut; high og low taget i samme minut før entry = ugyldig.

## SMT
- 3-6-9-reglen beholdes (uden den: +33R mod +70R).
- **Kurvefilter (afbryder):** alle SMT-signaler noteres på papir. Næste SMT-trade tages kun rigtigt,
  når papirkurven ligger på eller over gennemsnittet af de sidste 30 kurvepunkter. Ellers kun papir.
  Værktøj: "SMT afbryder"-artifact.

## Vergence
- Begge indeks skal tage samme niveau; det andet senest 5 min efter.
- Nye yderpunkter tæller som liq indtil siden har haft sin første Vergence.
- Indekset der tager liq i det fuldendende minut lukker tilbage forbi niveauet (begge, hvis begge i samme minut).
- Entry i samme minut som sweepet. BE kun EQ (EQ, 25/75 %, EQ før open) og session-levels – ikke 5m/15m.
- Intet kurvefilter (gjorde Vergence dårligere i alle varianter).
- Kør med: `MODE='vrg', USE_5M=False, USE_15M_BE=False`.

## Resultater med reglerne (R)
| | 2023* | 2024 | 2025 | 2026** | I alt | Max DD | Blows (−10R) |
|---|---|---|---|---|---|---|---|
| SMT + tid close | +32,6 | −52,2 | +70,0 | +40,2 | +90,6 | −56 | 6 |
| SMT + tid close + kurvefilter 30 | +32,6 | −9,8 | +55,7 | +40,2 | +118,8 | −19 | 2 |
| Vergence + tid close | +1,0 | −0,9 | +10,6 | +17,6 | +28,3 | −24 | 8 |

\* fra 20/6. \*\* til 11/9.

## Testet og forkastet
Pris-/volatilitetsskalering af SL/TP, mindre TP, SL max 25, ingen max SL, uden 3-6-9, ekstra tidsvinduer
(16:00–17:00, London-åbning), pause efter tab, "siden lukket" efter Vergence uden trade, "gyldigt BE påkrævet".
