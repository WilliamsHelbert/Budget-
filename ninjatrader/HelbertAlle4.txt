// =====================================================================
//  HelbertAlle4  -  alle fire modeller i EEN NinjaTrader 8-strategi
//  Swing (Hugin), Market Open (Munin), SMT (Gungner) og Vergence (Sleipner).
//  Bygget af Magnus' ODIN (OdinSamlet + OdinMotor + OdinSmtMotor) samlet i een fil,
//  saa den kan indsaettes direkte: New Strategy -> slet alt -> indsaet -> F5.
//  Kurverne til kurvefilteret ligger i koden - ingen mapper skal kopieres.
//
//  AENDRET I FORHOLD TIL ODIN (kun standardindstillinger, reglerne er de samme):
//    - 5 micros paa alle fire modeller
//    - Kurvefilter 30 paa baade SMT og Vergence
//    - Sender IKKE handler til ODIN-serveren (feltet er tomt)
//    - Egne navne (HelbertAlle4, mappen HelbertAlle4), saa den kan ligge ved siden af ODIN-filerne
// =====================================================================
// ODIN samlet - alle fire modeller i een NinjaTrader-strategi (unmanaged ordrestyring).
//   Hugin (Swing), Munin (Market Open), Gungner (SMT) og Sleipner (Vergence). Reglerne er de samme motorer som i de
//   fire enkelte strategier (OdinMotor.cs, OdinSmtMotor.cs) - kun ordrestyringen er ny.
//
// HVORFOR UNMANAGED
//   En strategi har een position i MNQ. Hver model har her sin egen virtuelle position med egne stop-, target- og
//   exit-ordrer. Kontoen ser kun summen (Swing short 2 + Market Open long 1 = short 1), men hver models stop og exit
//   virker for sig, saa resultatet er det samme som fire strategier ved siden af hinanden.
//
// REGLER FOR FLERE MODELLER (virker ogsaa i Strategy Analyzer, fordi alt sker i een strategi)
//   - Market Open lukkes, naar SMT eller Vergence gaar ind den modsatte vej.
//   - SMT og Vergence: har den ene et rigtigt trade aabent, og giver den anden signal modsat, bliver det nye papir.
//   - Alt samme vej holdes under "Maks micros i alt" (Lucid: 40). Halv stoerrelse samme vej kan slaas til (fra).
//   - Kurvefilter: 30 paa SMT og Vergence (startkurverne ligger i koden, gemmes i HelbertAlle4\kurve_<model>.csv).
//
// OPSAETNING som de enkelte strategier: diagram med MNQ (den der handles), 15 sekunder, "CME US Index Futures ETH",
// mindst 10 dage (foerste gang tilbage til 9/10-2026). NQ og ES laegges til automatisk ("##-##" ruller selv).
// Koer IKKE de enkelte strategier samtidig paa samme konto - saa handles der dobbelt.

using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript.Strategies.HelbertOdin;

namespace NinjaTrader.NinjaScript.Strategies
{
	public enum HelbertStoerrelse { Fast, ProcentAfKonto }

	public class HelbertAlle4 : Strategy
	{
		// ------------------------------------------------------------------ et ben pr. model
		private class Ben
		{
			public string Model, Navn;
			public bool Smt;                 // Gungner/Sleipner (SmtMotor) - ellers Hugin/Munin (Motor)
			public Motor M;
			public SmtMotor S;
			public string OrdreNavn;         // Hugin/Munin: motorens ordre ("SWING"/"MO")

			// virtuel position (fyldt) og ordrer
			public int Pos;                  // +antal long, -antal short, 0 flad
			public int Ventende;             // indsendt entry, endnu ikke fyldt
			public bool Kort;
			public double IndPris;
			public int IndAntal;
			public DateTime IndTid;
			public double StopPt;            // til risiko i loggen
			public double? StopPris, TpPris; // SMT/Vergence: faste priser fra motoren. Hugin/Munin: regnes ved fyld
			public double StopAfstand;       // Hugin/Munin: stop i point fra fyldprisen
			public long UdTid;
			public double BePt, BeLaas;
			public bool BeFlyttet;
			public string Oco = "";
			public Order Entry, Stop, Tp, Exit;
			public string ExitGrund = "";
			public double UdSum;             // sum af exitpris * antal til snitprisen
			public int UdAntal;
			public SmtHandel Rigtig;         // SMT/Vergence: handlen der er aaben rigtigt

			public int Nr;                   // nummer paa den aktuelle handel (i ordrenavnet)

			// kurvefilter: "dato tid" -> R. Kun handler foer den nye bruges, saa en backtest ikke ser kurvefilens fremtid
			public readonly SortedDictionary<string, double> Kurve = new SortedDictionary<string, double>(StringComparer.Ordinal);
			public string FilSidste = "";
		}

