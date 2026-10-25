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
//   - Kurvefilter: SMT 25, Vergence 0. Kurverne deles med de enkelte strategier (ODIN\kurve_<model>.csv).
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
using NinjaTrader.NinjaScript.Strategies.Odin;

namespace NinjaTrader.NinjaScript.Strategies
{
	public class OdinSamlet : Strategy
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

		private Ben hugin, munin, gungner, sleipner;
		private Ben[] ben;
		private TimeZoneInfo newYork;
		private readonly DateTime epoke = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);
		private int ocoTaeller;

		// NQ-bar der venter paa ES-baren med samme tid
		private bool venter, dataAdvaret;
		private DateTime statusDag = DateTime.MinValue;
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
				Name = "OdinSamlet";
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
				Stoerrelse = OdinStoerrelse.Fast;
				KontoStart = 7692;
				BrugKontoSaldo = true;
				SwingTil = true; SwingAntal = 2; SwingRisikoPct = 2.5;
				MoTil = true; MoAntal = 1; MoRisikoPct = 1.5;
				SmtTil = true; SmtAntal = 5; SmtRisikoPct = 2.0; SmtKurve = 25;
				VergenceTil = true; VergenceAntal = 5; VergenceRisikoPct = 2.0; VergenceKurve = 0;
				LukMoVedModsat = true;
				PapirVedModsat = true;
				HalverSammeVej = false;
				MaksIAlt = 40;
				DiscordTradeLog = "";
				SkrivLogfil = true;
				OdinServer = "http://79.108.164.132/odin/indtag";
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
			// dagens status for Swing og Market Open, een linje ved market open (09:29:45-baren)
			if (ny.TimeOfDay == new TimeSpan(9, 29, 45) && ny.Date != statusDag)
			{
				statusDag = ny.Date;
				Print(string.Format("{0} ODIN status: Swing {1} | Market Open {2}", slut, SwingStatusTekst(), MoStatusTekst()));
			}
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

		private static string Rv5Tekst(double? rv5)
		{
			return rv5.HasValue ? rv5.Value.ToString("0.00", CultureInfo.InvariantCulture) : "ukendt";
		}

		private string SwingStatusTekst()
		{
			Motor m = hugin.M;
			string rv = " (rv5 " + Rv5Tekst(m.Rv5) + ")";
			if (!SwingTil) return "slaaet fra";
			if (!m.HarSwing) return "intet signal" + rv;
			if (!m.Rv5.HasValue) return "sprunget over - rv5 kendes ikke endnu";
			if (!m.HandelTilladt()) return "sprunget over - rv5 " + Rv5Tekst(m.Rv5) + " er for hoej (graense " + m.Ind.Rv5Graense.ToString("0.00", CultureInfo.InvariantCulture) + ") eller fridag";
			if (m.Ind.Rv5Min > 0 && m.Rv5.Value < m.Ind.Rv5Min) return "sprunget over - rv5 " + Rv5Tekst(m.Rv5) + " er for lav (under " + m.Ind.Rv5Min.ToString("0.00", CultureInfo.InvariantCulture) + ")";
			return "signal " + (m.SwingKort ? "SHORT" : "LONG") + rv;
		}

		private string MoStatusTekst()
		{
			Motor m = munin.M;
			string rv = " (rv5 " + Rv5Tekst(m.Rv5) + ")";
			if (!MoTil) return "slaaet fra";
			if (!m.Rv5.HasValue) return "sprunget over - rv5 kendes ikke endnu";
			switch (m.MoRetning)
			{
				case "INGEN": return "intet signal (ingen swing at foelge)" + rv;
				case "SPRING OVER": return "sprunget over - rv5 " + Rv5Tekst(m.Rv5) + " er for hoej (graense " + m.Ind.Rv5Graense.ToString("0.00", CultureInfo.InvariantCulture) + ") eller fridag";
				case "SHORT":
				case "LONG": return m.MoRetning + rv;
				default: return "ingen beslutning" + rv;
			}
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
			string mappe = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "ODIN");
			Directory.CreateDirectory(mappe);
			return mappe;
		}

		private string KurveFil(Ben b) { return Path.Combine(OdinMappe(), "kurve_" + b.Model + ".csv"); }

		private void LaesKurve(Ben b)
		{
			b.Kurve.Clear();
			try
			{
				if (!File.Exists(KurveFil(b))) return;
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
			if (Stoerrelse == OdinStoerrelse.Fast)
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
		public OdinStoerrelse Stoerrelse { get; set; }

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

		[Display(Name = "Skriv handler til ODIN\\handler.csv", Order = 2, GroupName = "8. Log")]
		public bool SkrivLogfil { get; set; }

		[Display(Name = "ODIN-server (indtag)", Order = 3, GroupName = "8. Log")]
		public string OdinServer { get; set; }

		[Display(Name = "ODIN-token", Order = 4, GroupName = "8. Log")]
		public string OdinToken { get; set; }
		#endregion
	}
}
