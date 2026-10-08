# SMT – komplet regelbog (oktober 2026)

Selvstændig beskrivelse af SMT-modellen, så den kan implementeres fra bunden uden anden kode.
Alle tider er **New York-tid** (dansk tid = NY + 6 timer, undtagen i de uger hvor sommertid
skifter på forskellige datoer). Instrumenter: **NQ** (handles) og **ES** (sammenligning).
Data: 15-sekunders candles (OHLC) for begge. 1 tick = 0,25 point. **1R = 10 point.**

## 1. Sessioner og session-niveauer
| Session | NY-tid |
|---|---|
| Asia | 20:00 – 02:00 (aftenen før) |
| London | 02:00 – 08:00 |
| NY PRE | 08:00 – 09:30 |

- Hver session har et high og et low pr. indeks (NQ og ES hver for sig), fra alle 15s-candles i sessionen.
- **Samling (merge):** Efter at Asia/London er slut og frem til 09:30: laver et indeks et nyt high
  over sessionens high (eller low under low), flytter niveauet med (det er ikke "brugt", det er nu
  samlet med en senere session). Er et London- eller Asia-niveau samlet på **bare ét af indeksene**,
  bruges det niveau slet ikke som SMT-niveau den dag (kun det senere sessions niveau, fx NY PRE high).
  NY PRE samles aldrig (den slutter 09:30).
- Sweep af et niveau = indeksets high ≥ niveau + 1 tick (for highs), low ≤ niveau − 1 tick (lows).

## 2. 15m-niveauer (NY PRE)
- Hver 15m-candle der starter i NY PRE (08:00–09:15) giver et high- og et low-niveau på både NQ og ES
  (samme 15m-candle på begge).
- Rører et af indeksene niveauet (high ≥ / low ≤) i en senere candle mens NY PRE kører, er det dødt.
- Et 15m-niveau lig NQ's NY PRE high/low (inden for ½ tick) springes over (det er NY PRE-niveauet).
- **15m-niveauer er kun liq i 09:30-minuttet** (09:30:00–09:30:45). Som BE kan de bruges hele vinduet,
  så længe NQ ikke har taget dem.
- **5m-niveauer** laves på samme måde af 5m-candles i NY PRE, men bruges **kun som BE og kun ved
  entry i 09:30-minuttet**.

## 3. Taget-reglen
For hvert session-high (low spejlvendt), så længe sessionen kører:
- Notér i hvilken 15m-candle hvert indeks senest lavede sit session-high.
- Lavede de det i **forskellige** 15m-candles, er hvert indeks' **Taget** = dets eget high i den
  15m-candle hvor det *andet* indeks lavede sit session-high. (Samme 15m-candle → ingen Taget.)
- Taget gælder ikke for samlede niveauer.
- I vinduet: tager et indeks sin Taget (high ≥ Taget + 1 tick, og Taget ligger under indeksets eget
  niveau), tæller det som at indekset har taget niveauet.

## 4. Handelsvindue og SMT-signal
- Vindue **09:30:00 – 09:59:45**. Kun minutter med tværsum 3, 6 eller 9: **:30, :33, :36, :42, :45, :51, :54**
  (3-6-9). Et sweep i et andet minut gør det niveau brugt (ingen SMT på det).
- **SMT short** på et high-niveau (long spejlvendt på lows): det ene indeks sweeper sit niveau i vinduet,
  og det andet indeks har **ikke** taget sit (hverken niveau eller Taget). Har begge taget det = ingen SMT
  (det er Vergence) – niveauet er brugt.
- Niveauer der allerede er swept før 09:30 er brugt.
- **Close tilbage:** i **samme minut** som sweepet skal en 15s-candle lukke tilbage under niveauet på det
  indeks der sweepede, og **begge indeks skal lukke samme vej** på den candle (short: begge close < open).
  Minuttet går uden det → niveauet er brugt.
- **Tid close:** entry kun på den 15s-candle der *først* sweepede niveauet, eller den næste. 3. candle eller
  senere = intet trade.
- **Max SL:** SL = NQ's 1-minut-high indtil nu (short; long: 1m-low), mindst 10 point fra entry.
  Er (1m-high − close) > 30 point → intet trade, niveauet er brugt.
- Entry = NQ's close på den 15s-candle. Kun ét trade pr. minut. Først fyrede niveau vinder.
- **Begge sider samme minut:** tages der både et high-niveau og et low-niveau (sweep på et af indeksene)
  i samme minut, kommer der ikke flere trades i det minut (trades der allerede er taget, står).