		// startkurver til kurvefilteret (alle papir-handler 2023 til og med 9/10-2026: dato;tid;R). Skrives til
		// Dokumenter\NinjaTrader 8\HelbertAlle4\kurve_<model>.csv foerste gang, derefter laeses og udvides filen.
		private const string StartKurveSmt = "2023-01-04;15:30:00;4.62\r\n2023-01-05;15:30:00;0.0\r\n2023-01-10;15:30:00;0.0\r\n2023-01-30;15:36:00;0.0\r\n2023-01-31;15:30:15;3.72\r\n2023-01-31;15:33:45;-1.32\r\n2023-02-01;15:30:30;0.0\r\n2023-02-07;15:30:30;0.0\r\n2023-02-15;15:42:30;0.0\r\n2023-02-15;15:54:15;0.0\r\n2023-02-21;15:30:00;-1.0\r\n2023-02-23;15:30:00;0.0\r\n2023-02-27;15:30:45;0.0\r\n2023-03-01;15:30:15;-1.0\r\n2023-03-20;15:30:15;-1.0\r\n2023-03-24;15:42:15;-1.35\r\n2023-03-27;15:30:45;-1.0\r\n2023-03-29;15:30:00;-1.0\r\n2023-03-31;15:30:15;4.5\r\n2023-04-26;15:30:30;0.0\r\n2023-05-01;15:30:45;0.0\r\n2023-05-02;15:30:00;0.0\r\n2023-05-03;15:30:15;-1.0\r\n2023-05-05;15:30:30;0.0\r\n2023-05-24;15:30:45;-1.0\r\n2023-05-26;15:30:00;0.0\r\n2023-05-30;15:30:15;0.0\r\n2023-06-01;15:30:45;-1.23\r\n2023-06-08;15:30:00;0.0\r\n2023-06-16;15:30:00;4.6\r\n2023-06-20;15:30:30;3.9\r\n2023-06-21;15:30:00;0.0\r\n2023-06-22;15:30:15;4.5\r\n2023-06-23;15:30:45;-1.2\r\n2023-06-26;15:30:15;0.0\r\n2023-06-28;15:30:45;0.0\r\n2023-07-11;15:30:00;-1.58\r\n2023-07-18;15:30:15;-1.0\r\n2023-07-21;15:30:15;-1.0\r\n2023-07-25;15:30:45;-1.27\r\n2023-07-28;15:30:15;-1.05\r\n2023-08-09;15:30:00;-1.0\r\n2023-08-16;15:30:45;0.0\r\n2023-08-18;15:30:00;0.0\r\n2023-08-18;15:33:15;0.0\r\n2023-08-21;15:30:30;-1.18\r\n2023-09-05;15:30:30;0.0\r\n2023-09-05;15:42:45;0.0\r\n2023-09-06;15:30:00;0.0\r\n2023-09-08;15:30:15;6.25\r\n2023-09-18;15:30:30;6.88\r\n2023-09-26;15:30:15;0.0\r\n2023-10-02;15:30:15;0.0\r\n2023-10-05;15:42:45;0.0\r\n2023-10-09;15:30:15;-1.4\r\n2023-10-18;15:30:00;0.0\r\n2023-10-23;15:30:30;-1.0\r\n2023-10-24;15:33:15;4.9\r\n2023-10-30;15:30:15;0.0\r\n2023-11-01;15:30:15;0.0\r\n2023-11-03;15:30:15;-1.32\r\n2023-11-14;15:30:45;0.0\r\n2023-12-06;15:30:00;7.5\r\n2023-12-12;15:30:15;-1.42\r\n2023-12-13;15:30:15;0.0\r\n2023-12-14;15:30:00;0.0\r\n2023-12-18;15:30:30;0.0\r\n2023-12-19;15:30:15;0.0\r\n2023-12-20;15:30:15;5.4\r\n2023-12-28;15:30:30;7.5\r\n2024-01-04;15:30:00;0.0\r\n2024-01-05;15:30:00;-1.27\r\n2024-01-19;15:30:15;-1.0\r\n2024-01-22;15:42:45;-1.0\r\n2024-01-26;15:30:00;-1.72\r\n2024-01-29;15:30:15;0.0\r\n2024-01-29;15:33:45;-1.0\r\n2024-01-31;15:30:15;0.0\r\n2024-02-01;15:30:15;0.0\r\n2024-02-05;15:30:00;0.0\r\n2024-02-07;15:30:00;0.0\r\n2024-02-14;15:30:15;-1.35\r\n2024-02-15;15:33:00;0.0\r\n2024-02-22;15:30:15;0.0\r\n2024-03-07;15:30:00;-1.42\r\n2024-03-14;15:30:00;0.0\r\n2024-03-15;15:30:00;-2.78\r\n2024-03-18;15:30:00;-1.48\r\n2024-03-20;15:30:00;-1.68\r\n2024-03-26;15:30:00;-1.48\r\n2024-04-01;15:30:00;-1.0\r\n2024-04-03;15:30:15;-1.0\r\n2024-04-09;15:30:00;-2.2\r\n2024-04-12;15:30:30;0.0\r\n2024-04-16;15:30:15;0.0\r\n2024-04-18;15:30:15;-1.78\r\n2024-04-22;15:30:15;0.0\r\n2024-04-23;15:30:15;0.0\r\n2024-05-08;15:30:00;0.0\r\n2024-05-09;15:30:00;0.0\r\n2024-05-15;15:30:00;0.0\r\n2024-05-17;15:30:00;-1.0\r\n2024-05-22;15:33:15;0.0\r\n2024-05-24;15:30:45;0.0\r\n2024-05-29;15:33:15;-1.0\r\n2024-05-31;15:30:00;-1.0\r\n2024-06-04;15:30:15;0.0\r\n2024-06-05;15:51:15;0.0\r\n2024-06-18;15:30:00;-1.0\r\n2024-06-27;15:30:30;-1.0\r\n2024-07-01;15:30:45;0.0\r\n2024-07-02;15:30:15;-1.12\r\n2024-07-09;15:33:15;-1.0\r\n2024-07-11;15:30:15;-1.0\r\n2024-07-19;15:30:00;-1.02\r\n2024-07-22;15:33:00;-1.32\r\n2024-07-23;15:30:30;0.0\r\n2024-07-24;15:33:30;-2.58\r\n2024-07-25;15:30:15;-1.55\r\n2024-07-30;15:30:15;0.0\r\n2024-07-31;15:30:00;0.0\r\n2024-08-01;15:30:15;-1.92\r\n2024-08-07;15:30:00;-1.32\r\n2024-08-09;15:30:45;-2.25\r\n2024-08-19;15:30:00;-1.15\r\n2024-08-20;15:42:15;0.0\r\n2024-08-22;15:30:00;-1.0\r\n2024-08-27;15:30:45;0.0\r\n2024-08-29;15:30:00;-2.0\r\n2024-09-09;15:30:00;-2.48\r\n2024-09-10;15:30:15;0.0\r\n2024-10-07;15:45:45;0.0\r\n2024-10-10;15:30:00;0.0\r\n2024-10-11;15:54:15;-1.0\r\n2024-10-14;15:30:30;0.0\r\n2024-10-18;15:45:30;-1.32\r\n2024-11-12;15:30:15;-1.0\r\n2024-11-13;15:30:15;-1.45\r\n2024-12-02;15:30:00;-1.6\r\n2024-12-06;15:30:45;3.6\r\n2024-12-11;15:30:00;-1.0\r\n2024-12-19;15:30:15;0.0\r\n2024-12-23;15:33:30;0.0\r\n2024-12-31;15:30:15;-2.55\r\n2025-01-06;15:30:15;-1.5\r\n2025-01-08;15:54:00;0.0\r\n2025-01-13;15:54:30;-1.58\r\n2025-01-21;15:30:15;7.5\r\n2025-01-23;15:30:15;-1.0\r\n2025-01-28;15:36:00;-1.02\r\n2025-02-03;15:30:30;5.38\r\n2025-02-04;15:30:15;-1.0\r\n2025-02-04;15:36:15;-1.18\r\n2025-02-11;15:36:45;0.0\r\n2025-02-12;15:30:15;0.0\r\n2025-02-13;15:30:15;5.78\r\n2025-02-14;15:30:00;0.0\r\n2025-02-18;15:30:45;-1.65\r\n2025-02-27;15:30:15;-1.58\r\n2025-03-04;15:36:45;-2.48\r\n2025-03-10;15:30:15;0.0\r\n2025-03-13;15:54:45;-1.42\r\n2025-03-14;15:30:00;5.42\r\n2025-03-14;15:33:45;0.0\r\n2025-03-26;15:30:00;0.0\r\n2025-03-28;15:30:15;-1.15\r\n2025-03-31;15:30:00;-2.82\r\n2025-04-01;15:30:15;5.38\r\n2025-04-15;15:33:30;0.0\r\n2025-04-23;15:30:15;-2.42\r\n2025-05-05;15:42:15;7.5\r\n2025-05-09;15:30:45;-1.0\r\n2025-05-14;15:30:45;-1.0\r\n2025-05-20;15:30:15;-1.38\r\n2025-05-29;15:30:45;-1.12\r\n2025-06-04;15:30:00;-1.0\r\n2025-06-09;15:30:00;-1.72\r\n2025-06-10;15:30:45;0.0\r\n2025-06-13;15:51:15;0.0\r\n2025-06-16;15:30:15;7.5\r\n2025-06-20;15:30:15;3.62\r\n2025-06-23;15:33:45;-1.98\r\n2025-07-07;15:30:45;4.28\r\n2025-07-15;15:30:30;7.4\r\n2025-07-16;15:30:00;-1.0\r\n2025-07-16;15:42:15;-1.88\r\n2025-07-17;15:33:45;0.0\r\n2025-07-25;15:30:15;0.0\r\n2025-07-30;15:30:15;-1.0\r\n2025-08-01;15:30:00;0.0\r\n2025-08-06;15:30:45;6.0\r\n2025-08-11;15:30:15;0.0\r\n2025-08-13;15:30:00;0.0\r\n2025-08-14;15:30:15;0.0\r\n2025-08-18;15:30:15;-1.0\r\n2025-08-19;15:42:15;7.5\r\n2025-08-20;15:30:15;6.5\r\n2025-08-29;15:30:00;-1.0\r\n2025-09-02;15:30:30;-2.05\r\n2025-09-03;15:30:00;0.0\r\n2025-09-09;15:30:15;0.0\r\n2025-09-25;15:30:30;-1.02\r\n2025-09-29;15:30:00;5.1\r\n2025-09-30;15:30:15;5.98\r\n2025-10-01;15:36:30;-1.08\r\n2025-10-03;15:30:30;0.0\r\n2025-10-08;15:30:00;7.5\r\n2025-10-10;15:30:30;4.15\r\n2025-10-16;15:30:00;4.55\r\n2025-10-21;15:30:15;0.0\r\n2025-10-30;15:30:00;7.5\r\n2025-11-04;15:42:00;-1.0\r\n2025-11-06;15:30:00;-2.48\r\n2025-11-13;15:30:15;4.45\r\n2025-11-21;15:54:45;7.5\r\n2025-12-02;15:30:00;-1.18\r\n2025-12-02;15:33:45;-1.3\r\n2025-12-03;15:30:00;0.0\r\n2025-12-16;15:51:45;0.0\r\n2025-12-22;15:30:15;0.0\r\n2026-01-06;15:30:30;0.0\r\n2026-01-07;15:30:30;0.0\r\n2026-01-08;15:30:00;7.5\r\n2026-01-15;15:45:15;7.5\r\n2026-01-21;15:30:15;0.0\r\n2026-01-22;15:30:30;-1.0\r\n2026-01-30;15:30:45;7.5\r\n2026-02-19;15:30:15;3.72\r\n2026-02-23;15:42:15;-1.75\r\n2026-02-24;15:30:00;-2.4\r\n2026-02-26;15:30:15;-1.0\r\n2026-02-27;15:42:15;-1.0\r\n2026-03-05;15:30:45;-2.33\r\n2026-03-27;15:30:45;7.3\r\n2026-03-30;15:30:15;-1.95\r\n2026-03-30;15:36:15;-1.05\r\n2026-04-02;15:54:30;-1.52\r\n2026-04-08;15:33:30;0.0\r\n2026-04-22;15:30:00;5.05\r\n2026-04-22;15:33:45;-1.82\r\n2026-05-04;15:42:15;0.0\r\n2026-05-12;15:45:00;4.44\r\n2026-05-14;15:30:15;-2.02\r\n2026-05-22;15:30:15;7.5\r\n2026-05-26;15:36:15;7.5\r\n2026-06-02;15:33:30;-1.02\r\n2026-07-02;15:30:15;7.5\r\n2026-07-02;15:42:30;-1.0\r\n2026-07-06;15:51:45;3.98\r\n2026-07-13;15:45:15;-1.42\r\n2026-07-15;15:30:15;0.0\r\n2026-08-17;15:33:15;0.0\r\n2026-08-28;15:30:15;-1.75\r\n2026-09-01;15:30:00;0.0\r\n2026-09-09;15:30:00;-2.12\r\n2026-09-10;15:30:15;-2.8\r\n2026-09-16;15:36:15;0.0\r\n2026-10-05;15:45:30;6.31\r\n2026-10-06;15:30:15;-1.3\r\n2026-10-09;15:30:15;-1.72\r\n";          // 260 handler
		private const string StartKurveVergence = "2023-01-03;15:39:30;-1.0\r\n2023-01-05;15:32:15;-2.17\r\n2023-01-06;15:30:45;-1.2\r\n2023-01-23;15:30:15;0.0\r\n2023-01-25;15:30:15;-1.0\r\n2023-02-01;15:30:30;0.0\r\n2023-02-01;15:34:45;-1.0\r\n2023-02-07;15:31:30;0.0\r\n2023-02-09;15:30:00;5.48\r\n2023-02-17;15:35:15;4.82\r\n2023-02-17;15:41:00;0.0\r\n2023-02-22;15:30:15;0.0\r\n2023-03-06;15:34:15;0.0\r\n2023-03-08;15:32:15;5.68\r\n2023-03-09;15:35:00;-1.0\r\n2023-03-15;15:34:15;-1.1\r\n2023-03-16;15:32:30;0.0\r\n2023-03-17;15:40:15;0.0\r\n2023-03-27;15:30:45;-1.0\r\n2023-03-27;15:50:45;7.5\r\n2023-03-31;15:30:15;4.5\r\n2023-04-20;15:30:00;7.5\r\n2023-05-01;15:30:45;0.0\r\n2023-05-01;15:34:45;-1.0\r\n2023-05-11;15:30:15;0.0\r\n2023-05-23;15:51:30;0.0\r\n2023-06-14;15:33:00;-1.0\r\n2023-06-15;15:31:15;0.0\r\n2023-06-20;15:30:30;3.9\r\n2023-06-26;15:44:15;-1.0\r\n2023-07-07;15:30:15;-1.25\r\n2023-07-12;15:33:30;-1.0\r\n2023-07-31;15:45:30;-1.0\r\n2023-08-07;15:31:00;5.78\r\n2023-08-28;15:34:15;-1.0\r\n2023-08-29;15:30:45;0.0\r\n2023-09-05;15:30:30;0.0\r\n2023-09-11;15:31:15;0.0\r\n2023-09-12;15:42:30;0.0\r\n2023-09-18;15:30:30;6.88\r\n2023-09-19;15:31:15;0.0\r\n2023-09-21;15:30:00;-1.0\r\n2023-09-21;15:53:30;-1.0\r\n2023-09-25;15:30:15;-1.42\r\n2023-09-26;15:31:45;0.0\r\n2023-09-27;15:30:00;0.0\r\n2023-09-29;15:30:15;0.0\r\n2023-10-03;15:30:45;0.0\r\n2023-10-23;15:30:30;-1.0\r\n2023-10-30;15:30:15;0.0\r\n2023-10-31;15:30:30;7.5\r\n2023-11-08;15:31:15;-1.3\r\n2023-11-14;15:30:45;0.0\r\n2023-11-20;15:36:30;0.0\r\n2023-11-22;15:56:30;0.0\r\n2023-11-28;15:31:30;-1.3\r\n2023-12-01;15:30:00;0.0\r\n2023-12-08;15:30:15;-2.22\r\n2023-12-08;15:44:15;0.0\r\n2023-12-14;15:45:30;-1.0\r\n2023-12-20;15:36:30;-1.0\r\n2023-12-26;15:31:30;0.0\r\n2023-12-29;15:35:45;0.0\r\n2024-01-03;15:30:15;0.0\r\n2024-01-16;15:30:00;-1.52\r\n2024-01-22;15:35:15;6.4\r\n2024-02-12;15:34:30;0.0\r\n2024-02-14;15:30:15;-1.35\r\n2024-02-14;15:31:30;0.0\r\n2024-02-20;15:32:45;6.58\r\n2024-02-22;15:30:15;0.0\r\n2024-02-22;15:32:15;0.0\r\n2024-02-26;15:30:00;-1.05\r\n2024-02-26;15:33:30;5.1\r\n2024-03-14;15:33:00;0.0\r\n2024-03-15;15:31:15;-2.52\r\n2024-03-20;15:30:45;4.28\r\n2024-04-05;15:48:15;-1.4\r\n2024-04-09;15:50:15;0.0\r\n2024-04-16;15:30:15;0.0\r\n2024-04-18;15:30:15;-1.78\r\n2024-04-29;15:30:15;-1.88\r\n2024-05-02;15:36:45;0.0\r\n2024-05-02;15:40:15;0.0\r\n2024-05-13;15:35:00;0.0\r\n2024-05-13;15:40:30;-1.0\r\n2024-05-20;15:30:45;4.58\r\n2024-05-22;15:30:15;-1.0\r\n2024-05-24;15:35:15;-1.72\r\n2024-06-03;15:30:15;0.0\r\n2024-06-04;15:30:15;0.0\r\n2024-06-10;15:33:15;0.0\r\n2024-06-17;15:33:30;-1.0\r\n2024-06-17;15:35:15;0.0\r\n2024-06-25;15:30:30;-1.12\r\n2024-06-26;15:30:15;-1.0\r\n2024-07-15;15:40:30;-1.0\r\n2024-07-15;15:46:45;6.15\r\n2024-07-19;15:32:15;0.0\r\n2024-07-19;15:41:15;3.9\r\n2024-07-23;15:40:45;0.0\r\n2024-08-09;15:39:30;7.5\r\n2024-08-12;15:33:45;0.0\r\n2024-08-15;15:32:15;0.0\r\n2024-08-29;15:35:15;-1.18\r\n2024-09-05;15:33:45;0.0\r\n2024-09-09;15:31:30;-1.15\r\n2024-09-16;15:34:00;-1.2\r\n2024-09-17;15:33:00;4.68\r\n2024-09-19;15:30:00;0.0\r\n2024-10-16;15:33:00;-1.08\r\n2024-10-17;15:34:45;-1.0\r\n2024-10-22;15:30:30;0.0\r\n2024-10-23;15:31:30;-2.3\r\n2024-10-30;15:31:15;-2.75\r\n2024-11-07;15:30:30;-1.0\r\n2024-11-12;15:30:15;-1.0\r\n2024-11-15;15:33:30;-1.4\r\n2024-11-26;15:35:30;-1.2\r\n2024-12-04;15:30:15;0.0\r\n2024-12-06;15:34:30;0.0\r\n2024-12-31;15:30:15;-2.55\r\n2025-01-02;15:34:00;-2.15\r\n2025-01-02;15:40:15;0.0\r\n2025-01-03;15:30:30;-1.0\r\n2025-01-10;15:30:00;0.0\r\n2025-01-10;15:48:15;0.0\r\n2025-01-13;15:30:00;0.0\r\n2025-01-21;15:41:15;4.8\r\n2025-01-22;15:30:00;-1.55\r\n2025-01-28;15:30:00;-1.0\r\n2025-02-04;15:30:45;5.38\r\n2025-02-07;15:30:15;4.53\r\n2025-02-18;15:30:00;-1.0\r\n2025-02-20;15:47:45;0.0\r\n2025-02-27;15:44:15;0.0\r\n2025-02-27;15:55:15;-1.88\r\n2025-02-28;15:30:15;-2.1\r\n2025-03-03;15:57:00;-1.6\r\n2025-03-11;15:30:00;-2.33\r\n2025-03-14;15:37:30;-1.0\r\n2025-03-18;15:31:00;0.0\r\n2025-03-26;15:34:15;0.0\r\n2025-03-27;15:30:15;0.0\r\n2025-04-02;15:31:00;0.0\r\n2025-04-04;15:42:00;-1.5\r\n2025-04-21;15:30:15;-1.32\r\n2025-04-21;15:37:15;0.0\r\n2025-04-22;15:30:00;0.0\r\n2025-04-23;15:32:15;-1.42\r\n2025-04-28;15:31:15;0.0\r\n2025-04-29;15:30:15;-1.92\r\n2025-04-29;15:50:15;0.0\r\n2025-05-06;15:30:00;0.0\r\n2025-05-08;15:30:15;-2.35\r\n2025-05-14;15:35:15;7.5\r\n2025-05-15;15:34:45;7.5\r\n2025-05-19;15:36:45;-1.0\r\n2025-05-20;15:35:15;-1.0\r\n2025-05-27;15:30:15;0.0\r\n2025-05-27;15:36:15;-1.0\r\n2025-05-30;15:30:00;7.5\r\n2025-06-06;15:33:30;0.0\r\n2025-06-09;15:30:00;-1.72\r\n2025-06-10;15:30:45;0.0\r\n2025-06-16;15:32:15;0.0\r\n2025-06-23;15:33:45;-1.98\r\n2025-06-24;15:30:15;3.58\r\n2025-06-26;15:30:30;3.58\r\n2025-06-27;15:30:15;-1.55\r\n2025-07-01;15:30:15;0.0\r\n2025-07-01;15:51:45;0.0\r\n2025-07-14;15:30:15;-1.35\r\n2025-07-16;15:30:45;5.65\r\n2025-07-25;15:53:30;0.0\r\n2025-07-30;15:31:00;-1.0\r\n2025-08-06;15:30:45;6.0\r\n2025-08-07;15:34:30;0.0\r\n2025-08-14;15:30:15;0.0\r\n2025-08-18;15:30:15;-1.0\r\n2025-08-19;15:30:45;7.5\r\n2025-08-20;15:30:15;6.5\r\n2025-08-20;15:46:15;-1.05\r\n2025-08-28;15:31:00;-1.65\r\n2025-08-28;15:52:15;0.0\r\n2025-09-09;15:30:15;0.0\r\n2025-09-24;15:30:15;4.18\r\n2025-09-25;15:30:30;0.0\r\n2025-09-25;15:31:15;0.0\r\n2025-09-30;15:30:15;5.98\r\n2025-10-02;15:43:45;-1.38\r\n2025-10-14;15:42:30;-1.08\r\n2025-10-17;15:31:15;0.0\r\n2025-10-31;15:39:45;-1.0\r\n2025-11-03;15:31:15;-1.95\r\n2025-11-05;15:35:30;-2.3\r\n2025-11-13;15:31:30;0.0\r\n2025-11-18;15:30:45;4.15\r\n2025-11-24;15:30:30;7.5\r\n2025-11-26;15:31:00;-2.42\r\n2025-12-15;15:34:15;-1.85\r\n2025-12-15;15:56:30;-1.2\r\n2025-12-22;15:30:15;0.0\r\n2025-12-30;15:50:30;0.0\r\n2025-12-30;15:55:30;-1.0\r\n2025-12-31;15:30:15;0.0\r\n2026-01-07;15:30:30;0.0\r\n2026-01-21;15:51:15;-1.68\r\n2026-01-27;15:30:45;0.0\r\n2026-01-30;15:30:45;7.5\r\n2026-02-06;15:34:15;0.0\r\n2026-02-13;15:41:00;-1.88\r\n2026-02-19;15:30:15;3.72\r\n2026-02-24;15:30:30;-1.58\r\n2026-02-24;15:45:15;-1.18\r\n2026-02-27;15:43:45;4.42\r\n2026-03-05;15:30:45;-2.33\r\n2026-03-05;15:35:45;-1.32\r\n2026-03-30;15:30:15;-1.95\r\n2026-03-30;15:58:45;7.5\r\n2026-04-06;15:37:30;0.0\r\n2026-04-09;15:30:15;0.0\r\n2026-04-15;15:30:15;-2.65\r\n2026-04-28;15:38:30;0.0\r\n2026-05-12;15:59:30;-1.25\r\n2026-05-18;15:30:00;-2.98\r\n2026-05-22;15:33:15;0.0\r\n2026-05-27;15:38:15;0.0\r\n2026-06-11;15:54:15;7.5\r\n2026-06-26;15:57:30;-2.5\r\n2026-07-02;15:30:15;7.5\r\n2026-07-06;15:34:45;6.88\r\n2026-07-09;15:32:15;7.5\r\n2026-07-10;15:31:15;-1.8\r\n2026-07-15;15:30:15;0.0\r\n2026-07-16;15:42:15;-1.1\r\n2026-07-20;15:35:45;-1.9\r\n2026-07-20;15:59:00;-1.0\r\n2026-07-27;15:31:15;0.0\r\n2026-07-31;15:45:45;-2.55\r\n2026-08-12;15:30:00;7.5\r\n2026-08-21;15:33:15;0.0\r\n2026-08-25;15:30:15;0.0\r\n2026-09-01;15:31:15;-2.08\r\n2026-09-09;15:34:30;-1.78\r\n2026-10-09;15:30:15;-1.72\r\n";     // 246 handler

