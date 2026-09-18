# EQ + SMT — overlevering

Opdateret 18-09-2026. Læs denne først.

**Kort version: EQ tjener kun penge i det vindue den blev tunet på. Uden for
det vindue er den nul eller negativ. SMT-journalen er derimod stærk, men
SMT-modellen i repo'et er en dårlig kopi af den. Handl ikke EQ endnu.**

---

## 1. Filerne

| Fil | Hvad |
|---|---|
| `eq_model.py` | EQ-konfluensmotoren. Rører ES og NQ samtidig. |
| `smt_model.py` | SMT (Session Sweep), port af Pine v10. Taber hvor journalen tjener. |
| `koer_alt.py` | Kører begge og skriver `alle_trades.csv`. |
| `databento_konverter3.py` | Databento OHLCV-1s → 15s parquet, ét år pr. fil. |
| `del_op.py` | Deler en parquet i bidder under 30 MB. |

Kør: `python koer_alt.py sti/til/datamappe`

### Dataformat — konverteren og motoren taler ikke samme sprog

`databento_konverter3.py` skriver `ts` (epoch-sekunder, int32) og priser som
**heltal i ticks** (pris / 0,25). Motoren forventer `time` (UTC-datetime) og
priser i **rigtige point**. Der mangler et mellemtrin: slå årene sammen,
omdøb `ts` → `time`, gang priserne med 0,25.

Sker det ikke, er ES-priser 4× for høje og 8/40-reglen måler i ticks.
Alt bliver forkert uden at fejle.

---

## 2. Enheder

```
1 R  = 10 NQ-point = 2 ES-point = 200 USD
```

**R er en fast enhed, ikke risiko-normaliseret.** Et bredere stop koster
flere R. Journalens `r`-kolonne følger samme konvention.

Den faktiske reward:risk er TP divideret med stoppet — median 4,3:1, ikke 7,5:1.

---

## 3. EQ-reglerne

**Setup**
- Bear-EQ fødes når et 1m-lys lukker bearish OG under sit eget (H+L)/2.
  Ankeret er lysets high. Linjen = (anker + løbende ekstrem) / 2.
- Begge aktiver skal have aktiv EQ i samme retning.
- Ét aktiv rører sin EQ-linje uden at lukke igennem → setup armet.
- Bekræftelse: et 15s-lys hvor **begge** aktiver lukker samme vej.

**Indgang** — kun 15:30–16:00 dansk tid, kun shorts. Åben position gør
næste setup **ugyldigt** (ikke udskudt).

**Stop** på EQ-ankeret.

**EQ'ernes levetid** — begge aktivers EQ'er er ude af drift fra handlen
udløses til den er ude i SL, BE eller TP.

**Break-even** — nærmeste **levende** 5m-likviditet i gevinstretningen,
låst ved entry. Et niveau dør når prisen har handlet igennem det.

**8/40** — stop og BE-afstand skal være ≤ 8 ES-point / ≤ 40 NQ-point,
ellers er handlen ugyldig.

**TP** 15 ES-point / 75 NQ-point. **Intet dagsstop.**

**Tilføjet efter test:** TP1 (halv position ved 1,0 R) og mindstestop på
2,5 ES-point. Uden dem taber modellen 63,88 R out-of-sample med 94,38 R
drawdown; med dem 9,75 R og 29,56 R.

---

## 4. Resultater — juni 2023 til september 2026, 432 handler

| Periode | n | R | pr. handel | PF | maxDD |
|---|---:|---:|---:|---:|---:|
| **Ude: jun 2023 – nov 2024** | 202 | **−9,75** | −0,048 | **0,92** | −29,56 |
| Tunet: nov 2024 – feb 2026 | 197 | **+72,06** | +0,366 | 1,64 | −10,00 |
| **Ude: mar – sep 2026** | 33 | **+1,12** | +0,034 | 1,04 | −13,75 |
| **I alt** | 432 | +63,44 | +0,147 | 1,24 | **−29,56** |

