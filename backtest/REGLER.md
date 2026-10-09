# Endelige regler (oktober 2026)

Besluttet ud fra backtest 20/6/2023 – 11/9/2026 (NQ/ES 15s) og dine journaler.
Kun ændringer der hjælper over hele perioden er taget med.

## Fælles (SMT og Vergence)
- Handelsvindue 15:30–16:00 dansk tid (09:30–10:00 NY).
- SL 10–30 point (over 30 = ugyldig), TP 35–75 point, 1R = 10 point.
- **Tid close:** entry på den første 15s-candle der tager niveauet eller den næste.
  3. candle eller senere = ugyldig. (`TID_CLOSE = 2`, `TID_REF = 'first'`, `TID_REF_SMT = 'first'`)
- Ingen BE i de første 2 15s-candles efter entry.
- EQ før open (BE-siden) ramt i entry-minuttet – før eller af entry-candlen – = **altid ugyldig**, uanset hvor
  linjen ligger ift. entry (valgt 8/10-26; 14/5 SMT bliver ugyldig); EQ før open fortsætter med at vokse efter open.
  EQ'en fra 15:29-candlen (lukker før open) tæller også som EQ før open, men kun hvis der ikke stod
  en live EQ ved open (`PRE_1529`, 30/3-26 og 24/2-26). EQ før open vokser og stopper på den candle
  der rammer linjen. Candlens forløb afgør om det er den gamle eller den flyttede linje:
  grøn candle = open-low-high-close, rød = open-high-low-close (`PRE_GROWFIRST='path'`, 6/1-26).
- 15m-niveauer: liq kun i 15:30-minuttet (entry i samme minut). Som BE (kun SMT) hele vinduet,
  så længe de ikke er taget.
- Et session-niveau der kun er samlet med en senere session på det ene indeks, er ikke sit eget
  niveau (fx London+Asia samlet i NY PRE high på NQ, men ikke på ES → kun NY PRE high). (`MERGE_EITHER`, 9/4-26)
- Ét trade pr. minut; high og low taget i samme minut før entry = ugyldig.
- Max 2 trades pr. dag pr. model, og **stop modellen for dagen efter en vundet trade** (også hvis det er dagens første).
  BE er ikke en win. Effekt 2023–26: SMT filter 30 +124,0 → +126,8R, Vergence +53,4 → +46,9R, samlet 177,4 → 173,7R, samme DD og blows.

## SMT
- 3-6-9-reglen beholdes (uden den: +33R mod +70R).
- **Kurvefilter (afbryder):** alle SMT-signaler noteres på papir. Næste SMT-trade tages kun rigtigt,
  når papirkurven ligger på eller over gennemsnittet af de sidste 30 kurvepunkter. Ellers kun papir.
  Værktøj: "SMT afbryder"-artifact.

## Vergence
- Begge indeks skal tage SAMME niveau. De 5 min måles mellem de to indeks' første take af det niveau –
  nye yderpunkter tæller ikke (20/1 og 5/2-26). Hvert 15m-niveau er sit eget niveau (22/1-26).
- Indekset der tager liq i det fuldendende minut lukker tilbage forbi niveauet (begge, hvis begge i samme minut).
- Entry i samme minut som sweepet. BE kun EQ (EQ, 25/75 %, EQ før open) og session-levels – ikke 5m/15m.
- Intet kurvefilter. Vergence 2023–26: +42,9R, DD −22, 4 blows (10R). Begge modeller: +143,1R, DD −30, 4 blows.

## Resultater med reglerne (R)
| | 2023* | 2024 | 2025 | 2026** | I alt | Max DD | Blows (−10R) |
|---|---|---|---|---|---|---|---|
| SMT + tid close + kurvefilter 30 | +26,3 | −10,7 | +29,9 | +54,7 | +100,2 | −19 | 1 |
| Vergence + tid close | +5,9 | +7,0 | +5,1 | +34,8 | +52,9 | −24 | 6 |
| SMT filter 30 + Vergence | +32,2 | −3,7 | +35,0 | +89,6 | +153,1 | −34 | 7 |

Alle med max 2/dag og stop efter win. Testet og forkastet (oktober 2026): EQ før open min. 3/5 min gammel,
EQ før open ramt af entry-candlen tæller ikke, EQ ramt bag entry gør altid ugyldig (−18R, og 14/5 er gyldig),
correlation 50 % af NY PRE-rangen (kun NY PRE: −5R; NY PRE+15m/alle: −70R).
\* fra 20/6. \*\* til 11/9.

## Testet og forkastet
Pris-/volatilitetsskalering af SL/TP, mindre TP, SL max 25, ingen max SL, uden 3-6-9, ekstra tidsvinduer
(16:00–17:00, London-åbning), pause efter tab, "siden lukket" efter Vergence uden trade, "gyldigt BE påkrævet".
