# EQ-konfluens — status 14. september 2026

Dual-asset (ES + NQ) EQ-konfluensmodel. Der handles kun **NQ-benet**, men signalet
kræver at begge assets holder en aktiv EQ samme vej og bekræfter samme retning.
ES-data kan derfor ikke undværes.

## Nuværende opsætning

| Parameter | Værdi |
|---|---|
| Vindue | 09:30–10:00 New York (15:30–16:00 dansk) |
| Retning | kun shorts; longs spærrer pladsen men handles ikke |
| Stop | EQ-anchoren |
| Mål | 75 NQ-point (= 7,5 R) |
| Break-even | forrige 5-minutters ekstrem |
| Lofter | stop og BE maks. 8 pts (ES) / 40 pts (NQ) |
| Dagsstop / dagsmål | −2,5 R / +3,75 R, målt på NQ-benet alene |
| Konfirmation | 15 s |

R-enheden er fast: **1 R = 10 NQ-point**. Det er ikke risikoen pr. handel —
den faktiske stopafstand varierer (median ~25 point).

Motoren kører i **New York-tid**. Det er vigtigt: amerikansk og europæisk sommertid
skifter ikke samtidig, så tre uger i marts ville ramme forkert time med dansk tid.

## Resultater

| Periode | Handler | R | Pr. handel | maxDD | t |
|---|---:|---:|---:|---:|---:|
| 2025 (Databento) | 167 | +74,80 | +0,45 | −26,70 | +1,67 |
| 2026 jan–11. sep | 116 | +45,52 | +0,39 | −21,05 | +1,18 |

Begge år positive i samme størrelsesorden pr. handel.

## Hvad der er efterprøvet på begge år

- **Vindue 15:30–16:00 slår 15:30–16:30.** Bekræftet uafhængigt i 2025 og 2026.
  Udvidelsen til 16:30 var en fejlslutning fra 22 dages data.
- **Dagsregel −2,5/+3,75 slår −5/+7,5 og "ingen regel".** Bekræftet begge år.
- **Shorts slår longs.** Bekræftet, men svagere end først antaget.

## Hvad der IKKE holdt

- "Longs taber penge" gjaldt kun 2026 (−17,75 R). I 2025 gav longs **+11,62 R**.
- Begge sider gav **+86,43 R** i 2025 mod shorts alene +74,80 — mere i alt,
  men mindre pr. handel. Valget mellem dem er ikke afgjort.

## Kendt, uløst problem

`armed` i `engine/model.py` er **én global plads** for hele modellen. Rammer to
raids tæt på hinanden — samme bar, forskellige assets eller modsatte retninger —
overskriver det seneste det forrige, og det første forsvinder lydløst.

Det var uskadeligt i den oprindelige parmodel. Nu hvor ES og NQ kører med hvert
sit dagsbudget, er det forkert: de burde have hver sin arming-kø. Fundet
14. september på handlen 9. jan 2026 15:55, hvor en SHORT blev fortrængt af en
LONG på samme 15s-bar. **Ikke rettet** — det ændrer samtlige tal, så det skal
gøres bevidst og køres om fra bunden.

## Datakilder og krydstjek

| Kilde | Periode | Match mod naboer |
|---|---|---|
| TradingView 15s | 12. aug – 11. sep 2026 | — |
| NinjaTrader-ticks (ven) | 1. jan – 11. sep 2026 | 99,4 % / 99,2 % af barer mod TradingView |
| Databento OHLCV-1s | 2. jan 2025 – 27. feb 2026 | 96,2 % / 93,4 % mod NinjaTrader |

Databento afviger mest på **open og close** (typisk 1 tick). **High og low —
som EQ-raids afgøres på — matcher 99 %.** Målt på modellen: 34 af 36 handler
rammer samme sekund, 33 er identiske i udfald og R.

Parquet-data ligger ikke i repoet. Brug `tools/databento_konverter.py` til at
lave dem igen fra Databentos zip-filer.

## Næste skridt

3–4 års ekstra data på vej. Protokollen: udvikl på de ældste år, læg de seneste
væk, og kør dem igennem **én gang** til sidst uden at justere bagefter.