		private Ben hugin, munin, gungner, sleipner;
		private Ben[] ben;
		private TimeZoneInfo newYork;
		private readonly DateTime epoke = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);
		private int ocoTaeller;

		// NQ-bar der venter paa ES-baren med samme tid
		private bool venter, dataAdvaret;
		private DateTime ventSlut;
		private double vo, vh, vl, vc;
		private DateTime esSlut = DateTime.MinValue;
		private double eo, eh, el, ec;

		// log
		private static readonly HttpClient http = new HttpClient();
		private static readonly CultureInfo dk = CultureInfo.GetCultureInfo("da-DK");
		private volatile string sidsteFejl;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Name = "HelbertAlle4";
				Description = "ODIN: Swing, Market Open, SMT og Vergence i een strategi med regler for flere modeller paa en gang.";
				Calculate = Calculate.OnBarClose;
				IsUnmanaged = true;
				IsExitOnSessionCloseStrategy = true;
				ExitOnSessionCloseSeconds = 30;
				BarsRequiredToTrade = 0;
				RealtimeErrorHandling = RealtimeErrorHandling.IgnoreAllErrors;
				IgnoreOverfill = true;
				TraceOrders = false;

				NqInstrument = "NQ ##-##";
				EsInstrument = "ES ##-##";
				Stoerrelse = HelbertStoerrelse.Fast;
				KontoStart = 7692;
				BrugKontoSaldo = true;
				SwingTil = true; SwingAntal = 5; SwingRisikoPct = 2.5;
				MoTil = true; MoAntal = 5; MoRisikoPct = 1.5;
				SmtTil = true; SmtAntal = 5; SmtRisikoPct = 2.0; SmtKurve = 30;
				VergenceTil = true; VergenceAntal = 5; VergenceRisikoPct = 2.0; VergenceKurve = 30;
				LukMoVedModsat = true;
				PapirVedModsat = true;
				HalverSammeVej = false;
				MaksIAlt = 40;
				DiscordTradeLog = "";
				SkrivLogfil = true;
				OdinServer = "";
				OdinToken = "";
			}
			else if (State == State.Configure)
			{
				BarsPeriod p = new BarsPeriod { BarsPeriodType = BarsPeriodType.Second, Value = 15 };
				AddDataSeries(NqInstrument, p, "CME US Index Futures ETH");     // BarsArray[1]
				AddDataSeries(EsInstrument, p, "CME US Index Futures ETH");     // BarsArray[2]
			}
			else if (State == State.DataLoaded)
			{
				newYork = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
				hugin = new Ben { Model = "Hugin", Navn = "Swing", M = new Motor(MotorIndstillinger.PlanSwing()), OrdreNavn = "SWING" };
				munin = new Ben { Model = "Munin", Navn = "Market Open", M = new Motor(MotorIndstillinger.MarketOpen()), OrdreNavn = "MO" };
				gungner = new Ben { Model = "Gungner", Navn = "SMT", Smt = true, S = new SmtMotor(false) };
				sleipner = new Ben { Model = "Sleipner", Navn = "Vergence", Smt = true, S = new SmtMotor(true) };
				ben = new Ben[] { hugin, munin, gungner, sleipner };
				LaesKurve(gungner);
				LaesKurve(sleipner);
			}
			else if (State == State.Realtime)
			{
				// ordrer fra den historiske gennemkoersel skal skiftes til deres realtime-udgave
				foreach (Ben b in ben)
				{
					if (b.Entry != null) b.Entry = GetRealtimeOrder(b.Entry);
					if (b.Stop != null) b.Stop = GetRealtimeOrder(b.Stop);
					if (b.Tp != null) b.Tp = GetRealtimeOrder(b.Tp);
					if (b.Exit != null) b.Exit = GetRealtimeOrder(b.Exit);
				}
			}
		}

		private long Unix(DateTime ntTid)
		{
			return (long)(TimeZoneInfo.ConvertTimeToUtc(ntTid, NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo) - epoke).TotalSeconds;
		}

		// ------------------------------------------------------------------ data: NQ og ES parres paa tid
		protected override void OnBarUpdate()
		{
			if (BarsInProgress == 0)
			{
				// uden NQ- eller ES-barer goer strategien ingenting - sig det, i stedet for at tie
				if (!dataAdvaret && CurrentBars[0] == 2000 && (CurrentBars[1] < 0 || CurrentBars[2] < 0))
				{
					dataAdvaret = true;
					Print(string.Format("ODIN: 2000 barer paa {0}, men {1} har {2} barer og {3} har {4}. Tjek NQ-/ES-instrument i indstillingerne og at der er data.",
						Instrument.FullName, NqInstrument, CurrentBars[1] + 1, EsInstrument, CurrentBars[2] + 1));
				}
				return;
			}
			if (CurrentBars[1] < 0 || CurrentBars[2] < 0)
				return;
			DateTime slut = Times[BarsInProgress][0];
			if (BarsInProgress == 1)
			{
				if (venter && ventSlut < slut)
					Behandl(ventSlut, false);
				venter = true; ventSlut = slut;
				vo = Opens[1][0]; vh = Highs[1][0]; vl = Lows[1][0]; vc = Closes[1][0];
				if (esSlut == slut)
					Behandl(slut, true);
			}
			else if (BarsInProgress == 2)
			{
				if (venter && ventSlut < slut)
					Behandl(ventSlut, false);
				esSlut = slut;
				eo = Opens[2][0]; eh = Highs[2][0]; el = Lows[2][0]; ec = Closes[2][0];
				long te = Unix(slut.AddSeconds(-15));
				gungner.S.PaaEs(te, eo, eh, el, ec);
				sleipner.S.PaaEs(te, eo, eh, el, ec);
				if (venter && ventSlut == slut)
					Behandl(slut, true);
			}
		}

		private void Behandl(DateTime slut, bool harE)
		{
			venter = false;
			if (sidsteFejl != null) { Print(Name + " log-fejl: " + sidsteFejl); sidsteFejl = null; }
			DateTime start = slut.AddSeconds(-15);
			DateTime ny = TimeZoneInfo.ConvertTime(start, NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo, newYork);
			long t = Unix(start);

			// 1) Hugin og Munin: tidsudgang og BE paa aabne handler (foer motoren ser baren, som i Python)
			foreach (Ben b in new Ben[] { hugin, munin })
			{
				if (b.Pos == 0) continue;
				if (t + 15 >= b.UdTid)
					Luk(b, "tid", slut);
				else if (b.BePt > 0 && !b.BeFlyttet)
				{
					double bedst = b.Kort ? b.IndPris - vl : vh - b.IndPris;
					if (bedst >= b.BePt)
						FlytStop(b, b.Kort ? b.IndPris - b.BeLaas : b.IndPris + b.BeLaas, slut);
				}
			}

			// 2) motorerne, i raekkefoelgen Hugin, Munin, Gungner, Sleipner
			foreach (MotorOrdre od in hugin.M.PaaBar(t, ny, vo, vh, vl, vc, harE, eo, eh, el, ec))
				if (od.Navn == "SWING" && SwingTil) RavnInd(hugin, od, slut, SwingAntal, SwingRisikoPct);
			foreach (MotorOrdre od in munin.M.PaaBar(t, ny, vo, vh, vl, vc, harE, eo, eh, el, ec))
				if (od.Navn == "MO" && MoTil) RavnInd(munin, od, slut, MoAntal, MoRisikoPct);
			foreach (Ben b in new Ben[] { gungner, sleipner })
				foreach (SmtBegivenhed e in b.S.PaaNq(t, ny, vo, vh, vl, vc))
					SmtBegivenhed(b, e, slut);
		}

		// ------------------------------------------------------------------ Hugin / Munin
		private void RavnInd(Ben b, MotorOrdre od, DateTime slut, int antalFast, double pct)
		{
			if (b.Pos != 0 || b.Ventende > 0) return;
			// rv5 kraever 6 hele RTH-dage. Uden den slipper motoren alt igennem, saa de foerste dage af en backtest handles ikke
			if (!b.M.Rv5.HasValue)
			{
				Print(string.Format("{0} ODIN {1}: sprunget over - rv5 kendes ikke endnu (for faa dage indlaest)", slut, b.Navn));
				return;
			}
			string note;
			int antal = Juster(b, Beregn(od.StopPt, antalFast, pct), od.Kort, out note);
			if (antal < 1) { Print(string.Format("{0} ODIN {1}: sprunget over{2}", slut, b.Navn, note)); return; }
			b.StopAfstand = od.StopPt;
			b.StopPt = od.StopPt;
			b.StopPris = null;
			b.TpPris = null;
			b.UdTid = od.UdTid;
			b.BePt = od.BePt;
			b.BeLaas = od.BeLaas;
			GaaInd(b, od.Kort, antal);
			Print(string.Format("{0} ODIN {1} {2} x{3}{4}", slut, b.Navn, od.Kort ? "SHORT" : "LONG", antal, note));
		}

		// ------------------------------------------------------------------ Gungner / Sleipner
		private void SmtBegivenhed(Ben b, SmtBegivenhed e, DateTime slut)
		{
			SmtHandel x = e.Handel;
			switch (e.Type)
			{
				case SmtType.Lukket:
					TilKurve(b, x, x.R ?? 0);
					if (b.Rigtig == x && b.Pos != 0) Luk(b, "papir lukket", slut);      // stop/TP burde allerede have lukket den
					if (b.Rigtig == x) b.Rigtig = null;
					break;
				case SmtType.Afloest:
					TilKurve(b, x, 0);
					break;
				case SmtType.Be:
					if (b.Rigtig == x && b.Pos != 0 && !b.BeFlyttet) FlytStop(b, b.IndPris, slut);
					break;
				case SmtType.Ugyldig:
					Print(string.Format("{0} ODIN {1} {2} {3}: {4}", slut, b.Navn, x.Kort ? "SHORT" : "LONG", x.Niveau, x.Status));
					break;
				case SmtType.Ny:
					SmtNy(b, x, slut);
					break;
			}
		}

		private void SmtNy(Ben b, SmtHandel x, DateTime slut)
		{
			bool til = b == gungner ? SmtTil : VergenceTil;
			int kurve = b == gungner ? SmtKurve : VergenceKurve;
			Ben anden = b == gungner ? sleipner : gungner;
			bool ok = til && KurveOk(b, kurve, x.Dato + " " + x.Tid);
			bool modsat = PapirVedModsat && anden.Pos != 0 && (anden.Pos < 0) != x.Kort;
			string hvorfor = !til ? "slaaet fra" : !ok ? "papir (kurvefilter)" : modsat ? "papir (" + anden.Navn + " har et modsat trade aabent)" : "RIGTIG";
			Print(string.Format(CultureInfo.InvariantCulture, "{0} ODIN {1} {2} {3} entry {4} SL {5} TP {6} - {7}", slut, b.Navn,
				x.Kort ? "SHORT" : "LONG", x.Niveau, x.Entry, x.Sl, x.Tp, hvorfor));
			if (!ok || modsat)
			{
				if (b.Pos != 0 || b.Ventende > 0) Luk(b, "afloest", slut);           // den gamle er afloest, den nye er papir
				b.Rigtig = null;
				return;
			}
			// Market Open lukkes, naar SMT/Vergence gaar ind den modsatte vej
			if (LukMoVedModsat && munin.Pos != 0 && (munin.Pos < 0) != x.Kort)
			{
				Luk(munin, "modsat " + b.Navn, slut);
				Print(string.Format("{0} ODIN Market Open lukket - {1} gik ind den modsatte vej", slut, b.Navn));
			}
			double stopPt = Math.Abs(x.Entry - x.Sl.Value);
			if (b.Pos != 0 && (b.Pos < 0) == x.Kort)
			{
				// afloest samme vej: positionen fortsaetter med nyt SL og TP
				b.Rigtig = x;
				b.StopPris = x.Sl.Value; b.TpPris = x.Tp.Value; b.StopPt = stopPt; b.BeFlyttet = false;
				if (b.Stop != null) ChangeOrder(b.Stop, Math.Abs(b.Pos), 0, x.Sl.Value);
				if (b.Tp != null) ChangeOrder(b.Tp, Math.Abs(b.Pos), x.Tp.Value, 0);
				return;
			}
			if (b.Pos != 0 || b.Ventende > 0) Luk(b, "afloest", slut);                 // modsat vej: luk den gamle
			string note;
			int antal = Juster(b, Beregn(stopPt, b == gungner ? SmtAntal : VergenceAntal, b == gungner ? SmtRisikoPct : VergenceRisikoPct), x.Kort, out note);
			if (antal < 1) { Print(string.Format("{0} ODIN {1}: kun papir{2}", slut, b.Navn, note)); b.Rigtig = null; return; }
			b.Rigtig = x;
			b.StopPris = x.Sl.Value; b.TpPris = x.Tp.Value; b.StopPt = stopPt; b.StopAfstand = 0;
			b.UdTid = long.MaxValue; b.BePt = 0;
			GaaInd(b, x.Kort, antal);
			if (note.Length > 0) Print(string.Format("{0} ODIN {1}: x{2}{3}", slut, b.Navn, antal, note));
		}

		// ------------------------------------------------------------------ kurvefilter (delt med de enkelte strategier)
		private static string OdinMappe()
		{
			string mappe = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "HelbertAlle4");
			Directory.CreateDirectory(mappe);
			return mappe;
		}

		private string KurveFil(Ben b) { return Path.Combine(OdinMappe(), "kurve_" + b.Model + ".csv"); }

		private void LaesKurve(Ben b)
		{
			b.Kurve.Clear();
			try
			{
				if (!File.Exists(KurveFil(b)))
				{
					// foerste start: kurven til og med 9/10-2026 ligger i koden og skrives til filen
					File.WriteAllText(KurveFil(b), b == gungner ? StartKurveSmt : StartKurveVergence);
					Print(string.Format("HelbertAlle4 {0}: startkurve skrevet til {1}", b.Navn, KurveFil(b)));
				}
				foreach (string linje in File.ReadAllLines(KurveFil(b)))
				{
					string[] f = linje.Split(';');
					double r;
					if (f.Length < 3 || !double.TryParse(f[2], NumberStyles.Float, CultureInfo.InvariantCulture, out r)) continue;
					string noegle = f[0] + " " + f[1];
					b.Kurve[noegle] = r;
					if (string.CompareOrdinal(noegle, b.FilSidste) > 0) b.FilSidste = noegle;
				}
				Print(string.Format("ODIN {0}: kurven har {1} handler, seneste {2}", b.Navn, b.Kurve.Count, b.FilSidste));
			}
			catch (Exception ex) { Print("ODIN kunne ikke laese kurven for " + b.Navn + ": " + ex.Message); }
		}

		private void TilKurve(Ben b, SmtHandel x, double r)
		{
			string noegle = x.Dato + " " + x.Tid;
			if (b.Kurve.ContainsKey(noegle)) return;
			b.Kurve[noegle] = r;
			// filen skrives kun fremad og ikke fra Strategy Analyzer
			if (string.CompareOrdinal(noegle, b.FilSidste) <= 0 || (Account != null && Account.Name == "Backtest")) return;
			b.FilSidste = noegle;
			try { File.AppendAllText(KurveFil(b), string.Format(CultureInfo.InvariantCulture, "{0};{1};{2}\r\n", x.Dato, x.Tid, r)); }
			catch (Exception ex) { Print("ODIN kunne ikke skrive kurven for " + b.Navn + ": " + ex.Message); }
		}

		private static bool KurveOk(Ben b, int n, string foer)
		{
			if (n <= 0) return true;
			List<double> kum = new List<double>();
			double sum = 0;
			foreach (KeyValuePair<string, double> kv in b.Kurve)
			{
				if (string.CompareOrdinal(kv.Key, foer) >= 0) break;
				sum += kv.Value;
				kum.Add(sum);
			}
			if (kum.Count < n) return true;
			double snit = 0;
			for (int i = kum.Count - n; i < kum.Count; i++) snit += kum[i];
			return kum[kum.Count - 1] >= snit / n;
		}

		// ------------------------------------------------------------------ stoerrelse
		private int Beregn(double stopPt, int antalFast, double pct)
		{
			if (Stoerrelse == HelbertStoerrelse.Fast)
				return antalFast;
			double konto = KontoStart + SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;
			if (BrugKontoSaldo && State == State.Realtime && Account != null)
				konto = Account.Get(AccountItem.NetLiquidation, Currency.UsDollar);
			double risiko = Math.Max(stopPt, TickSize) * Instrument.MasterInstrument.PointValue;
			return Math.Max(1, (int)Math.Floor(konto * pct / 100.0 / risiko));
		}

		// andre modeller samme vej: halv stoerrelse (hvis slaaet til) og samlet loft. 0 = gaa ikke ind
		private int Juster(Ben b, int antal, bool kort, out string note)
		{
			note = "";
			int andre = 0;
			foreach (Ben o in ben)
			{
				if (o == b) continue;
				if (o.Pos != 0 && (o.Pos < 0) == kort) andre += Math.Abs(o.Pos);
				if (o.Ventende > 0 && o.Kort == kort) andre += o.Ventende;
			}
			if (andre > 0 && HalverSammeVej)
			{
				antal = Math.Max(1, antal / 2);
				note = " (halv: " + andre + " samme vej i forvejen)";
			}
			if (MaksIAlt > 0 && andre + antal > MaksIAlt)
			{
				antal = Math.Max(0, MaksIAlt - andre);
				note += " (loft " + MaksIAlt + " micros)";
			}
			return antal;
		}

		// ------------------------------------------------------------------ ordrer
		private void GaaInd(Ben b, bool kort, int antal)
		{
			b.Kort = kort;
			b.Ventende = antal;
			b.BeFlyttet = false;
			b.IndAntal = 0;
			b.UdSum = 0;
			b.UdAntal = 0;
			b.ExitGrund = "";
			b.Nr = ++ocoTaeller;
			b.Oco = b.Model + "-" + b.Nr.ToString(CultureInfo.InvariantCulture) + "-" + DateTime.Now.Ticks.ToString(CultureInfo.InvariantCulture);
			b.Entry = SubmitOrderUnmanaged(0, kort ? OrderAction.SellShort : OrderAction.Buy, OrderType.Market, antal, 0, 0, "", OrdreNavn(b, "E"));
		}

		private void Beskyt(Ben b)
		{
			int antal = Math.Abs(b.Pos);
			if (antal == 0) return;
			double stop = b.StopPris ?? (b.Kort ? b.IndPris + b.StopAfstand : b.IndPris - b.StopAfstand);
			if (b.StopPris == null && b.StopAfstand <= 0) return;
			if (b.Stop == null || Slut(b.Stop))
				b.Stop = SubmitOrderUnmanaged(0, b.Kort ? OrderAction.BuyToCover : OrderAction.Sell, OrderType.StopMarket, antal, 0, stop, b.Oco, OrdreNavn(b, "S"));
			else
				ChangeOrder(b.Stop, antal, 0, b.Stop.StopPrice);
			if (b.TpPris.HasValue)
			{
				if (b.Tp == null || Slut(b.Tp))
					b.Tp = SubmitOrderUnmanaged(0, b.Kort ? OrderAction.BuyToCover : OrderAction.Sell, OrderType.Limit, antal, b.TpPris.Value, 0, b.Oco, OrdreNavn(b, "T"));
				else
					ChangeOrder(b.Tp, antal, b.Tp.LimitPrice, 0);
			}
		}

		private void FlytStop(Ben b, double nyStop, DateTime slut)
		{
			b.BeFlyttet = true;
			if (b.Stop != null && !Slut(b.Stop))
			{
				ChangeOrder(b.Stop, b.Stop.Quantity, 0, nyStop);
				Print(string.Format(CultureInfo.InvariantCulture, "{0} ODIN {1} BE: stop flyttet til {2}", slut, b.Navn, nyStop));
			}
		}

		private void Luk(Ben b, string grund, DateTime slut)
		{
			if (b.Entry != null && !Slut(b.Entry)) CancelOrder(b.Entry);
			b.Ventende = 0;
			if (b.Pos == 0) return;
			if (b.Exit != null && !Slut(b.Exit)) return;                              // er allerede ved at lukke
			b.ExitGrund = grund;
			if (b.Stop != null && !Slut(b.Stop)) CancelOrder(b.Stop);
			if (b.Tp != null && !Slut(b.Tp)) CancelOrder(b.Tp);
			b.Exit = SubmitOrderUnmanaged(0, b.Pos < 0 ? OrderAction.BuyToCover : OrderAction.Sell, OrderType.Market, Math.Abs(b.Pos), 0, 0, "", OrdreNavn(b, "X"));
		}

		private static bool Slut(Order o)
		{
			return o.OrderState == OrderState.Filled || o.OrderState == OrderState.Cancelled || o.OrderState == OrderState.Rejected;
		}

		private static string OrdreNavn(Ben b, string del)
		{
			return b.Model + "|" + del + "|" + b.Nr.ToString(CultureInfo.InvariantCulture);
		}

		// ordrenavn "Model|del|nr" -> modellen, delen (E entry, S stop, T target, X exit, K ret) og handlens nummer
		private Ben FindBen(Order o, out string del, out int nr)
		{
			del = ""; nr = 0;
			if (o == null || o.Name == null) return null;
			string[] f = o.Name.Split('|');
			if (f.Length != 3) return null;
			del = f[1];
			int.TryParse(f[2], NumberStyles.Integer, CultureInfo.InvariantCulture, out nr);
			foreach (Ben b in ben) if (b.Model == f[0]) return b;
			return null;
		}

		protected override void OnOrderUpdate(Order order, double limitPrice, double stopPrice, int quantity, int filled,
			double averageFillPrice, OrderState orderState, DateTime time, ErrorCode error, string comment)
		{
			string del;
			int nr;
			Ben b = FindBen(order, out del, out nr);
			if (b == null || nr != b.Nr) return;                                     // ordrer fra en tidligere handel roeres ikke
			// referencerne holdes opdaterede, som NinjaTrader anbefaler for unmanaged
			if (del == "E") b.Entry = order;
			else if (del == "S") b.Stop = order;
			else if (del == "T") b.Tp = order;
			else if (del == "X") b.Exit = order;
			if (orderState == OrderState.Rejected)
			{
				Print(string.Format("{0} ODIN {1}: {2}-ordre afvist ({3})", time, b.Navn, del, comment));
				if (del == "E") b.Ventende = 0;
				if ((del == "S" || del == "T") && b.Pos != 0)
					Luk(b, "beskyttelse afvist", time);                                // ingen ubeskyttet position
			}
			if (orderState == OrderState.Cancelled && del == "E")
				b.Ventende = 0;
		}

		protected override void OnExecutionUpdate(Execution execution, string executionId, double price, int quantity,
			MarketPosition marketPosition, string orderId, DateTime time)
		{
			string del;
			int nr;
			Ben b = FindBen(execution.Order, out del, out nr);
			if (b == null)
			{
				// NinjaTraders egen lukning ved sessionens slutning: alle modeller er flade bagefter
				if (execution.Order != null && execution.Order.Name == "Exit on session close")
					foreach (Ben o in ben)
						if (o.Pos != 0) Nulstil(o, "session slut", price, time);
				return;
			}
			if (del == "K") return;                                                 // retteordre efter dobbelt exit
			bool koeb = execution.Order.OrderAction == OrderAction.Buy || execution.Order.OrderAction == OrderAction.BuyToCover;
			if (del == "E")
			{
				int foer = Math.Abs(b.Pos);
				b.Pos += koeb ? quantity : -quantity;
				b.Ventende = Math.Max(0, b.Ventende - quantity);
				int nu = Math.Abs(b.Pos);
				b.IndPris = nu > 0 ? (b.IndPris * foer + price * quantity) / nu : price;
				b.IndAntal = nu;
				b.IndTid = time;
				Beskyt(b);
				if (execution.Order.OrderState == OrderState.Filled)
					LogInd(b);
				return;
			}
			// exit: stop, target eller marked
			int foerPos = b.Pos;
			if (foerPos == 0)
			{
				// stop/target og markedsexit fyldt begge (de krydsede hinanden): ret kontoen tilbage
				Print(string.Format("{0} ODIN {1}: dobbelt exit ({2} stk) - rettes med en markedsordre", time, b.Navn, quantity));
				SubmitOrderUnmanaged(0, koeb ? OrderAction.Sell : OrderAction.BuyToCover, OrderType.Market, quantity, 0, 0, "", OrdreNavn(b, "K"));
				return;
			}
			b.Pos += koeb ? quantity : -quantity;
			if (foerPos != 0 && (b.Pos == 0 || (b.Pos < 0) != (foerPos < 0)))
				b.Pos = 0;                                                            // aldrig over nul (overfill)
			b.UdSum += price * quantity;
			b.UdAntal += quantity;
			if (b.Pos != 0)
			{
				// delvis exit: resten beholder sine ordrer med rigtigt antal
				if (b.Stop != null && !Slut(b.Stop) && b.Stop.Quantity != Math.Abs(b.Pos)) ChangeOrder(b.Stop, Math.Abs(b.Pos), 0, b.Stop.StopPrice);
				if (b.Tp != null && !Slut(b.Tp) && b.Tp.Quantity != Math.Abs(b.Pos)) ChangeOrder(b.Tp, Math.Abs(b.Pos), b.Tp.LimitPrice, 0);
				return;
			}
			string grund = del == "S" ? (b.BeFlyttet ? "BE" : "stop") : del == "T" ? "TP" : (b.ExitGrund.Length > 0 ? b.ExitGrund : "lukket");
			if (b.Stop != null && !Slut(b.Stop)) CancelOrder(b.Stop);
			if (b.Tp != null && !Slut(b.Tp)) CancelOrder(b.Tp);
			if (b.Exit != null && !Slut(b.Exit) && del != "X") CancelOrder(b.Exit);
			LogUd(b, grund, b.UdAntal > 0 ? b.UdSum / b.UdAntal : price, time);
			b.Stop = b.Tp = b.Exit = b.Entry = null;
			b.UdSum = 0; b.UdAntal = 0; b.ExitGrund = "";
		}

		private void Nulstil(Ben b, string grund, double pris, DateTime tid)
		{
			if (b.Stop != null && !Slut(b.Stop)) CancelOrder(b.Stop);
			if (b.Tp != null && !Slut(b.Tp)) CancelOrder(b.Tp);
			if (b.Entry != null && !Slut(b.Entry)) CancelOrder(b.Entry);
			b.Pos = 0; b.Ventende = 0;
			b.Nr = ++ocoTaeller;                                                      // gamle ordrer ignoreres herefter
			LogUd(b, grund, pris, tid);
			b.Stop = b.Tp = b.Exit = b.Entry = null;
			b.UdSum = 0; b.UdAntal = 0; b.ExitGrund = "";
		}

		// ------------------------------------------------------------------ log (kun live): Discord, handler.csv og ODIN-server
		private void LogInd(Ben b)
		{
			if (State != State.Realtime) return;
			string instr = Instrument.MasterInstrument.Name, konto = Account != null ? Account.Name : "";
			double stop = b.StopPris ?? (b.Kort ? b.IndPris + b.StopAfstand : b.IndPris - b.StopAfstand);
			double riskPt = Math.Abs(b.IndPris - stop), riskUsd = riskPt * Instrument.MasterInstrument.PointValue * b.IndAntal;
			CultureInfo ic = CultureInfo.InvariantCulture;
			// ODIN | ÅBEN | dato tid DK | trade-id | model | retning antal instrument | fyld | stop | TP | risiko | konto
			Send(string.Format(ic, "ODIN | ÅBEN | {0} DK | {1} | {2} ({3}) | {4} {5} {6} | fyld {7:0.00} | stop {8:0.00} | TP {9} | risk {10:0.00} pt / {11:0} $ | {12}",
				DkTid(b.IndTid), TradeId(b), b.Model, b.Navn, b.Kort ? "SHORT" : "LONG", b.IndAntal, instr, b.IndPris, stop,
				b.TpPris.HasValue ? b.TpPris.Value.ToString("0.00", ic) : "-", riskPt, riskUsd, konto));
		}

		// dansk tid til Discord-beskeden
		private string DkTid(DateTime t)
		{
			TimeZoneInfo cph = TimeZoneInfo.FindSystemTimeZoneById("Romance Standard Time");
			return TimeZoneInfo.ConvertTime(t, NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo, cph).ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture);
		}

		// samme id paa aabning og lukning: model + entry-tid (NY)
		private string TradeId(Ben b)
		{
			DateTime indNy = TimeZoneInfo.ConvertTime(b.IndTid, NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo, newYork);
			return string.Format(CultureInfo.InvariantCulture, "{0}-{1:yyyyMMdd-HHmmss}", b.Model, indNy);
		}

		private void LogUd(Ben b, string grund, double ud, DateTime tid)
		{
			if (State != State.Realtime || b.IndAntal == 0) return;
			string instr = Instrument.MasterInstrument.Name, konto = Account != null ? Account.Name : "";
			double pt = (ud - b.IndPris) * (b.Kort ? -1 : 1);
			double usd = pt * Instrument.MasterInstrument.PointValue * b.IndAntal;
			double r = b.StopPt > 0 ? pt / b.StopPt : 0;
			// ODIN | LUKKET | dato tid DK | trade-id | model | retning antal instrument | ind -> ud | grund | point | $ | R | konto
			Send(string.Format(CultureInfo.InvariantCulture, "ODIN | LUKKET | {0} DK | {1} | {2} ({3}) | {4} {5} {6} | {7:0.00} → {8:0.00} | {9} | {10:+0.00;-0.00;0.00} pt | {11:+0;-0;0} $ | {12:+0.00;-0.00;0.00} R | {13}",
				DkTid(tid), TradeId(b), b.Model, b.Navn, b.Kort ? "SHORT" : "LONG", b.IndAntal, instr, b.IndPris, ud, grund, pt, usd, r, konto));
			TimeZoneInfo ntZone = NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo;
			DateTime indNy = TimeZoneInfo.ConvertTime(b.IndTid, ntZone, newYork), udNy = TimeZoneInfo.ConvertTime(tid, ntZone, newYork);
			CultureInfo ic = CultureInfo.InvariantCulture;
			if (SkrivLogfil)
			{
				try
				{
					string fil = Path.Combine(OdinMappe(), "handler.csv");
					bool ny = !File.Exists(fil);
					using (StreamWriter w = new StreamWriter(fil, true, new UTF8Encoding(ny)))
					{
						if (ny)
							w.WriteLine("dato;ind (NY);ud (NY);model;retning;antal;entry;exit;grund;point;dollars;instrument;konto");
						w.WriteLine(string.Join(";", new string[] {
							indNy.ToString("yyyy-MM-dd", ic), indNy.ToString("HH:mm:ss", ic), udNy.ToString("HH:mm:ss", ic), b.Model, b.Kort ? "short" : "long",
							b.IndAntal.ToString(ic), b.IndPris.ToString("0.00", dk), ud.ToString("0.00", dk), grund, pt.ToString("0.00", dk),
							usd.ToString("0.00", dk), instr, konto }));
					}
				}
				catch (Exception ex) { Print("ODIN kunne ikke skrive logfil: " + ex.Message); }
			}
			if (string.IsNullOrWhiteSpace(OdinServer)) return;
			double risiko = b.StopPt * Instrument.MasterInstrument.PointValue * b.IndAntal;
			string id = string.Format(ic, "{0}-{1:yyyyMMdd-HHmmss}-{2}", b.Model, indNy, konto);
			string json = string.Format(ic,
				"{{\"id\":\"{0}\",\"model\":\"{1}\",\"dato\":\"{2:yyyy-MM-dd}\",\"ind\":\"{2:HH:mm:ss}\",\"ud\":\"{3:HH:mm:ss}\"," +
				"\"retning\":\"{4}\",\"antal\":{5},\"entry\":{6},\"exit\":{7},\"grund\":\"{8}\",\"point\":{9},\"dollars\":{10}," +
				"\"risiko\":{11},\"instrument\":\"{12}\",\"konto\":\"{13}\"}}",
				Json(id), b.Model, indNy, udNy, b.Kort ? "short" : "long", b.IndAntal, b.IndPris, ud, Json(grund),
				Math.Round(pt, 2), Math.Round(usd, 2), Math.Round(risiko, 2), Json(instr), Json(konto));
			string url = OdinServer.Trim(), token = (OdinToken ?? "").Trim();
			Task.Run(async () =>
			{
				try
				{
					HttpRequestMessage besked = new HttpRequestMessage(HttpMethod.Post, url);
					besked.Content = new StringContent(json, Encoding.UTF8, "application/json");
					if (token.Length > 0) besked.Headers.Add("X-Odin-Token", token);
					HttpResponseMessage svar = await http.SendAsync(besked);
					if (!svar.IsSuccessStatusCode) sidsteFejl = "ODIN-serveren svarede " + (int)svar.StatusCode;
				}
				catch (Exception ex) { sidsteFejl = "ODIN-serveren: " + ex.Message; }
			});
		}

		private void Send(string tekst)
		{
			if (string.IsNullOrWhiteSpace(DiscordTradeLog)) return;
			string json = "{\"content\":\"" + tekst.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n") + "\"}";
			string url = DiscordTradeLog.Trim();
			Task.Run(async () =>
			{
				try
				{
					ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
					HttpResponseMessage svar = await http.PostAsync(url, new StringContent(json, Encoding.UTF8, "application/json"));
					if (!svar.IsSuccessStatusCode) sidsteFejl = "Discord svarede " + (int)svar.StatusCode;
				}
				catch (Exception ex) { sidsteFejl = ex.Message; }
			});
		}

		private static string Json(string s) { return (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\""); }

		#region Egenskaber
		[NinjaScriptProperty]
		[Display(Name = "NQ-instrument (signal)", Order = 1, GroupName = "1. Signaler")]
		public string NqInstrument { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "ES-instrument (signal)", Order = 2, GroupName = "1. Signaler")]
		public string EsInstrument { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "Stoerrelse", Order = 1, GroupName = "2. Stoerrelse")]
		public HelbertStoerrelse Stoerrelse { get; set; }

		[NinjaScriptProperty]
		[Range(100, double.MaxValue)]
		[Display(Name = "Konto ved start ($)", Order = 2, GroupName = "2. Stoerrelse")]
		public double KontoStart { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "Brug kontoens saldo live", Order = 3, GroupName = "2. Stoerrelse")]
		public bool BrugKontoSaldo { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "Til", Order = 1, GroupName = "3. Swing (Hugin)")]
		public bool SwingTil { get; set; }

		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name = "Antal (fast)", Order = 2, GroupName = "3. Swing (Hugin)")]
		public int SwingAntal { get; set; }

		[NinjaScriptProperty]
		[Range(0.1, 20)]
		[Display(Name = "Risiko % af konto", Order = 3, GroupName = "3. Swing (Hugin)")]
		public double SwingRisikoPct { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "Til", Order = 1, GroupName = "4. Market Open (Munin)")]
		public bool MoTil { get; set; }

		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name = "Antal (fast)", Order = 2, GroupName = "4. Market Open (Munin)")]
		public int MoAntal { get; set; }

		[NinjaScriptProperty]
		[Range(0.1, 20)]
		[Display(Name = "Risiko % af konto", Order = 3, GroupName = "4. Market Open (Munin)")]
		public double MoRisikoPct { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "Til", Order = 1, GroupName = "5. SMT (Gungner)")]
		public bool SmtTil { get; set; }

		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name = "Antal (fast)", Order = 2, GroupName = "5. SMT (Gungner)")]
		public int SmtAntal { get; set; }

		[NinjaScriptProperty]
		[Range(0.1, 20)]
		[Display(Name = "Risiko % af konto", Order = 3, GroupName = "5. SMT (Gungner)")]
		public double SmtRisikoPct { get; set; }

		[NinjaScriptProperty]
		[Range(0, 200)]
		[Display(Name = "Kurvefilter (0 = fra)", Order = 4, GroupName = "5. SMT (Gungner)")]
		public int SmtKurve { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "Til", Order = 1, GroupName = "6. Vergence (Sleipner)")]
		public bool VergenceTil { get; set; }

		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name = "Antal (fast)", Order = 2, GroupName = "6. Vergence (Sleipner)")]
		public int VergenceAntal { get; set; }

		[NinjaScriptProperty]
		[Range(0.1, 20)]
		[Display(Name = "Risiko % af konto", Order = 3, GroupName = "6. Vergence (Sleipner)")]
		public double VergenceRisikoPct { get; set; }

		[NinjaScriptProperty]
		[Range(0, 200)]
		[Display(Name = "Kurvefilter (0 = fra)", Order = 4, GroupName = "6. Vergence (Sleipner)")]
		public int VergenceKurve { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "Luk Market Open naar SMT/Vergence gaar modsat", Order = 1, GroupName = "7. Flere modeller")]
		public bool LukMoVedModsat { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "SMT/Vergence modsat aabent trade = papir", Order = 2, GroupName = "7. Flere modeller")]
		public bool PapirVedModsat { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "Halv stoerrelse hvis en anden model er inde samme vej", Order = 3, GroupName = "7. Flere modeller")]
		public bool HalverSammeVej { get; set; }

		[NinjaScriptProperty]
		[Range(0, 1000)]
		[Display(Name = "Maks micros i alt samme vej (0 = intet loft)", Order = 4, GroupName = "7. Flere modeller")]
		public int MaksIAlt { get; set; }

		[Display(Name = "Discord trade-log (webhook)", Order = 1, GroupName = "8. Log")]
		public string DiscordTradeLog { get; set; }

		[Display(Name = "Skriv handler til HelbertAlle4\\handler.csv", Order = 2, GroupName = "8. Log")]
		public bool SkrivLogfil { get; set; }

		[Display(Name = "ODIN-server (indtag)", Order = 3, GroupName = "8. Log")]
		public string OdinServer { get; set; }

		[Display(Name = "ODIN-token", Order = 4, GroupName = "8. Log")]
		public string OdinToken { get; set; }
		#endregion
	}
}