## 5. EQ (equilibrium) – til BE og ugyldig-regler
EQ'er **oprettes** af 1m-candles på NQ (vurderes når 1m-candlen lukker, dvs. på den første 15s-candle i
næste minut), men de **følges på 15s-candles**: vækst og ramt-tjek sker for hver 15s-candle, ikke pr. minut.
Ved oprettelsen starter den voksende ende i 1m-candlens eget low/high og den aktuelle 15s-candles low/high.
- **Bearish EQ:** close < open OG close < (high+low)/2. Anker = candlens high. Bund = candlens low,
  og vokser med nye lows. EQ-linje = (anker + bund)/2.
- **Bullish EQ:** spejlvendt (close > open og > midten, anker = low, toppen vokser med nye highs).
- Max én live bearish og én live bullish ad gangen (ny oprettes kun når der ikke er en live).
- **Ramt:** pr. 15s-candle: bearish EQ er ramt når high ≥ EQ-linjen (tjekkes mod linjen før candlens eget low flytter den);
  bullish når low ≤ linjen. Ramt = brugt (ikke live mere).
- **Ved 09:30 nulstilles alle live EQ'er.** 09:29-candlen giver ikke en ny live EQ efter open.
- **EQ før open:** den live bearish og bullish EQ der står ved 09:29:59 gemmes som "EQ før open".
  Står der ingen live i en retning, bruges 09:29-candlens EQ (hvis den er en EQ) i den retning.
  EQ før open vokser videre efter open, til den er ramt. Ramt-tjek pr. 15s-candle efter candlens forløb:
  grøn candle = open→low→high→close, rød = open→high→low→close; kommer det nye yderpunkt før prisen går
  mod linjen, tjekkes mod den flyttede linje, ellers mod den gamle. (09:29-EQ'en tjekkes først fra 09:30:15.)

## 6. BE (break even)
Kandidater på profit-siden af entry, **2–50 point** fra entry; den **nærmeste** vælges:
- Live EQ på BE-siden: short → bullish EQ's linje og dens 0,75-niveau (bund + 0,75·(top−bund));
  long → bearish EQ's linje og dens 0,25-niveau.
- EQ før open (begge retninger), hvis ikke ramt endnu.
- Session-niveauer: **short → kun session LOWS** (Asia low, London low, NY PRE low); **long → kun session HIGHS**.
  Et session-high er aldrig BE for en short (heller ikke hvis prisen er løbet igennem det), og omvendt.
  Er niveauet taget af NQ **før 09:30**, er det ikke kandidat. Er det taget i vinduet (til og med
  entry-candlen) og bliver det valgt → tradet er ugyldigt.
- 15m-niveauer (ikke døde, ikke taget af NQ). 5m-niveauer kun ved entry i 09:30-minuttet.
- Intet BE fundet → tradet kører uden BE.

**Ugyldigt trade:**
- EQ før open på BE-siden (short: den bullish, long: den bearish) er ramt i entry-minuttet – før eller af
  entry-candlen – og ligger mellem 2 point bag entry og 50 point foran.
- En live EQ på BE-siden er ramt i entry-minuttet før entry-candlen, og dens linje ligger højst 2 point bag entry.
- Et session-niveau på BE-siden er taget (første gang i vinduet) i entry-minuttet før entry-candlen, højst 2 point bag entry.

## 7. TP og trade-styring
- **TP:** nærmeste af (begge live EQ-linjer, session high/low på profit-siden som NQ ikke har taget) der
  ligger **35–75 point** fra entry. Ellers 75 point.
- Fra candlen efter entry: SL rammes (short: high ≥ SL) eller TP rammes (low ≤ TP). Begge på samme candle → SL.
- **BE:** når prisen rører BE-niveauet flyttes SL til entry. Ikke i de første 2 15s-candles efter entry:
  rører prisen BE i dem, afgøres det ved 2. candles close – står prisen på profit-siden af entry, er BE aktiv
  fra 3. candle, ellers kører tradet uden BE.
- Resultat i R = point / 10 (TP 75 p = 7,5R, SL 24 p = −2,4R, BE = 0).
- Nyt trade mens et er åbent: det gamle lukkes (afløst).

## 8. Dagsregler
- Max 2 SMT-trades pr. dag, og **stop for dagen efter et vundet trade (TP)**. BE er ikke en win.
