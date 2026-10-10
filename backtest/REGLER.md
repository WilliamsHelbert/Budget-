# Endelige regler (oktober 2026)

Besluttet ud fra backtest 20/6/2023 – 11/9/2026 (NQ/ES 15s) og dine journaler.
Kun ændringer der hjælper over hele perioden er taget med.

## Fælles (SMT og Vergence)
- Handelsvindue 15:30–16:00 dansk tid (09:30–10:00 NY).
- SL 10–30 point (over 30 = ugyldig), TP 35–75 point, 1R = 10 point.
- **Tid close:** entry på den første 15s-candle der tager niveauet eller den næste.
  3. candle eller senere = ugyldig. (`TID_CLOSE = 2`, `TID_REF = 'first'`, `TID_REF_SMT = 'first'`)
- Ingen BE i de første 2 15s-candles efter entry.
- **EQ før open gør IKKE et trade ugyldigt** (ændret 9/10-26, `PRE_INVALID = False`). Den bruges kun som
  BE-kandidat, så længe den ikke er ramt. Den gamle regel (EQ før open ramt i entry-minuttet = ugyldig) var
  bygget på 2026-dage og var overfit: på 2023–2025 kostede den SMT +40R og Vergence +44R, og din 2025-journal
  matchede kun 48/89 med den mod 65/89 uden. I 2026 koster ændringen ~11R (SMT) / ~9R (Vergence), og 5 SMT-trades
  du har dømt ugyldige (fx 24/2, 30/3) kommer med (−6,7R i alt). Kan slås til igen i indikatorer og NinjaTrader.
  EQ før open vokser videre efter open; 15:29-candlens EQ bruges hvis der ingen live stod ved open (`PRE_1529`);
  candlens forløb afgør ramt (grøn O-L-H-C, rød O-H-L-C, `PRE_GROWFIRST='path'`).
- 15m-niveauer: liq kun i 15:30-minuttet (entry i samme minut). Som BE (kun SMT) hele vinduet,
  så længe de ikke er taget.
- Et session-niveau der kun er samlet med en senere session på det ene indeks, er ikke sit eget
  niveau (fx London+Asia samlet i NY PRE high på NQ, men ikke på ES → kun NY PRE high). (`MERGE_EITHER`, 9/4-26)
- Ét trade pr. minut; high og low taget i samme minut før entry = ugyldig.
- **Ingen trades på dage hvor New York-børsen er lukket** (futures handler, men der er ingen 09:30-open), og heller ikke
  hvis NY PRE mangler data (færre end 300 af 360 15s-bars, fx CME-nedbrud 28/11-25). Tilføjet 10/10-26 efter datatjek:
  fjerner 6 trades (−6,6R) i 2025–26. (`NO_TRADE_DAYS`, `NYPRE_MIN_BARS`)
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
- Entry i samme minut som sweepet. BE: EQ (EQ, 25/75 %, EQ før open), session-levels og – som i SMT – 15m-niveauer
  og 5m-niveauer ved entry i 15:30-minuttet (9/10-26: +6,9R, 1 blow færre for Vergence).
- Intet kurvefilter (kurvefilter 20/30/40 testet 9/10-26: færre R, ikke stabilt bedre).

## Resultater med reglerne (R) – opdateret 10/10-26
Samme tal fra backtesten og fra NinjaTrader-strategien `HelbertModels` (testet trade for trade).
| | 2023* | 2024 | 2025 | 2026** | I alt | Max DD | Blows (−10R) |
|---|---|---|---|---|---|---|---|
| SMT uden filter | +32,4 | −55,2 | +80,5 | +44,4 | +102,1 | −58 | 5 |
| SMT + kurvefilter 30 | +32,4 | −11,5 | +67,3 | +44,4 | +132,5 | −19 | 2 |
| Vergence uden filter | +7,6 | +12,0 | +40,3 | +26,5 | +86,4 | −24 | 2 |
| Vergence + kurvefilter 30 | +8,6 | +8,1 | +29,7 | +19,0 | +65,4 | −17 | 1 |
| Begge, intet filter | +40,0 | −43,2 | +120,8 | +70,9 | +188,5 | −56 | 10 |
| Begge, kurvefilter på begge | +41,0 | −3,4 | +97,0 | +63,4 | +198,0 | −22 | 5 |

Alle med max 2/dag og stop efter win. Gennemsnit begge: 5,4R/måned, 15 af 40 måneder negative.
Journal-match: SMT 2025 65/89, SMT 2026 30/30 (+5 ekstra), Vergence 2026 26/32.

EQ før open-varianter (begge modeller, hele perioden): altid ugyldig +150,0R · original ±2 p +171,2R ·
**aldrig ugyldig (valgt) +214,5R** · slet ikke brugt +193,6R.

Ekstra mulighed (ikke indført): stop dagen ved −2R samlet for begge modeller: +220,2R, 6 blows i stedet for 8,
lidt bedre i alle 4 år.

Testet og forkastet (oktober 2026): EQ før open min. 3/5 min gammel,
EQ før open ramt af entry-candlen tæller ikke,
correlation 50 % af NY PRE-rangen (kun NY PRE: −5R; NY PRE+15m/alle: −70R).
\* fra 20/6. \*\* til 11/9.

## Testet og forkastet
Pris-/volatilitetsskalering af SL/TP, mindre TP, SL max 25, ingen max SL, uden 3-6-9, ekstra tidsvinduer
(16:00–17:00, London-åbning), pause efter tab, "siden lukket" efter Vergence uden trade, "gyldigt BE påkrævet".