namespace NinjaTrader.NinjaScript.Strategies.HelbertOdin
{
	public class MotorIndstillinger
	{
		public double SwStop = 10.0;        // point
		public double SwTp = 175.0;         // point, 0 = intet
		public int SwSek = 4 * 3600;        // tidsudgang efter entry (bruges naar SwUdNy = 0)
		public int SwUdNy = 0;              // >0: luk swingen paa dette klokkeslaet NY (sekunder efter midnat)
		public double SwBe = 0.0;           // point i plus der flytter stoppet til entry (0 = intet)
		public double SwBeLaas = 0.0;
		public double MoStop = 30.0;
		public double MoTp = 0.0;
		public double Rv5Graense = 2.25;    // procent, 0 = slaaet fra
		public double Rv5Min = 0.0;         // kun swing: ingen swing under dette (0 = slaaet fra)
		public int MinRthBarer = 1000;
		public bool KunFormarked = false;   // kun formarkedets niveauer taeller
		public bool Fridage = false;        // ingen handler langfredag og Labor Day
		public int VindueStart = 525;       // minut efter midnat NY (525 = 08:45)

		// Planen 10/10 (motor/plan.py: swing())
		public static MotorIndstillinger PlanSwing()
		{
			MotorIndstillinger i = new MotorIndstillinger();
			i.SwStop = 40.0; i.SwTp = 0.0; i.SwUdNy = 11 * 3600; i.SwBe = 75.0;
			i.Rv5Graense = 2.0; i.Rv5Min = 1.0; i.Fridage = true; i.KunFormarked = true;
			return i;
		}

