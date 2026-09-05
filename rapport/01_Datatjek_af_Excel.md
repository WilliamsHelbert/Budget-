# Datatjek: `Betalingsbalance.xlsx`

## Kort svar: arket er i god stand

Jeg har regnet efter, og tallene hænger sammen indbyrdes. Det er det vigtigste
kvalitetstegn, fordi det betyder, at I har hentet én sammenhængende talserie fra
én kilde og ikke blandet årgange eller kilder sammen.

## Tjek 1: Vækstbidragene summer til BNP-væksten

Vægtene fra 2020-niveauerne (mia. USD): privat forbrug 54,0 pct. af BNP,
offentligt forbrug 21,0 pct., investeringer 25,6 pct., eksport 15,5 pct.,
import 15,8 pct.

Ganger man hver komponents realvækst med dens vægt og lægger nettoeksportens og
lagerinvesteringernes bidrag til, får man BNP-væksten:

| År | Privat forbr. | Off. forbr. | Investeringer | Nettoeksport | Lager | **Sum** | BNP i arket |
|----|---|---|---|---|---|---|---|
| 2021 | 0,22 | 0,73 | 0,05 | 1,00 | 0,20 | **2,20** | 2,2 |
| 2022 | 1,08 | 0,25 | −0,26 | −0,60 | 0,40 | **0,88** | 0,9 |
| 2023 | 0,38 | 0,10 | 0,43 | 0,80 | −0,20 | **1,52** | 1,7 |
| 2024 | 0,38 | −0,06 | 0,66 | 0,20 | −0,20 | **0,98** | 1,0 |
| 2025 | 0,38 | 0,00 | 0,72 | 0,10 | 0,00 | **1,19** | 1,2 |

*(alle tal i pct.point)*

Fire ud af fem år rammer inden for 0,02 pct.point. Kun 2023 afviger med 0,18
pct.point, og det er forventeligt: vægtene er låst til 2020, mens de reelle
vægte forskyder sig hen over årene. Det er ikke en fejl.

**Det kan I bruge i selve rapporten.** Tabellen ovenfor er ikke bare et tjek —
den er svaret på "hvad driver japansk vækst?". Lav den som figur.

## Tjek 2: Nettoeksportens bidrag stemmer med eksport- og importvæksten

| År | Beregnet ud fra X/M-vækst | I arket |
|----|---|---|
| 2021 | +1,04 | +1,0 |
| 2022 | −0,47 | −0,6 |
| 2023 | +0,58 | +0,8 |
| 2024 | +0,18 | +0,2 |
| 2025 | +0,06 | +0,1 |

Passer. Rækkerne er hentet fra samme opgørelse.

## Tjek 3: Forsyningsbalancen i niveauer

2 726 + 1 060 + 1 291 + 785 − 799 = **5 063** mod BNP på 5 051 mia. USD.
Differencen på 12 mia. USD (0,2 pct.) er lagerændringer og statistisk
diskrepans. Helt normalt.

---

# Fire ting I skal rette eller være opmærksomme på

### 1. 2024 og 2025 er fremskrivninger, ikke facit — og de er formentlig forældede

Tallene ser ud til at stamme fra en OECD Economic Outlook-årgang fra omkring
efteråret 2023 (BNP-vækst 1,0 pct. i 2024 og 1,2 pct. i 2025, inflation 2,6 og
2,0 pct.). I den årgang var 2024 og 2025 **prognoser**.

Japans faktisk realiserede BNP-vækst i 2024 endte markant lavere end 1,0 pct. —
tæt på nul. Skriver I i dag, står der altså en prognose i arket, hvor der findes
et realiseret tal.

**Hvad I skal gøre:**
- Slå den nyeste Economic Outlook op og hent 2024 og 2025 som realiserede tal.
- Behold gerne 2026 (og evt. 2027) som prognose — men marker det tydeligt i
  tabellen, fx med en lodret streg og en note: *"2026 er OECD's fremskrivning"*.
- Skriv **hvilken årgang** I bruger, med udgivelsesdato. Det er et krav i
  metodeafsnittet, at kilden kan genfindes.

Det her er ikke en detalje. Hvis censor kan se, at I kalder en prognose for et
resultat, går det ud over kildekritikken.

### 2. Filnavnet er misvisende

Filen hedder `Betalingsbalance.xlsx`, men betalingsbalancen er én række ud af 20.
Arket indeholder en hel forsyningsbalance plus nøgletal. Døb det om til noget i
retning af `Japan_noegletal_OECD.xlsx` — ellers roder I selv rundt i det om tre uger.

### 3. Der mangler tre talserier, som analysen ikke kan undvære

Lærebogens tabel 21.1 lister de nøgletal, en makroøkonomisk landeanalyse skal
bygge på. I har dækket økonomisk vækst, arbejdsløshed, betalingsbalance,
eksport/import, offentlige finanser og inflation. **I mangler løn og rente** —
og dertil valutakursen, som er helt central, når forløbet handler om handel og
konkurrenceevne.

| Række I skal tilføje | Hvorfor den er nødvendig | Hvor |
|---|---|---|
| **Nominel lønudvikling (pct.)** | Uden den kan I ikke dokumentere reallønsfaldet, som hele forbrugshistorien hviler på | OECD.Stat, "Average annual wages" / Japans Ministry of Health, Labour and Welfare |
| **Valutakurs JPY/USD + effektiv kronekurs** | Yenens fald er selve konkurrenceevne-mekanismen i jeres analyse | Bank of Japan, eller OECD "Exchange rates" |
| **Pengepolitisk rente + 10-årig statsobligationsrente** | Bærer hele gældsdiskussionen. Uden den kan I ikke vurdere risikoen ved 244 pct. gæld | Bank of Japan / OECD "Long-term interest rates" |

Overvej også en række for **befolkningsudvikling eller arbejdsstyrke**, da den
forklarer, hvorfor ledigheden kan være 2,4 pct. uden lønpres.

### 4. Formalia i selve arket

Lærebogens tommelfingerregler for tabeller: overskrift, enhed, kildehenvisning,
evt. forklaringsnote. Arket mangler kildehenvisningen. Skriv nederst:

> Kilde: OECD, *Economic Outlook* nr. XX, [måned] [år], [link].
> Note: Tal for 20XX og frem er OECD's fremskrivning.

Det skal med, hver gang tabellen optræder i rapporten — ikke bare én gang.