**235 handler uden for tuningsvinduet giver −8,63 R. 197 handler indeni
giver +72,06 R.** To uafhængige perioder, én før og én efter, begge nul
eller negative. Det er kendetegnet ved kurvetilpasning.

Opsætningen blev fundet gennem ca. 55 kørsler på midterperioden.

### NQ er mere robust end ES

| Periode | ES | NQ |
|---|---:|---:|
| Ude: jun23–nov24 | −9,75 (PF 0,92) | **+3,09** (PF 1,02) |
| Tunet | +72,06 (PF 1,64) | +28,25 (PF 1,22) |
| Ude: mar–sep26 | +1,12 (PF 1,04) | **+4,45** (PF 1,15) |
| **Kun uden for vinduet** | **−8,63** | **+7,54** |

NQ er positiv i alle tre perioder; ES er det ikke. Beslutningen "der handles
ES" blev truffet på det tunede vindue. **Den bør tages op igen.**

---

## 5. Fejl fundet og rettet — gentag dem ikke

**Partnerens EQ blev aldrig brugt op.** `eq_model.py` dræbte EQ'en når et
aktiv raidede sin egen linje, men når aktivet var konfluens-partner blev
dets EQ kun aflæst. Ankeret blev genbrugt hele dagen mens ekstremet løb, så
stopafstanden voksede uden loft (op til 659 point på NQ). 8. jan 2026 gav
samme NQ-anker tre setups med stop på 98 → 129 → 167 point.
**Rettet 18-09-2026.** Median-afvigelse mod journalen: +21,00 → +1,25 point.

**BE lå på død likviditet.** Den gamle regel tjekkede ikke om prisen allerede
havde handlet igennem niveauet. 58 % fik flyttet stop. +128,21 → +34,55 R.

**RTH-filteret i datakonverteren.** Databeskæring der virkede som skjult
filter. 85 setups blev aldrig gyldige. **Brug altid fuld døgndata**
(02:00–22:10 dansk tid).

**Dagsstop på −2,5 R.** Fandtes ikke i journalen. Tilføjet af modellen,
ikke af traderen.

**Tidszone.** Motoren SKAL køre i `America/New_York`. `eq_model.py:21` har
stadig `Europe/Copenhagen` som modulstandard — den overskrives af
`koer_alt.py`. **Kør altid gennem `koer_alt.py`.**

**ms mod ns i parquet.** Brug `.astype('datetime64[s]').astype('int64')`.

---

## 6. Testet og virker IKKE

| Idé | Resultat |
|---|---|
| Stop efter første tab på dagen | +71,00 mod +98,50 |
| Kun én handel per dag | +52,38 |
| Fjern BE | R uændret, **maxDD −22 → −36** |
| Tættere TP (1,5–6,0 R) | Monotont dårligere |
| Konstant risiko-skalering | R uændret, **maxDD −11 → −16** |
| Stoploft på 3 R | Forkert præmis — brede stop er de **bedste** handler |
| Longs samtidig med shorts | −10,08 |
| **Volatilitetsskalerede mål** | ES +63 → **+12 R**, maxDD −30 → **−55** |
| **3 kontrakter + TP 10 point** | +64 → **+28 R**, maxDD −30 → **−45** |
| Dagsstop | Fandtes ikke i journalen |

**BE-reglen er dit drawdown-værktøj, ikke et profit-værktøj.** Den koster
0,50 R og halverer drawdownen.

**Brede stop er de bedste handler.** Monotont over alle fire kvartiler:
0,75–2,75 pt giver +0,185 R/handel, 5,25–8,00 pt giver +0,586.

---

## 7. Hvad der driver resultatet

TP-raten, ikke volatiliteten:

| Periode | TP-rate | MFE median | TP delt med 30m-range |
|---|---:|---:|---:|
| Ude jun23–nov24 | **8,9 %** | 1,25 R | 1,10× |
| Tunet | **17,3 %** | 1,75 R | 0,69× |
| Ude mar–sep26 | 15,2 % | 1,38 R | 0,59× |