		// Market open som maalt (motor/plan_mo.py: Indstillinger(rv5_graense=2.25, fridage=True)).
		// Retningen afgoeres af den OPRINDELIGE swing-regel (London + formarked, status med stop 10 / TP 175).
		public static MotorIndstillinger MarketOpen()
		{
			MotorIndstillinger i = new MotorIndstillinger();
			i.Rv5Graense = 2.25; i.Fridage = true;
			return i;
		}
	}

	public class MotorOrdre
	{
		public string Navn;      // "SWING" eller "MO"
		public bool Kort;
		public double StopPt;    // 0 = intet stop
		public double TpPt;      // 0 = intet TP
		public long UdTid;       // luk ved lukket af den foerste bar der slutter >= denne tid (unix)
		public long T;           // start af baren ordren kom paa (fyldes ved dens luk)
		public double BePt;
		public double BeLaas;

		public override string ToString()
		{
			return string.Format("{0} {1} stop {2} tp {3}", Navn, Kort ? "SHORT" : "LONG", StopPt, TpPt);
		}
	}

	public class Motor
	{
		public readonly MotorIndstillinger Ind;
		public double? Rv5;
		public string MoRetning;            // "SHORT" / "LONG" / "INGEN" / "SPRING OVER"
		public readonly List<string> Log = new List<string>();

		private DateTime? dag;
		private readonly List<double> trp = new List<double>();
		private double[] rth;               // o, h, l, c, antal barer
		private double? forrigeLuk;

		// niveauer: 0 nLH, 1 nLL, 2 nPH, 3 nPL, 4 eLH, 5 eLL, 6 ePH, 7 ePL
		private const int NLH = 0, NLL = 1, NPH = 2, NPL = 3, ELH = 4, ELL = 5, EPH = 6, EPL = 7;
		private readonly double?[] niv = new double?[8];
		private readonly bool[] taget = new bool[8];
		private readonly bool[] brugt = new bool[8];      // kun London-niveauerne bruges
		private int sidstNH, sidstNL;
		private long fraH, tilH, fraL, tilL;

		// swingen (ogsaa naar den ikke handles - market open bruger dens status)
		private bool harSw;
		private bool swKort;
		private double swE, swStop;
		private long swT;
		private string swStatus;            // "aaben" / "tabt" / "vundet"
		private bool moGivet;

		public Motor(MotorIndstillinger ind)
		{
			Ind = ind;
			Nulstil();
		}

		public bool HarSwing { get { return harSw; } }
		public bool SwingKort { get { return swKort; } }
		public string SwingStatus { get { return swStatus; } }

		private void Nulstil()
		{
			for (int i = 0; i < 8; i++) { niv[i] = null; taget[i] = false; brugt[i] = false; }
			sidstNH = sidstNL = 0;
			fraH = tilH = fraL = tilL = 0;
			harSw = false; swStatus = null;
			moGivet = false;
			MoRetning = null;
		}

		private void NyDag()
		{
			if (rth != null && rth[4] > Ind.MinRthBarer)
			{
				double h = rth[1], l = rth[2], c = rth[3];
				if (forrigeLuk.HasValue)
				{
					double pc = forrigeLuk.Value;
					trp.Add(Math.Max(h - l, Math.Max(Math.Abs(h - pc), Math.Abs(l - pc))) / c * 100.0);
				}
				forrigeLuk = c;
			}
			rth = null;
			if (trp.Count >= 5)
			{
				double s = 0;
				for (int i = trp.Count - 5; i < trp.Count; i++) s += trp[i];
				Rv5 = s / 5.0;
			}
			else
				Rv5 = null;
			Nulstil();
		}

		// stop/TP i point rundet til tick (0,25)
		private static double Pt(double x)
		{
			return x != 0 ? Math.Round(x * 4.0, MidpointRounding.ToEven) / 4.0 : 0.0;
		}

		public bool HandelTilladt()
		{
			if (Ind.Fridage && dag.HasValue && ErFridag(dag.Value))
				return false;
			double g = Ind.Rv5Graense;
			return !(g > 0 && Rv5.HasValue && Rv5.Value >= g);
		}

		public static DateTime Paaske(int aar)
		{
			int a = aar % 19, b = aar / 100, c = aar % 100;
			int d = b / 4, e = b % 4;
			int f = (b + 8) / 25;
			int g = (b - f + 1) / 3;
			int h = (19 * a + b - d - g + 15) % 30;
			int i = c / 4, k = c % 4;
			int l = (32 + 2 * e + 2 * i - h - k) % 7;
			int m = (a + 11 * h + 22 * l) / 451;
			int mdr = (h + l - 7 * m + 114) / 31;
			int dg = ((h + l - 7 * m + 114) % 31) + 1;
			return new DateTime(aar, mdr, dg);
		}

		public static bool ErFridag(DateTime d)
		{
			if (d.Month == 9 && d.DayOfWeek == DayOfWeek.Monday && d.Day <= 7)
				return true;                                      // Labor Day
			return d.Date == Paaske(d.Year).AddDays(-2);          // langfredag
		}

		private static double? Maks(double? a, double b) { return a.HasValue ? Math.Max(a.Value, b) : b; }
		private static double? Min(double? a, double b) { return a.HasValue ? Math.Min(a.Value, b) : b; }

		public List<MotorOrdre> PaaBar(long t, DateTime ny, double o, double h, double l, double c,
		                              bool harE, double eo, double eh, double el, double ec)
		{
			int nyMin = ny.Hour * 60 + ny.Minute;
			int nySek = nyMin * 60 + ny.Second;
			if (!dag.HasValue || dag.Value != ny.Date)
			{
				dag = ny.Date;
				NyDag();
			}
			List<MotorOrdre> ud = new List<MotorOrdre>();

			// RTH til rv5 (09:30-16:00 NY)
			if (nyMin >= 570 && nyMin < 960)
			{
				if (rth == null)
					rth = new double[] { o, h, l, c, 1 };
				else
				{
					rth[1] = Math.Max(rth[1], h);
					rth[2] = Math.Min(rth[2], l);
					rth[3] = c;
					rth[4] += 1;
				}
			}
			// niveauer
			if (nyMin >= 120 && nyMin < 480)
			{
				niv[NLH] = Maks(niv[NLH], h);
				niv[NLL] = Min(niv[NLL], l);
				if (harE) { niv[ELH] = Maks(niv[ELH], eh); niv[ELL] = Min(niv[ELL], el); }
			}
			if (nyMin >= 480 && nyMin < 540)
			{
				niv[NPH] = Maks(niv[NPH], h);
				niv[NPL] = Min(niv[NPL], l);
				if (harE) { niv[EPH] = Maks(niv[EPH], eh); niv[EPL] = Min(niv[EPL], el); }
			}
			if (nyMin >= 480 && nyMin < 525)
			{
				if (niv[NLH].HasValue && h >= niv[NLH].Value) brugt[NLH] = true;
				if (niv[NLL].HasValue && l <= niv[NLL].Value) brugt[NLL] = true;
				if (harE && niv[ELH].HasValue && eh >= niv[ELH].Value) brugt[ELH] = true;
				if (harE && niv[ELL].HasValue && el <= niv[ELL].Value) brugt[ELL] = true;
			}

			const int tBeslut = 9 * 3600 + 29 * 60 + 45;       // 09:29:45 NY
			// swingens status til market open-retningen (barer efter entry, foer 09:29:45-baren)
			if (harSw && swStatus == "aaben" && t > swT && nySek < tBeslut)
			{
				double tp = Pt(Ind.SwTp);
				bool stopR, tpR;
				if (swKort) { stopR = h >= swE + swStop; tpR = l <= swE - tp; }
				else { stopR = l <= swE - swStop; tpR = h >= swE + tp; }
				if (stopR) swStatus = "tabt";
				else if (tpR) swStatus = "vundet";
			}

			// find swingen
			if (nyMin >= Ind.VindueStart && nySek < tBeslut && !harSw)
			{
				Sweep(h, l, harE, eh, el, nyMin >= 540);
				int nH, nL;
				if (Ind.KunFormarked)
				{
					nH = (taget[NPH] && taget[EPH]) ? 1 : 0;
					nL = (taget[NPL] && taget[EPL]) ? 1 : 0;
				}
				else
				{
					nH = ((taget[NLH] && taget[ELH]) ? 1 : 0) + ((taget[NPH] && taget[EPH]) ? 1 : 0);
					nL = ((taget[NLL] && taget[ELL]) ? 1 : 0) + ((taget[NPL] && taget[EPL]) ? 1 : 0);
				}
				long minNr = FloorDiv(t, 60);
				bool s15 = Mod(t, 60) == 45;
				if (nH > sidstNH) { fraH = minNr; tilH = s15 ? minNr + 1 : minNr; sidstNH = nH; }
				if (nL > sidstNL) { fraL = minNr; tilL = s15 ? minNr + 1 : minNr; sidstNL = nL; }
				bool ned = harE && c < o && ec < eo;
				bool op = harE && c > o && ec > eo;
				bool kortOK = nH > 0 && ned && fraH <= minNr && minNr <= tilH;
				bool langOK = nL > 0 && op && fraL <= minNr && minNr <= tilL;
				if (kortOK || langOK)
				{
					harSw = true; swKort = kortOK; swE = c; swT = t; swStatus = "aaben"; swStop = Pt(Ind.SwStop);
					Log.Add(string.Format("{0:yyyy-MM-dd HH:mm:ss} NY swing {1} {2}", ny, kortOK ? "SHORT" : "LONG", c));
					if (HandelTilladt() && !(Ind.Rv5Min > 0 && Rv5.HasValue && Rv5.Value < Ind.Rv5Min))
					{
						MotorOrdre od = new MotorOrdre();
						od.Navn = "SWING"; od.Kort = kortOK; od.StopPt = swStop; od.TpPt = Pt(Ind.SwTp);
						od.UdTid = Ind.SwUdNy > 0 ? t - nySek + Ind.SwUdNy : t + 15 + Ind.SwSek;
						od.T = t; od.BePt = Ind.SwBe; od.BeLaas = Ind.SwBeLaas;
						ud.Add(od);
					}
				}
			}

			// market open: beslutning paa baren der starter 09:29:45
			if (!moGivet && nySek == tBeslut)
			{
				moGivet = true;
				if (!harSw)
					MoRetning = "INGEN";
				else if (!HandelTilladt())
					MoRetning = "SPRING OVER";
				else
				{
					bool kort = swStatus == "tabt" ? !swKort : swKort;
					MoRetning = kort ? "SHORT" : "LONG";
					MotorOrdre od = new MotorOrdre();
					od.Navn = "MO"; od.Kort = kort; od.StopPt = Pt(Ind.MoStop); od.TpPt = Pt(Ind.MoTp);
					od.UdTid = t + 15 + 60; od.T = t;
					ud.Add(od);
				}
				Log.Add(string.Format("{0:yyyy-MM-dd HH:mm:ss} NY market open {1}", ny, MoRetning));
			}
			return ud;
		}

		// formarkedets niveauer taeller kun fra 09:00 (pA); Londons kun hvis ikke brugt op foer 08:45
		private void Sweep(double h, double l, bool harE, double eh, double el, bool pA)
		{
			if (!taget[NLH] && !brugt[NLH] && niv[NLH].HasValue && h >= niv[NLH].Value) taget[NLH] = true;
			if (pA && !taget[NPH] && niv[NPH].HasValue && h >= niv[NPH].Value) taget[NPH] = true;
			if (harE && !taget[ELH] && !brugt[ELH] && niv[ELH].HasValue && eh >= niv[ELH].Value) taget[ELH] = true;
			if (harE && pA && !taget[EPH] && niv[EPH].HasValue && eh >= niv[EPH].Value) taget[EPH] = true;
			if (!taget[NLL] && !brugt[NLL] && niv[NLL].HasValue && l <= niv[NLL].Value) taget[NLL] = true;
			if (pA && !taget[NPL] && niv[NPL].HasValue && l <= niv[NPL].Value) taget[NPL] = true;
			if (harE && !taget[ELL] && !brugt[ELL] && niv[ELL].HasValue && el <= niv[ELL].Value) taget[ELL] = true;
			if (harE && pA && !taget[EPL] && niv[EPL].HasValue && el <= niv[EPL].Value) taget[EPL] = true;
		}

		private static long FloorDiv(long a, long b) { long q = a / b; if ((a % b != 0) && ((a < 0) != (b < 0))) q--; return q; }
		private static long Mod(long a, long b) { long m = a % b; return m < 0 ? m + b : m; }
	}
}

namespace NinjaTrader.NinjaScript.Strategies.HelbertOdin
{
	public class SmtHandel
	{
		public string Dato, Tid, Niveau = "", Swept = "", Info = "", TpKilde = "", BeKilde = "-", Status, Resultat = "", Exit = "";
		public bool Kort;
		public double Entry;
		public double? Sl, Tp, Be, Points, R;
		public long T;
	}

	public enum SmtType { Ny, Ugyldig, Lukket, Be, Afloest }

	public class SmtBegivenhed
	{
		public SmtType Type;
		public SmtHandel Handel;
		public double Pris;          // Lukket: exitpris (SL eller TP). Be: ny stop (= entry)
		public SmtBegivenhed(SmtType type, SmtHandel h, double pris) { Type = type; Handel = h; Pris = pris; }
	}

	public class SmtMotor
	{
		private const double TICK = 0.25;
		private const int WIN_S = 9 * 60 + 30, WIN_E = 10 * 60, M15_END = 9 * 60 + 31;
		private const double MIN_SL = 10, MAX_SL = 30, TP_MIN = 35, TP_MAX = 75, BE_MIN = 2, BE_MAX = 50;
		private const int VRG_GAP = 5, NYPRE_MIN_BARS = 300;
		// Vergence: close tilbage maales kun mod niveauer BEGGE indeks har taget (15/10-26)
		private const bool VRG_SHARED = true;
		private static readonly HashSet<string> NO_TRADE_DAYS = new HashSet<string>(new string[] {
			"2022-01-17", "2022-02-21", "2022-04-15", "2022-05-30", "2022-06-20", "2022-07-04", "2022-09-05", "2022-11-24", "2022-12-26",
			"2023-01-02", "2023-01-16", "2023-02-20", "2023-04-07", "2023-05-29", "2023-06-19", "2023-07-04", "2023-09-04", "2023-11-23", "2023-12-25",
			"2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29", "2024-05-27", "2024-06-19", "2024-07-04", "2024-09-02", "2024-11-28", "2024-12-25",
			"2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26", "2025-06-19", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25",
			"2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
			"2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24" });

		private class St
		{
			public long? aM, bM, aT, bT;
			public bool aDone, bDone, aTook, bTook, aTgT, bTgT, aPre;
			public double? aLv, bLv;
		}

		private class Sess
		{
			public double? aHi, aLo, bHi, bLo, aTgH, bTgH, aTgL, bTgL;
			public St hi, lo;
			public long aHiM, bHiM, aLoM, bLoM;
			public bool maHi, mbHi, maLo, mbLo;
		}

		private class Lv
		{
			public double a, b;
			public bool isHi, dead;
			public St st = new St();
			public long tm;
		}

		private class Arm
		{
			public bool side;
			public double? va, vb;
			public string info, names;
			public long t;
		}

		private class Hit
		{
			public bool fired, isShort, swHi, swLo, sHi, sLo;
			public double? lvl;
			public string src = "", who = "", info = "";
			public List<Arm> varmList = new List<Arm>();
		}

		private class Frisk
		{
			public long m;
			public double lv;
			public string key;
			public bool brugt;
		}

		private class VSide
		{
			public List<Frisk> aF = new List<Frisk>(), bF = new List<Frisk>();
			public long? aE, bE, aFM, bFM, xT;
			public double? aFL, bFL;
			public bool neu, had;
		}

		private class Aaben
		{
			public bool kort, beHit, early, noBE;
			public double entry, sl, tp;
			public double? be;
			public int bars;
			public SmtHandel rec;
		}

		// 15m/5m-aggregat: seneste afsluttede candle (key, high, low) og den igangvaerende
		private class Agg
		{
			private readonly long sek;
			public long? curKey, prevKey;
			public double curH, curL, prevH, prevL;
			public Agg(long s) { sek = s; }
			public void Add(long t, double h, double l)
			{
				long k = FloorDiv(t, sek) * sek;
				if (curKey.HasValue && curKey.Value == k) { curH = Math.Max(curH, h); curL = Math.Min(curL, l); return; }
				if (curKey.HasValue) { prevKey = curKey; prevH = curH; prevL = curL; }
				curKey = k; curH = h; curL = l;
			}
			// sidste candle med start foer p (scriptets prev_period)
			public bool Foer(long p, out long key, out double h, out double l)
			{
				if (curKey.HasValue && curKey.Value < p) { key = curKey.Value; h = curH; l = curL; return true; }
				if (prevKey.HasValue && prevKey.Value < p) { key = prevKey.Value; h = prevH; l = prevL; return true; }
				key = 0; h = l = 0; return false;
			}
		}

		public readonly bool Vrg;
		private readonly TimeZoneInfo newYork;
		private static readonly DateTime epoke = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);
		public readonly List<SmtHandel> Handler = new List<SmtHandel>();

		// ES fyldt frem: senest modtagne ES-bar og den der bruges (kun opdateret naar ES har en bar paa NQ-barens tid)
		private bool bok;
		private double esO, esH, esL, esC;
		private long esT = long.MinValue;
		private double nyO, nyH, nyL, nyC;
		private readonly Agg g15a = new Agg(900), g05a = new Agg(300), g15b = new Agg(900), g05b = new Agg(300);

		private readonly Sess asia = new Sess(), lon = new Sess(), ny = new Sess();
		private List<Lv> lv15 = new List<Lv>(), lv05 = new List<Lv>();
		private bool prevA, prevL, prevN;
		private long? lastQt, lastFt;
		private int? prevMn;
		private double? m1Hi, m1Lo;
		private long? prevQ15;
		private double? aq15Hi, aq15Lo, bq15Hi, bq15Lo;
		private long? lastMin;
		private double[] curMinOHLC;
		private bool dAct, uAct;
		private double dTop, dBot, uTop, uBot;
		private double? preD, preU, pDT, pDB, pUB, pUT;
		private long? preDHitM, preUHitM;
		private long? lastTradeM;
		private List<Arm> vArms = new List<Arm>();
		private readonly Dictionary<bool, VSide> vSide = new Dictionary<bool, VSide>();
		private string vDay, resetDay;
		private readonly List<KeyValuePair<long, double>> hitsD = new List<KeyValuePair<long, double>>(), hitsU = new List<KeyValuePair<long, double>>(),
			hitsSH = new List<KeyValuePair<long, double>>(), hitsSL = new List<KeyValuePair<long, double>>();
		private readonly Dictionary<string, int> nyCnt = new Dictionary<string, int>();
		private long? curM;
		private bool mHi, mLo, mBad;
		private Aaben o;

		// pr. bar
		private long t, minB;
		private int tMin;
		private bool inWin, is369;
		private double hi, lo, cl, op, bh, bl, bc, bo;
		private Hit h;

		public SmtMotor(bool vergence)
		{
			Vrg = vergence;
			newYork = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
			vSide[true] = new VSide();
			vSide[false] = new VSide();
		}

		public bool HarAaben { get { return o != null; } }

		private DateTime NyTid(long u) { return TimeZoneInfo.ConvertTimeFromUtc(epoke.AddSeconds(u), newYork); }

		public void PaaEs(long tt, double eo, double eh, double el, double ec)
		{
			esT = tt; nyO = eo; nyH = eh; nyL = el; nyC = ec;
			g15b.Add(tt, eh, el);
			g05b.Add(tt, eh, el);
		}