Prisen steg 48 % og rangen 85 %, så den faste TP på 15 point blev ~2×
lettere at nå fra 2023 til 2026. **Men at korrigere for det gør det værre**
— volatilitetsskalerede mål ændrede TP-raten fra 8,9 % til 8,6 %.

Forskellen er statistisk marginal: ES z = +2,48 (p = 0,013) efter 55 forsøg;
NQ z = +0,25 (p = 0,81). Ved sand rate 13,2 % og 200 handler ligger 95 %
af stikprøver mellem 8,5 % og 17,9 % — begge observationer ligger i enderne.

**Forventningen vipper mellem tab og gevinst på fire procentpoint i
træfprocent.** Det er modellens egentlige problem: kanten er for tynd til
at overleve normal stikprøvevariation.

### Fortsættelsesegenskaben (målt med TP så bredt det aldrig rammes)

| Nået | → 15 pt | → 20 pt | → 25 pt |
|---|---:|---:|---:|
| 10 pt | 81 % | 67 % | 59 % |
| 15 pt | — | 83 % | 73 % |

Handler der når 10 point er stort set de samme som når 15 og 25. Derfor
taber en tættere TP: man fanger ingen nye vindere.

**Bredere TP virker konsekvent.** TP 20 point slår TP 15 i alle tre perioder
(−6,31 / +80,06 / +2,38 mod −9,75 / +72,06 / +1,12). TP 25 giver +100,62 R
i alt og er eneste niveau der er positivt out-of-sample — men det tal er
en spids mellem to negative naboer og er ikke robust.

**Bemærk:** TP over 15 point bryder 50 %-konsistensreglen i LucidFlex-
evalueringen ($1.500 af et $3.000-mål). Reglen gælder kun evalueringen.

---

## 8. SMT

**Journalen:** 142 handler, jan 2025 – aug 2026, **+127,50 R**, t = +3,46,
maxDD −7,30 R, **aldrig under −10 R**, profitfaktor 2,79.
Konto 50.000 → 75.500 USD. (127,50 × 200 = 25.500 — R-enheden bekræftet.)

**Modellen i repo'et:** 86 handler på samme slags data, **−34,15 R**.

Modellen taber hvor traderen tjener. Det er en fejl i samme klasse som
partner-EQ-fejlen og er formentlig findbar. **Det er det mest værdifulde
uløste punkt i hele projektet.**

Uløst detalje: 27. april 2026 skulle fjernes af regel C, men bliver det ikke.

---

## 9. Hvad der skal ske nu

1. **Find fejlen i SMT-porten.** Journalen giver +127,50 R, modellen −34,15 R.
2. **Genovervej ES mod NQ på EQ.** NQ er positiv i alle tre perioder.
3. **Handl ikke EQ** før den har vist en kant på data den ikke er tunet på.

Hent 2022 og første halvdel af 2023 hvis der skal mere out-of-sample til.
Lås opsætningen skriftligt først, kør så **én gang**.

---

## 10. Data

Motoren forventer `ES.parquet` + `NQ.parquet` pr. mappe: `time` (UTC),
`open`, `high`, `low`, `close`, 15s-barer i **point**, frontkontrakt
volumenrullet. **Filerne ligger ikke i repo'et** (.gitignore).

Verificeret dækning:

| Kilde | Periode | Døgndækning |
|---|---|---|
| Databento 2023–2024 | 16. jun 2023 – 1. nov 2024 | 02:00–22:09 |
| Databento | 1. nov 2024 – 27. feb 2026 | 02:00–22:09 |
| Egen 2026-kilde | 2. jan – 11. sep 2026 | 00:00–23:59 |

De to kilder blev krydstjekket på jan–feb 2026: **18 af 18 handler matcher
på dag og minut**, identiske stop, identiske R, største entry-afvigelse ét
tick. Den nye kilde har én handel mere (19. feb) som Databento manglede.