		public List<SmtBegivenhed> PaaNq(long tt, DateTime lt, double o_, double h_, double l_, double c_)
		{
			List<SmtBegivenhed> ud = new List<SmtBegivenhed>();
			t = tt; op = o_; hi = h_; lo = l_; cl = c_;
			if (esT == t) { bok = true; esO = nyO; esH = nyH; esL = nyL; esC = nyC; }
			bh = esH; bl = esL; bc = esC; bo = esO;
			g15a.Add(t, hi, lo);
			g05a.Add(t, hi, lo);
			tMin = lt.Hour * 60 + lt.Minute;
			inWin = tMin >= WIN_S && tMin < WIN_E;
			bool isOpenM = tMin == WIN_S;
			int ds = lt.Minute / 10 + lt.Minute % 10;
			is369 = ds == 3 || ds == 6 || ds == 9;
			minB = FloorDiv(t, 60);
			string dstr = lt.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
			DateTime dk = lt.AddHours(6);

			bool newMin = !prevMn.HasValue || lt.Minute != prevMn.Value;
			prevMn = lt.Minute;
			m1Hi = newMin || !m1Hi.HasValue ? hi : Math.Max(m1Hi.Value, hi);
			m1Lo = newMin || !m1Lo.HasValue ? lo : Math.Min(m1Lo.Value, lo);
			long q15B = FloorDiv(t, 900);
			bool newQ15 = !prevQ15.HasValue || q15B != prevQ15.Value;
			prevQ15 = q15B;
			aq15Hi = newQ15 || !aq15Hi.HasValue ? hi : Math.Max(aq15Hi.Value, hi);
			aq15Lo = newQ15 || !aq15Lo.HasValue ? lo : Math.Min(aq15Lo.Value, lo);
			if (bok)
			{
				bq15Hi = newQ15 || !bq15Hi.HasValue ? bh : Math.Max(bq15Hi.Value, bh);
				bq15Lo = newQ15 || !bq15Lo.HasValue ? bl : Math.Min(bq15Lo.Value, bl);
			}

			bool aOn = tMin >= 20 * 60 || tMin < 2 * 60, lOn = tMin >= 2 * 60 && tMin < 8 * 60, nOn = tMin >= 8 * 60 && tMin < WIN_S;
			if (nOn) { int n; nyCnt.TryGetValue(dstr, out n); nyCnt[dstr] = n + 1; }
			bool aStart = aOn && !prevA, lStart = lOn && !prevL, nStart = nOn && !prevN;
			prevA = aOn; prevL = lOn; prevN = nOn;

			Merge(asia, aOn);
			Merge(lon, lOn);
			if (aOn) Build(asia, aStart, q15B);
			if (lOn) Build(lon, lStart, q15B);
			if (nOn) Build(ny, nStart, q15B);

			// 15m / 5m niveauer fra NY PRE
			long k15 = FloorDiv(t, 900) * 900, k05 = FloorDiv(t, 300) * 300;
			long qT, fT, eT, gT;
			double qah, qal, fah, fal, qbh, qbl, fbh, fbl;
			bool harQ = g15a.Foer(k15, out qT, out qah, out qal);
			bool harF = g05a.Foer(k05, out fT, out fah, out fal);
			bool newM15 = harQ && (!lastQt.HasValue || qT != lastQt.Value);
			if (newM15) lastQt = qT;
			bool newM05 = harF && (!lastFt.HasValue || fT != lastFt.Value);
			if (newM05) lastFt = fT;
			if (nStart) { lv15 = new List<Lv>(); lv05 = new List<Lv>(); }
			if (newM15 && INyPre(qT) && g15b.Foer(k15, out eT, out qbh, out qbl))
			{
				lv15.Add(new Lv { a = qah, b = qbh, isHi = true, tm = qT });
				lv15.Add(new Lv { a = qal, b = qbl, isHi = false, tm = qT });
			}
			if (newM05 && INyPre(fT) && g05b.Foer(k05, out gT, out fbh, out fbl))
			{
				lv05.Add(new Lv { a = fah, b = fbh, isHi = true });
				lv05.Add(new Lv { a = fal, b = fbl, isHi = false });
			}
			if (nOn)
			{
				foreach (Lv m in Kaede(lv15, lv05))
				{
					bool aHit = m.isHi ? hi >= m.a : lo <= m.a;
					bool bHit = bok && (m.isHi ? bh >= m.b : bl <= m.b);
					if (aHit || bHit) m.dead = true;
				}
			}
			else
			{
				foreach (Lv m in Kaede(lv05, tMin >= M15_END ? lv15 : new List<Lv>()))
					if (m.isHi ? hi >= m.a : lo <= m.a) m.st.aTook = true;
			}

			// tjek niveauer
			if (Vrg && inWin && vDay != dstr)
			{
				vDay = dstr;
				vSide[true] = new VSide();
				vSide[false] = new VSide();
			}
			h = new Hit();
			if (!nOn)
			{
				double? a1, b1;
				Tg(ny, true, out a1, out b1); Check(ny.hi, ny.aHi, ny.bHi, true, "NY PRE", a1, b1, null);
				Tg(ny, false, out a1, out b1); Check(ny.lo, ny.aLo, ny.bLo, false, "NY PRE", a1, b1, null);
			}
			if (!lOn)
			{
				double? a1, b1;
				if (!(lon.maHi || lon.mbHi)) { Tg(lon, true, out a1, out b1); Check(lon.hi, lon.aHi, lon.bHi, true, "London", a1, b1, null); }
				if (!(lon.maLo || lon.mbLo)) { Tg(lon, false, out a1, out b1); Check(lon.lo, lon.aLo, lon.bLo, false, "London", a1, b1, null); }
			}
			if (!aOn)
			{
				double? a1, b1;
				if (!(asia.maHi || asia.mbHi)) { Tg(asia, true, out a1, out b1); Check(asia.hi, asia.aHi, asia.bHi, true, "Asia", a1, b1, null); }
				if (!(asia.maLo || asia.mbLo)) { Tg(asia, false, out a1, out b1); Check(asia.lo, asia.aLo, asia.bLo, false, "Asia", a1, b1, null); }
			}
			if (!nOn && tMin < M15_END)
			{
				foreach (Lv m in lv15)
				{
					double ext = m.isHi ? (ny.aHi ?? 0) : (ny.aLo ?? 0);
					bool isExt = Math.Abs(m.a - ext) < TICK / 2;
					if (!m.dead && !isExt)
						Check(m.st, m.a, m.b, m.isHi, "15m", null, null, NyTid(m.tm).AddHours(6).ToString("HH:mm", CultureInfo.InvariantCulture));
				}
			}

			// EQ paa 1m: vurder den netop lukkede minut-candle paa foerste bar i et nyt minut
			bool new1m = lastMin.HasValue && minB != lastMin.Value;
			double[] prevMin = null;
			bool bearE = false, bullE = false;
			if (new1m)
			{
				prevMin = (double[])curMinOHLC.Clone();
				double own = (prevMin[1] + prevMin[2]) / 2;
				bearE = prevMin[3] < prevMin[0] && prevMin[3] < own;
				bullE = prevMin[3] > prevMin[0] && prevMin[3] > own;
				if (inWin && tMin == WIN_S) bearE = bullE = false;
			}
			if (!lastMin.HasValue || minB != lastMin.Value) { curMinOHLC = new double[] { op, hi, lo, cl }; lastMin = minB; }
			else { curMinOHLC[1] = Math.Max(curMinOHLC[1], hi); curMinOHLC[2] = Math.Min(curMinOHLC[2], lo); curMinOHLC[3] = cl; }
			if (inWin && resetDay != dstr) { resetDay = dstr; dAct = uAct = false; }
			if (dAct)
			{
				if (hi >= (dTop + dBot) / 2) { dAct = false; hitsD.Add(new KeyValuePair<long, double>(t, (dTop + dBot) / 2)); }
				else dBot = Math.Min(dBot, lo);
			}
			if (bearE && !dAct) { dTop = prevMin[1]; dBot = Math.Min(prevMin[2], lo); dAct = true; }
			if (uAct)
			{
				if (lo <= (uBot + uTop) / 2) { uAct = false; hitsU.Add(new KeyValuePair<long, double>(t, (uBot + uTop) / 2)); }
				else uTop = Math.Max(uTop, hi);
			}
			if (bullE && !uAct) { uBot = prevMin[2]; uTop = Math.Max(prevMin[1], hi); uAct = true; }
			// EQ foer market open (til BE) - laases fra 09:30 og vokser videre indtil den rammes
			if (tMin < WIN_S)
			{
				preD = dAct ? (dTop + dBot) / 2 : (double?)null;
				preU = uAct ? (uBot + uTop) / 2 : (double?)null;
				pDT = dAct ? dTop : (double?)null; pDB = dAct ? dBot : (double?)null;
				pUB = uAct ? uBot : (double?)null; pUT = uAct ? uTop : (double?)null;
				preDHitM = preUHitM = null;
			}
			else
			{
				bool gfD = cl > op, gfU = cl < op;
				if (!preDHitM.HasValue && pDT.HasValue)
				{
					if (gfD) pDB = Math.Min(pDB.Value, lo);
					if (hi >= (pDT.Value + pDB.Value) / 2) preDHitM = minB;
					else if (!gfD) pDB = Math.Min(pDB.Value, lo);
					preD = (pDT.Value + pDB.Value) / 2;
				}
				if (!preUHitM.HasValue && pUB.HasValue)
				{
					if (gfU) pUT = Math.Max(pUT.Value, hi);
					if (lo <= (pUB.Value + pUT.Value) / 2) preUHitM = minB;
					else if (!gfU) pUT = Math.Max(pUT.Value, hi);
					preU = (pUB.Value + pUT.Value) / 2;
				}
				// 09:29-candlen lukker foer open: dens EQ er ogsaa en "EQ foer open"
				if (new1m && tMin == WIN_S && resetDay == dstr)
				{
					double own = (prevMin[1] + prevMin[2]) / 2;
					if (prevMin[3] < prevMin[0] && prevMin[3] < own && !pDT.HasValue)
					{ pDT = prevMin[1]; pDB = Math.Min(prevMin[2], lo); preDHitM = null; preD = (pDT.Value + pDB.Value) / 2; }
					if (prevMin[3] > prevMin[0] && prevMin[3] > own && !pUB.HasValue)
					{ pUB = prevMin[2]; pUT = Math.Max(prevMin[1], hi); preUHitM = null; preU = (pUB.Value + pUT.Value) / 2; }
				}
			}

			// minut-status: high- og low-side taget i samme minut -> ingen nye handler i minuttet
			if (!curM.HasValue || minB != curM.Value) { curM = minB; mHi = mLo = mBad = false; }
			if (inWin) { mHi = mHi || h.swHi; mLo = mLo || h.swLo; }
			if (mHi && mLo && !mBad) mBad = true;

			// aaben handel
			if (o != null)
			{
				bool hitSL = o.kort ? hi >= o.sl : lo <= o.sl;
				bool hitTP = o.kort ? lo <= o.tp : hi >= o.tp;
				if (hitSL || hitTP)
				{
					SmtHandel tr = o.rec;
					double pts, px;
					if (hitSL) { pts = o.kort ? o.entry - o.sl : o.sl - o.entry; tr.Resultat = o.beHit ? "BE" : "SL"; px = o.sl; }
					else { pts = Math.Abs(o.tp - o.entry); tr.Resultat = "TP"; px = o.tp; }
					tr.Points = Math.Round(pts, 2);
					tr.R = Math.Round(pts / 10.0, 2);
					tr.Exit = dk.ToString("HH:mm:ss", CultureInfo.InvariantCulture);
					ud.Add(new SmtBegivenhed(SmtType.Lukket, tr, px));
					o = null;
				}
				else
				{
					if (!o.beHit && o.be.HasValue && !o.noBE)
					{
						bool touch = o.kort ? lo <= o.be.Value : hi >= o.be.Value;
						if (o.bars < 2)
						{
							if (touch) o.early = true;
							if (o.bars == 1 && o.early)
							{
								if (o.kort ? cl < o.entry : cl > o.entry) { o.beHit = true; o.sl = o.entry; ud.Add(new SmtBegivenhed(SmtType.Be, o.rec, o.entry)); }
								else o.noBE = true;
							}
						}
						else if (touch) { o.beHit = true; o.sl = o.entry; ud.Add(new SmtBegivenhed(SmtType.Be, o.rec, o.entry)); }
					}
					o.bars++;
				}
			}

			// Vergence: en side er klar, naar begge indeks har taget samme niveau frisk hoejst 5 min fra hinanden
			if (Vrg) VergenceArme(dstr);

			if (h.fired && lastTradeM.HasValue && lastTradeM.Value == minB) h.fired = false;      // eet trade pr. minut
			if (h.fired)
			{
				int n; nyCnt.TryGetValue(dstr, out n);
				if (NO_TRADE_DAYS.Contains(dstr) || n < NYPRE_MIN_BARS) h.fired = false;
			}
			if (h.fired && !mBad) NyHandel(lt, dk, isOpenM, ud);

			// gamle "ramt"-markeringer bruges kun i indevaerende minut
			Trim(hitsD); Trim(hitsU); Trim(hitsSH); Trim(hitsSL);
			return ud;
		}

		private void Trim(List<KeyValuePair<long, double>> L)
		{
			long graense = minB * 60 - 120;
			L.RemoveAll(x => x.Key < graense);
		}

		private static IEnumerable<Lv> Kaede(List<Lv> a, List<Lv> b)
		{
			foreach (Lv x in a) yield return x;
			foreach (Lv x in b) yield return x;
		}

		private bool INyPre(long pt)
		{
			DateTime d = NyTid(pt);
			int m = d.Hour * 60 + d.Minute;
			return m >= 8 * 60 && m < WIN_S;
		}

		private void Build(Sess s, bool isStart, long q15B)
		{
			if (isStart)
			{
				s.aHi = hi; s.aLo = lo;
				if (bok) { s.bHi = bh; s.bLo = bl; } else { s.bHi = null; s.bLo = null; }
				s.hi = new St(); s.lo = new St();
				s.aHiM = s.bHiM = s.aLoM = s.bLoM = q15B;
				s.aTgH = s.bTgH = s.aTgL = s.bTgL = null;
				s.maHi = s.mbHi = s.maLo = s.mbLo = false;
			}
			else
			{
				if (hi >= s.aHi.Value) s.aHiM = q15B;
				if (lo <= s.aLo.Value) s.aLoM = q15B;
				if (bok && (!s.bHi.HasValue || bh >= s.bHi.Value)) s.bHiM = q15B;
				if (bok && (!s.bLo.HasValue || bl <= s.bLo.Value)) s.bLoM = q15B;
				s.aHi = Math.Max(s.aHi.Value, hi); s.aLo = Math.Min(s.aLo.Value, lo);
				if (bok)
				{
					s.bHi = s.bHi.HasValue ? Math.Max(s.bHi.Value, bh) : bh;
					s.bLo = s.bLo.HasValue ? Math.Min(s.bLo.Value, bl) : bl;
				}
			}
			if (s.aHiM == q15B) s.bTgH = bq15Hi;
			if (s.bHiM == q15B) s.aTgH = aq15Hi;
			if (s.aLoM == q15B) s.bTgL = bq15Lo;
			if (s.bLoM == q15B) s.aTgL = aq15Lo;
		}

		private void Tg(Sess s, bool isHi, out double? a, out double? b)
		{
			a = b = null;
			if (isHi ? (s.maHi || s.mbHi) : (s.maLo || s.mbLo)) return;
			if (isHi && s.aHiM != s.bHiM) { a = s.aTgH; b = s.bTgH; }
			if (!isHi && s.aLoM != s.bLoM) { a = s.aTgL; b = s.bTgL; }
		}

		// Tager et indeks en tidligere sessions high/low i en senere session (foer open), flytter niveauet med
		private void Merge(Sess s, bool on)
		{
			if (on || !s.aHi.HasValue || tMin >= WIN_S) return;
			if (hi > s.aHi.Value) { s.aHi = hi; s.maHi = true; }
			if (lo < s.aLo.Value) { s.aLo = lo; s.maLo = true; }
			if (bok && s.bHi.HasValue && bh > s.bHi.Value) { s.bHi = bh; s.mbHi = true; }
			if (bok && s.bLo.HasValue && bl < s.bLo.Value) { s.bLo = bl; s.mbLo = true; }
		}

		private void Check(St st, double? aLn, double? bLn, bool isHi, string nm, double? aTg, double? bTg, string tag)
		{
			if (st == null || !aLn.HasValue || !bLn.HasValue) return;
			double aL = aLn.Value, bL = bLn.Value;
			bool aSweep = isHi ? hi >= aL + TICK : lo <= aL - TICK;
			bool bSweep = bok && (isHi ? bh >= bL + TICK : bl <= bL - TICK);
			string lvlNm = nm + (isHi ? " high" : " low");
			string vKey = lvlNm + (tag != null ? " " + tag : "");
			if (inWin && aSweep && !st.aTook && nm != "15m")
			{
				if (isHi) { h.sHi = true; hitsSH.Add(new KeyValuePair<long, double>(t, aL)); }
				else { h.sLo = true; hitsSL.Add(new KeyValuePair<long, double>(t, aL)); }
			}
			if (aSweep) st.aTook = true;
			if (bSweep) st.bTook = true;
			bool newTg = false;
			if (inWin && aTg.HasValue && !st.aTgT && (isHi ? (aTg.Value < aL && hi >= aTg.Value + TICK) : (aTg.Value > aL && lo <= aTg.Value - TICK)))
				st.aTgT = newTg = true;
			if (inWin && bok && bTg.HasValue && !st.bTgT && (isHi ? (bTg.Value < bL && bh >= bTg.Value + TICK) : (bTg.Value > bL && bl <= bTg.Value - TICK)))
				st.bTgT = newTg = true;
			bool aTk = st.aTook || st.aTgT, bTk = st.bTook || st.bTgT;

			if (Vrg)
			{
				// et niveau taget foerste gang i vinduet = FRISK liq; bagefter flytter det med til indeksets nye yderpunkt
				if (!inWin) return;
				double curA = st.aLv ?? aL, curB = st.bLv ?? bL;
				bool nA = isHi ? hi >= curA + TICK : lo <= curA - TICK;
				bool nB = bok && (isHi ? bh >= curB + TICK : bl <= curB - TICK);
				VSide sd = vSide[isHi];
				if (nA)
				{
					if (!st.aLv.HasValue)
					{
						sd.aF.Add(new Frisk { m = minB, lv = aL, key = vKey });
						sd.aFL = (!sd.aFM.HasValue || sd.aFM.Value != minB || !sd.aFL.HasValue) ? aL : (isHi ? Math.Max(sd.aFL.Value, aL) : Math.Min(sd.aFL.Value, aL));
						sd.aFM = minB;
					}
					if (curA == aL || !sd.had) { sd.aE = minB; sd.neu = true; }
					st.aLv = isHi ? hi : lo;
				}
				if (nB)
				{
					if (!st.bLv.HasValue)
					{
						sd.bF.Add(new Frisk { m = minB, lv = bL, key = vKey });
						sd.bFL = (!sd.bFM.HasValue || sd.bFM.Value != minB || !sd.bFL.HasValue) ? bL : (isHi ? Math.Max(sd.bFL.Value, bL) : Math.Min(sd.bFL.Value, bL));
						sd.bFM = minB;
					}
					if (curB == bL || !sd.had) { sd.bE = minB; sd.neu = true; }
					st.bLv = isHi ? bh : bl;
				}
				if (nA || nB)
				{
					sd.xT = t;
					h.swHi = h.swHi || isHi;
					h.swLo = h.swLo || !isHi;
				}
				return;
			}

			if (!inWin)
			{
				if (aSweep) { st.aDone = true; st.aPre = true; }
				if (bSweep) st.bDone = true;
				return;
			}
			bool newA = !st.aDone && !st.aM.HasValue && aSweep;
			bool newB = !st.bDone && !st.bM.HasValue && bSweep;
			if (newA) { st.aM = minB; st.aT = t; }
			if (newB) { st.bM = minB; st.bT = t; }
			if (newA || newB) { h.swHi = h.swHi || isHi; h.swLo = h.swLo || !isHi; }
			if ((newA || newB || newTg) && aTk && bTk && !(st.aDone && st.bDone)) st.aDone = st.bDone = true;
			if (!is369) { if (newA) st.aDone = true; if (newB) st.bDone = true; }
			if (!st.aDone && st.aM.HasValue && st.aM.Value != minB) st.aDone = true;
			if (!st.bDone && st.bM.HasValue && st.bM.Value != minB) st.bDone = true;
			if (!h.fired)
			{
				bool dirOK = isHi ? (cl < op && bok && bc < bo) : (cl > op && bok && bc > bo);
				bool aBack = !st.aDone && !bTk && st.aM.HasValue && st.aM.Value == minB && (isHi ? cl < aL : cl > aL);
				bool bBack = !st.bDone && !aTk && st.bM.HasValue && st.bM.Value == minB && bok && (isHi ? bc < bL : bc > bL);
				if (aBack && t - st.aT.Value > 15) aBack = false;      // entry paa sweep-candlen eller den naeste
				if (bBack && t - st.bT.Value > 15) bBack = false;
				bool slOK = isHi ? m1Hi.Value - cl <= MAX_SL : cl - m1Lo.Value <= MAX_SL;
				if (dirOK && (aBack || bBack) && !slOK) st.aDone = st.bDone = true;
				if (dirOK && (aBack || bBack) && slOK)
				{
					h.fired = true; h.isShort = isHi; h.lvl = aL; h.src = lvlNm;
					h.who = aBack && bBack ? "NQ + ES" : (aBack ? "NQ" : "ES");
					st.aDone = st.bDone = true;
				}
			}
		}

		private void VergenceArme(string dstr)
		{
			foreach (bool side in new bool[] { true, false })
			{
				VSide sd = vSide[side];
				if (sd.neu)
				{
					List<Frisk> fa = sd.aF.FindAll(f => !f.brugt && sd.bF.Exists(g => g.key == f.key && Math.Abs(g.m - f.m) <= VRG_GAP));
					List<Frisk> fb = sd.bF.FindAll(f => !f.brugt && sd.aF.Exists(g => g.key == f.key && Math.Abs(g.m - f.m) <= VRG_GAP));
					if (fa.Count > 0 || fb.Count > 0)
					{
						List<Frisk> faN = fa.FindAll(f => f.m == minB), fbN = fb.FindAll(f => f.m == minB);
						if (faN.Count > 0 || fbN.Count > 0) { fa = faN; fb = fbN; }
						HashSet<long> mA = new HashSet<long>(), mB = new HashSet<long>();
						foreach (Frisk f in fa) mA.Add(f.m);
						foreach (Frisk f in fb) mB.Add(f.m);
						fa = sd.aF.FindAll(f => mA.Contains(f.m));
						fb = sd.bF.FindAll(f => mB.Contains(f.m));
						if (VRG_SHARED)
						{
							// kun niveauer begge indeks har taget (fx 15m low 15:15) - ikke NQ's NY PRE low alene
							List<Frisk> aAll = sd.aF, bAll = sd.bF;
							fa = fa.FindAll(f => bAll.Exists(g => g.key == f.key));
							fb = fb.FindAll(f => aAll.Exists(g => g.key == f.key));
						}
						double? aLv = null, bLv = null;
						foreach (Frisk f in fa) aLv = !aLv.HasValue ? f.lv : (side ? Math.Max(aLv.Value, f.lv) : Math.Min(aLv.Value, f.lv));
						foreach (Frisk f in fb) bLv = !bLv.HasValue ? f.lv : (side ? Math.Max(bLv.Value, f.lv) : Math.Min(bLv.Value, f.lv));
						SortedSet<string> navne = new SortedSet<string>(StringComparer.Ordinal);
						foreach (Frisk f in fa) { navne.Add(f.key); f.brugt = true; }
						foreach (Frisk f in fb) { navne.Add(f.key); f.brugt = true; }
						sd.had = true;
						h.varmList.Add(new Arm { side = side, va = aLv, vb = bLv, info = "", names = string.Join(" / ", navne) });
					}
				}
				sd.neu = false;
			}
			// entry skal komme i samme minut som det sweep der fuldendte Vergence
			vArms = vArms.FindAll(v => FloorDiv(v.t, 60) == minB);
			foreach (Arm a in h.varmList)
				if (!mBad) { a.t = t; vArms.Add(a); }
			if (vArms.Count > 0 && !mBad)
			{
				List<Arm> keep = new List<Arm>();
				foreach (Arm v in vArms)
				{
					if (t - v.t > 15) continue;                          // for sent efter sweepet
					bool aD = v.side ? cl < op : cl > op;
					bool bD = bok && (v.side ? bc < bo : bc > bo);
					if (!(aD && bD)) { keep.Add(v); continue; }
					VSide sdv = vSide[v.side];
					long am = FloorDiv(v.t, 60);
					double? va = v.va, vb = v.vb;
					if (!VRG_SHARED && sdv.aFM.HasValue && sdv.aFM.Value == am && sdv.bFM.HasValue && sdv.bFM.Value == am)
					{
						if (!va.HasValue) va = sdv.aFL;
						if (!vb.HasValue) vb = sdv.bFL;
					}
					bool backA = !va.HasValue || (v.side ? cl < va.Value : cl > va.Value);
					bool backB = !vb.HasValue || (bok && (v.side ? bc < vb.Value : bc > vb.Value));
					bool slOK = v.side ? m1Hi.Value - cl <= MAX_SL : cl - m1Lo.Value <= MAX_SL;
					if (backA && backB && slOK && !h.fired)
					{
						h.fired = true; h.isShort = v.side; h.lvl = va; h.src = v.names; h.info = v.info;
						h.who = va.HasValue && vb.HasValue ? "Begge" : (va.HasValue ? "NQ" : "ES");
					}
				}
				vArms = keep;
			}
		}

		private void NyHandel(DateTime lt, DateTime dk, bool isOpenM, List<SmtBegivenhed> ud)
		{
			bool sh = h.isShort;
			double px = cl;
			// BE-kandidater: (niveau, navn, allerede taget)
			List<Tuple<double?, string, bool>> cands = new List<Tuple<double?, string, bool>>();
			bool eAct = sh ? uAct : dAct;
			if (eAct)
			{
				double elo = sh ? uBot : dBot, ehi = sh ? uTop : dTop;
				cands.Add(Tuple.Create((double?)((elo + ehi) / 2), "EQ", false));
				cands.Add(Tuple.Create((double?)(elo + (sh ? 0.75 : 0.25) * (ehi - elo)), sh ? "0.75" : "0.25", false));
			}
			if (!preDHitM.HasValue) cands.Add(Tuple.Create(preD, "EQ foer open", false));
			if (!preUHitM.HasValue) cands.Add(Tuple.Create(preU, "EQ foer open", false));
			foreach (Tuple<string, Sess> ns in new Tuple<string, Sess>[] { Tuple.Create("Asia", asia), Tuple.Create("London", lon), Tuple.Create("NY PRE", ny) })
			{
				St st = sh ? ns.Item2.lo : ns.Item2.hi;
				if (st != null && !st.aPre)
					cands.Add(Tuple.Create(sh ? ns.Item2.aLo : ns.Item2.aHi, ns.Item1 + (sh ? " low" : " high"), st.aTook));
			}
			foreach (Lv m in lv15)
				if (m.isHi != sh && !m.dead && !m.st.aTook) cands.Add(Tuple.Create((double?)m.a, sh ? "15m low" : "15m high", false));
			if (isOpenM)
				foreach (Lv m in lv05)
					if (m.isHi != sh && !m.dead && !m.st.aTook) cands.Add(Tuple.Create((double?)m.a, sh ? "5m low" : "5m high", false));
			double? be = null;
			string beS = "-";
			bool beBad = false;
			foreach (Tuple<double?, string, bool> c in cands)
			{
				if (!c.Item1.HasValue) continue;
				double cv = c.Item1.Value, d = Math.Abs(px - cv);
				if ((sh ? cv < px : cv > px) && d >= BE_MIN && d <= BE_MAX && (!be.HasValue || d < Math.Abs(px - be.Value)))
				{ be = cv; beS = c.Item2; beBad = c.Item3; }
			}
			// liq i trade-retningen taget i entry-minuttet (foer entry-candlen) -> BE-spottet er taget
			bool eqT = AnyHit(sh ? hitsU : hitsD, sh, px), slT = AnyHit(sh ? hitsSL : hitsSH, sh, px);
			if (eqT || slT)
			{
				beBad = true;
				beS = eqT ? (sh ? "bullish EQ" : "bearish EQ") : (sh ? "session low" : "session high");
			}
			double sl = sh ? Math.Max(m1Hi.Value, px + MIN_SL) : Math.Min(m1Lo.Value, px - MIN_SL);
			List<Tuple<double, string>> tcs = new List<Tuple<double, string>>();
			if (uAct) tcs.Add(Tuple.Create((uBot + uTop) / 2, "EQ"));
			if (dAct) tcs.Add(Tuple.Create((dBot + dTop) / 2, "EQ"));
			foreach (Tuple<string, Sess> ns in new Tuple<string, Sess>[] { Tuple.Create("Asia", asia), Tuple.Create("London", lon), Tuple.Create("NY PRE", ny) })
			{
				St st = sh ? ns.Item2.lo : ns.Item2.hi;
				double? v = sh ? ns.Item2.aLo : ns.Item2.aHi;
				if (st != null && !st.aTook && v.HasValue) tcs.Add(Tuple.Create(v.Value, ns.Item1 + (sh ? " low" : " high")));
			}
			double? tp = null;
			string tpS = "75p";
			foreach (Tuple<double, string> c in tcs)
			{
				double d = sh ? px - c.Item1 : c.Item1 - px;
				if (d >= TP_MIN && d <= TP_MAX && (!tp.HasValue || d < Math.Abs(px - tp.Value))) { tp = c.Item1; tpS = c.Item2; }
			}
			if (!tp.HasValue) tp = sh ? px - TP_MAX : px + TP_MAX;

			SmtHandel rec = new SmtHandel
			{
				Dato = lt.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture), Tid = dk.ToString("HH:mm:ss", CultureInfo.InvariantCulture), Kort = sh, Niveau = h.src, Swept = h.who, Info = h.info,
				Entry = px, Be = be, BeKilde = beS, T = t
			};
			if (beBad)
			{
				rec.Status = "UGYLDIG (BE allerede ramt)";
				Handler.Add(rec);
				ud.Add(new SmtBegivenhed(SmtType.Ugyldig, rec, px));
				return;
			}
			if (o != null)
			{
				o.rec.Resultat = "AFLOEST";
				o.rec.Exit = dk.ToString("HH:mm:ss", CultureInfo.InvariantCulture);
				ud.Add(new SmtBegivenhed(SmtType.Afloest, o.rec, px));
			}
			rec.Sl = sl; rec.Tp = tp; rec.TpKilde = tpS; rec.Status = "OK"; rec.Resultat = "AABEN";
			Handler.Add(rec);
			ud.Add(new SmtBegivenhed(SmtType.Ny, rec, px));
			lastTradeM = minB;
			o = new Aaben { kort = sh, entry = px, sl = sl, tp = tp.Value, be = be, rec = rec };
		}

		private bool AnyHit(List<KeyValuePair<long, double>> hits, bool sh, double px)
		{
			long m0 = minB * 60;
			foreach (KeyValuePair<long, double> x in hits)
				if (x.Key >= m0 && x.Key < t)
				{
					double d = sh ? px - x.Value : x.Value - px;
					if (d >= -BE_MIN) return true;
				}
			return false;
		}

		private static long FloorDiv(long a, long b) { long q = a / b; if ((a % b != 0) && ((a < 0) != (b < 0))) q--; return q; }
	}
}
