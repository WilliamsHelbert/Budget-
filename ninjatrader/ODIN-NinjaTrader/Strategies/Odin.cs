// ODIN - Magnus' suite til NinjaTrader 8.
//   OdinHugin      Hugin - swing paa formarkedets high/low (stop 40, stop til entry ved +75, ud 11:00 New York)
//   OdinMunin      Munin - market open (1 minut fra 09:29:45-barens luk, stop 30)
//   OdinGungner    Gungner - SMT / Sweep Trade (kurvefilter 10)
//   OdinSleipner   Sleipner - Vergence (uden kurvefilter)
// Reglerne ligger i OdinMotor.cs (Hugin/Munin) og OdinSmtMotor.cs (Gungner/Sleipner). Begge er testet mod Python:
// 268/268 swing-, 331/331 market open-, 264/264 SMT- og 250/250 Vergence-handler ens, jan 2023 - okt 2026.
//
// OPSAETNING
//   Diagram:   det instrument der handles (MNQ), 15 sekunder, handelstider "CME US Index Futures ETH", mindst 10 dage.
//   Signaler:  NQ og ES paa 15 sekunder laegges til automatisk. Standard er NinjaTraders loebende kontrakt
//              ("NQ ##-##" / "ES ##-##"), der selv ruller. Diagrammets MNQ skal stadig skiftes ved rul (hvert kvartal).
//   Koer hver model som sin egen strategi paa samme diagram. Hver har sin egen position.
// EXITS
//   Hugin:     stop 40 point, stop til entry naar handlen har vaeret +75 (maalt ved barens luk, gaelder fra naeste bar),
//              intet TP, luk ved barens luk kl. 11:00 New York (17:00 dansk).
//   Munin:     stop 30 point, luk ved luk af 09:30:45-baren (efter 1 minut).
//   Gungner/   SL paa 1m-candlens top/bund (mindst 10), TP ved liquidity 35-75 eller 75, stop til entry naar BE-niveauet
//   Sleipner:  rammes (tidligst efter 2 lukkede 15s-candles). Ny handel afloeser en aaben handel.
// MODSAT AABENT TRADE (Gungner/Sleipner, kun live)
//   Har den ene model et rigtigt trade aabent, og giver den anden signal den modsatte vej, tages det nye kun paa papir
//   (det taeller stadig paa kurven). NinjaTrader kan ikke vaere long og short paa samme MNQ paa samme konto, og de to
//   ville hedge hinanden. Skete 4 gange 2022-2026 og sparede 1 R. De to strategier deler status via OdinFaelles.
// FLERE MODELLER PAA EN GANG (kun live - strategierne deler status via OdinFaelles)
//   Samme vej:  alt samme vej holdes under "Maks micros i alt" (Lucid: 40). Halv stoerrelse naar en anden model
//               er inde samme vej kan slaas til, men er fra: det kostede 3.446 $ paa 4 aar og sparede 54 $ i drawdown.
//   Modsat vej: Market Open lukkes, naar SMT eller Vergence gaar ind den modsatte vej (Market Open kommer
//               15 sek. foer og kan ikke vide det paa forhaand). Ellers tages den nye handel.
// KURVEFILTER (Gungner/Sleipner)
//   Motoren handler alle signaler paa papir. En handel tages kun rigtigt, naar papirkurven (sum af R) staar paa eller
//   over snittet af de N seneste kurvepunkter (N = "Kurvefilter", 0 = slaaet fra). Kurven gemmes i
//   Documents\NinjaTrader 8\ODIN\kurve_<model>.csv, saa den overlever genstart.
// STOERRELSE
//   Fast:      Antal kontrakter.
//   Procent:   andel af kontoen risikeret pr. handel (stoppet i dollars), mindst 1. Kontoen = KontoStart + strategiens
//              eget resultat (historisk) eller kontoens Net Liquidation (live, hvis BrugKontoSaldo).
// LOG (kun live og sim, ikke historiske handler)
//   Discord:   hver entry og exit sendes til webhooken i "Discord trade-log" (tom = slaaet fra).
//   Fil:       hver lukket handel skrives til Documents\NinjaTrader 8\ODIN\handler.csv (semikolon, dansk komma).
//   ODIN:      hver lukket handel sendes til ODIN-dashboardet ("ODIN-server", header X-Odin-Token). Tom = slaaet fra.

using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript.Strategies.Odin;

namespace NinjaTrader.NinjaScript.Strategies
{
	public enum OdinStoerrelse { Fast, ProcentAfKonto }

	// Faelles opslagstavle for strategierne i samme NinjaTrader: hvilken retning hver model har rigtigt aabent
	// pr. konto og instrument. Bruges til reglen om modsat aabent trade mellem Gungner og Sleipner.
	public static class OdinFaelles
	{
		private class Stilling
		{
			public MarketPosition Mp;
			public int Antal;
			public bool Bekraeftet;          // fra NinjaTraders position (ikke kun en indsendt ordre)
			public DateTime Tid;
		}

		private static readonly object laas = new object();
		private static readonly Dictionary<string, Stilling> aabne = new Dictionary<string, Stilling>();

		// Bekraeftet position (OnPositionUpdate) eller en ordre der lige er sendt (bekraeftet = false).
		public static void Saet(string noegle, MarketPosition mp, int antal, bool bekraeftet)
		{
			lock (laas) { aabne[noegle] = new Stilling { Mp = mp, Antal = antal, Bekraeftet = bekraeftet, Tid = DateTime.UtcNow }; }
		}

		private static Stilling Gyldig(Stilling s)
		{
			// en indsendt ordre der ikke er blevet til en position inden for et minut, taeller ikke
			if (s == null || s.Mp == MarketPosition.Flat) return null;
			if (!s.Bekraeftet && (DateTime.UtcNow - s.Tid).TotalSeconds > 60) return null;
			return s;
		}

		public static MarketPosition Hent(string noegle)
		{
			lock (laas)
			{
				Stilling s;
				aabne.TryGetValue(noegle, out s);
				s = Gyldig(s);
				return s == null ? MarketPosition.Flat : s.Mp;
			}
		}

		// Sum af kontrakter samme vej hos de ANDRE modeller paa samme konto og instrument.
		public static int AndreSammeVej(string prefix, string egenNoegle, MarketPosition vej)
		{
			lock (laas)
			{
				int sum = 0;
				foreach (KeyValuePair<string, Stilling> kv in aabne)
				{
					if (kv.Key == egenNoegle || !kv.Key.StartsWith(prefix, StringComparison.Ordinal)) continue;
					Stilling s = Gyldig(kv.Value);
					if (s != null && s.Mp == vej) sum += s.Antal;
				}
				return sum;
			}
		}
	}

	// ------------------------------------------------------------------ faelles: data, stoerrelse og log
	public abstract class OdinBase : Strategy
	{
		protected TimeZoneInfo newYork;
		private readonly DateTime epoke = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);
		protected const string Signal = "ODIN";

		// NQ-bar der venter paa ES-baren med samme tid
		private bool venter;
		private DateTime ventSlut;
		protected double vo, vh, vl, vc;
		private DateTime esSlut = DateTime.MinValue;
		protected double eo, eh, el, ec;

		// den aabne handel (til log)
		protected double aabenStopPt;
		protected bool beFlyttet;

		// log
		private static readonly HttpClient http = new HttpClient();
		protected static readonly CultureInfo dk = CultureInfo.GetCultureInfo("da-DK");
		private volatile string sidsteFejl;
		private double indPris;
		private int indAntal;
		private bool indKort;
		private DateTime indTid;

		protected abstract string Model { get; }
		protected abstract string Beskrivelse { get; }
		protected abstract int StandardAntal { get; }
		protected abstract double StandardRisikoPct { get; }
		protected virtual void Standarder() { }
		protected virtual void Klar() { }
		protected virtual void PaaEs(long t) { }
		protected abstract void PaaBar(DateTime slut, long t, DateTime ny, bool harE);

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Name = "Odin" + Model;
				Description = Beskrivelse;
				Calculate = Calculate.OnBarClose;
				EntriesPerDirection = 1;
				EntryHandling = EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy = true;
				ExitOnSessionCloseSeconds = 30;
				BarsRequiredToTrade = 0;
				StopTargetHandling = StopTargetHandling.PerEntryExecution;
				TraceOrders = false;

				NqInstrument = "NQ ##-##";
				EsInstrument = "ES ##-##";
				Stoerrelse = OdinStoerrelse.Fast;
				Antal = StandardAntal;
				RisikoPct = StandardRisikoPct;
				KontoStart = 7692;
				BrugKontoSaldo = true;
				DiscordTradeLog = "";
				SkrivLogfil = true;
				OdinServer = "http://79.108.164.132/odin/indtag";
				OdinToken = "";
				HalverSammeVej = false;
				MaksIAlt = 40;
				Standarder();
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
				Klar();
			}
			else if (State == State.Realtime)
				OdinFaelles.Saet(Noegle(Model), Position.MarketPosition, Position.Quantity, true);
			else if (State == State.Terminated && Account != null)
				OdinFaelles.Saet(Noegle(Model), MarketPosition.Flat, 0, true);
		}

		protected string Prefix()
		{
			return (Account != null ? Account.Name : "") + "|" + (Instrument != null ? Instrument.FullName : "") + "|";
		}

		protected string Noegle(string model) { return Prefix() + model; }

		protected override void OnPositionUpdate(Position position, double averagePrice, int quantity, MarketPosition marketPosition)
		{
			if (State == State.Realtime)
				OdinFaelles.Saet(Noegle(Model), marketPosition, quantity, true);
		}

		// Ny handel naar andre ODIN-modeller er aabne samme vej: halv stoerrelse og samlet loft. 0 = gaa ikke ind.
		protected int Juster(int antal, bool kort, out string note)
		{
			note = "";
			if (State != State.Realtime) return antal;
			MarketPosition vej = kort ? MarketPosition.Short : MarketPosition.Long;
			int andre = OdinFaelles.AndreSammeVej(Prefix(), Noegle(Model), vej);
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

		protected void Meld(bool kort, int antal)
		{
			if (State == State.Realtime)
				OdinFaelles.Saet(Noegle(Model), kort ? MarketPosition.Short : MarketPosition.Long, antal, false);
		}

		protected long Unix(DateTime ntTid)
		{
			return (long)(TimeZoneInfo.ConvertTimeToUtc(ntTid, NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo) - epoke).TotalSeconds;
		}

		protected override void OnBarUpdate()
		{
			if (BarsInProgress == 0 || CurrentBars[1] < 0 || CurrentBars[2] < 0)
				return;
			DateTime slut = Times[BarsInProgress][0];
			if (BarsInProgress == 1)
			{
				if (venter && ventSlut < slut)
					Behandl(ventSlut, false);                    // ES havde ingen bar paa den forrige tid
				venter = true; ventSlut = slut;
				vo = Opens[1][0]; vh = Highs[1][0]; vl = Lows[1][0]; vc = Closes[1][0];
				if (esSlut == slut)
					Behandl(slut, true);
			}
			else if (BarsInProgress == 2)
			{
				if (venter && ventSlut < slut)
					Behandl(ventSlut, false);                    // en aeldre NQ-bar faerdigbehandles foer ES-baren
				esSlut = slut;
				eo = Opens[2][0]; eh = Highs[2][0]; el = Lows[2][0]; ec = Closes[2][0];
				PaaEs(Unix(slut.AddSeconds(-15)));
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
			PaaBar(slut, Unix(start), ny, harE);
		}

		protected int Beregn(double stopPt)
		{
			if (Stoerrelse == OdinStoerrelse.Fast)
				return Antal;
			double konto = KontoStart + SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;
			if (BrugKontoSaldo && State == State.Realtime && Account != null)
				konto = Account.Get(AccountItem.NetLiquidation, Currency.UsDollar);
			double risiko = Math.Max(stopPt, TickSize) * Instrument.MasterInstrument.PointValue;
			return Math.Max(1, (int)Math.Floor(konto * RisikoPct / 100.0 / risiko));
		}

		protected override void OnExecutionUpdate(Execution execution, string executionId, double price, int quantity,
			MarketPosition marketPosition, string orderId, DateTime time)
		{
			if (State != State.Realtime || execution.Order == null || execution.Order.OrderState != OrderState.Filled)
				return;
			Order o = execution.Order;
			string instr = Instrument.MasterInstrument.Name;
			string konto = Account != null ? Account.Name : "";
			bool erEntry = o.Name == Signal;
			// en vending (fx Gungner der skifter retning) lukker den gamle handel og aabner en ny
			if (!erEntry || indAntal > 0)
			{
				if (indAntal > 0 && (!erEntry || o.Name == Signal))
				{
					double ud = o.AverageFillPrice;
					double pt = (ud - indPris) * (indKort ? -1 : 1);
					double usd = pt * Instrument.MasterInstrument.PointValue * indAntal;
					string grund = o.Name == "Stop loss" ? (beFlyttet ? "BE" : "stop") : o.Name == "Profit target" ? "TP"
						: o.Name == "Tid" ? "tid" : o.Name == Signal ? "afloest" : o.Name;
					if (!erEntry || marketPosition != (indKort ? MarketPosition.Short : MarketPosition.Long))
					{
						Send(string.Format(dk, "**ODIN {0}** lukket ({1}) · {2} {3} {4} {5:N2} → {6:N2} · {7:+0.00;-0.00} pt · **{8:+#,##0;-#,##0} $** · {9}",
							Model, grund, indKort ? "SHORT" : "LONG", indAntal, instr, indPris, ud, pt, usd, konto));
						if (SkrivLogfil)
							SkrivHandel(grund, ud, pt, usd, time, instr, konto);
						SendOdin(grund, ud, pt, usd, time, instr, konto);
						indAntal = 0;
					}
				}
				if (!erEntry)
					return;
			}
			indPris = o.AverageFillPrice; indAntal = Position.Quantity > 0 ? Position.Quantity : o.Filled; indTid = time;
			indKort = o.OrderAction == OrderAction.SellShort || o.OrderAction == OrderAction.Sell;
			double stop = indKort ? indPris + aabenStopPt : indPris - aabenStopPt;
			Send(string.Format(dk, "**ODIN {0}** {1} {2} {3} @ {4:N2} · stop {5:N2} · {6}", Model, indKort ? "SHORT" : "LONG",
				indAntal, instr, indPris, stop, konto));
		}

		private void Send(string tekst)
		{
			if (string.IsNullOrWhiteSpace(DiscordTradeLog))
				return;
			string json = "{\"content\":\"" + tekst.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n") + "\"}";
			string url = DiscordTradeLog.Trim();
			Task.Run(async () =>
			{
				try
				{
					ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
					HttpResponseMessage svar = await http.PostAsync(url, new StringContent(json, Encoding.UTF8, "application/json"));
					if (!svar.IsSuccessStatusCode)
						sidsteFejl = "Discord svarede " + (int)svar.StatusCode;
				}
				catch (Exception ex) { sidsteFejl = ex.Message; }
			});
		}

		private void SendOdin(string grund, double ud, double pt, double usd, DateTime tid, string instr, string konto)
		{
			if (string.IsNullOrWhiteSpace(OdinServer))
				return;
			TimeZoneInfo ntZone = NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo;
			DateTime indNy = TimeZoneInfo.ConvertTime(indTid, ntZone, newYork), udNy = TimeZoneInfo.ConvertTime(tid, ntZone, newYork);
			CultureInfo ic = CultureInfo.InvariantCulture;
			double risiko = aabenStopPt * Instrument.MasterInstrument.PointValue * indAntal;
			string id = string.Format(ic, "{0}-{1:yyyyMMdd-HHmmss}-{2}", Model, indNy, konto);
			string json = string.Format(ic,
				"{{\"id\":\"{0}\",\"model\":\"{1}\",\"dato\":\"{2:yyyy-MM-dd}\",\"ind\":\"{2:HH:mm:ss}\",\"ud\":\"{3:HH:mm:ss}\"," +
				"\"retning\":\"{4}\",\"antal\":{5},\"entry\":{6},\"exit\":{7},\"grund\":\"{8}\",\"point\":{9},\"dollars\":{10}," +
				"\"risiko\":{11},\"instrument\":\"{12}\",\"konto\":\"{13}\"}}",
				Json(id), Model, indNy, udNy, indKort ? "short" : "long", indAntal, indPris, ud, Json(grund),
				Math.Round(pt, 2), Math.Round(usd, 2), Math.Round(risiko, 2), Json(instr), Json(konto));
			string url = OdinServer.Trim(), token = (OdinToken ?? "").Trim();
			Task.Run(async () =>
			{
				try
				{
					HttpRequestMessage besked = new HttpRequestMessage(HttpMethod.Post, url);
					besked.Content = new StringContent(json, Encoding.UTF8, "application/json");
					if (token.Length > 0)
						besked.Headers.Add("X-Odin-Token", token);
					HttpResponseMessage svar = await http.SendAsync(besked);
					if (!svar.IsSuccessStatusCode)
						sidsteFejl = "ODIN-serveren svarede " + (int)svar.StatusCode;
				}
				catch (Exception ex) { sidsteFejl = "ODIN-serveren: " + ex.Message; }
			});
		}

		private static string Json(string s)
		{
			return (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"");
		}

		protected static string OdinMappe()
		{
			string mappe = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "ODIN");
			Directory.CreateDirectory(mappe);
			return mappe;
		}

		private void SkrivHandel(string grund, double ud, double pt, double usd, DateTime tid, string instr, string konto)
		{
			try
			{
				string fil = Path.Combine(OdinMappe(), "handler.csv");
				bool ny = !File.Exists(fil);
				TimeZoneInfo ntZone = NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo;
				DateTime indNy = TimeZoneInfo.ConvertTime(indTid, ntZone, newYork), udNy = TimeZoneInfo.ConvertTime(tid, ntZone, newYork);
				CultureInfo ic = CultureInfo.InvariantCulture;
				using (StreamWriter w = new StreamWriter(fil, true, new UTF8Encoding(ny)))
				{
					if (ny)
						w.WriteLine("dato;ind (NY);ud (NY);model;retning;antal;entry;exit;grund;point;dollars;instrument;konto");
					w.WriteLine(string.Join(";", new string[] {
						indNy.ToString("yyyy-MM-dd", ic), indNy.ToString("HH:mm:ss", ic), udNy.ToString("HH:mm:ss", ic), Model, indKort ? "short" : "long",
						indAntal.ToString(ic), indPris.ToString("0.00", dk), ud.ToString("0.00", dk), grund, pt.ToString("0.00", dk),
						usd.ToString("0.00", dk), instr, konto }));
				}
			}
			catch (Exception ex) { Print(Name + " kunne ikke skrive logfil: " + ex.Message); }
		}

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
		[Range(1, int.MaxValue)]
		[Display(Name = "Antal (fast)", Order = 2, GroupName = "2. Stoerrelse")]
		public int Antal { get; set; }

		[NinjaScriptProperty]
		[Range(0.1, 20)]
		[Display(Name = "Risiko % af konto", Order = 3, GroupName = "2. Stoerrelse")]
		public double RisikoPct { get; set; }

		[NinjaScriptProperty]
		[Range(100, double.MaxValue)]
		[Display(Name = "Konto ved start ($)", Order = 4, GroupName = "2. Stoerrelse")]
		public double KontoStart { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "Brug kontoens saldo live", Order = 5, GroupName = "2. Stoerrelse")]
		public bool BrugKontoSaldo { get; set; }

		[Display(Name = "Discord trade-log (webhook)", Order = 1, GroupName = "3. Log")]
		public string DiscordTradeLog { get; set; }

		[Display(Name = "Skriv handler til ODIN\\handler.csv", Order = 2, GroupName = "3. Log")]
		public bool SkrivLogfil { get; set; }

		[Display(Name = "ODIN-server (indtag)", Order = 3, GroupName = "3. Log")]
		public string OdinServer { get; set; }

		[Display(Name = "ODIN-token", Order = 4, GroupName = "3. Log")]
		public string OdinToken { get; set; }

		[NinjaScriptProperty]
		[Display(Name = "Halv stoerrelse hvis en anden model er inde samme vej", Order = 1, GroupName = "5. Flere modeller")]
		public bool HalverSammeVej { get; set; }

		[NinjaScriptProperty]
		[Range(0, 1000)]
		[Display(Name = "Maks micros i alt samme vej (0 = intet loft)", Order = 2, GroupName = "5. Flere modeller")]
		public int MaksIAlt { get; set; }
		#endregion
	}

	// ------------------------------------------------------------------ Hugin og Munin (OdinMotor.cs)
	public abstract class OdinRavnBase : OdinBase
	{
		private Motor motor;
		private MotorOrdre aaben;

		protected abstract string OrdreNavn { get; }         // motorens ordre: "SWING" eller "MO"
		protected abstract MotorIndstillinger Regler();

		protected override void Klar() { motor = new Motor(Regler()); }

		protected override void PaaBar(DateTime slut, long t, DateTime ny, bool harE)
		{
			// 1) den aabne handel: tidsudgang og BE (som motor/broker.py: foer motoren ser baren)
			if (aaben != null && Position.MarketPosition != MarketPosition.Flat)
			{
				MarketPosition modsat = aaben.Kort ? MarketPosition.Long : MarketPosition.Short;
				bool smtModsat = OrdreNavn == "MO" && State == State.Realtime &&
					(OdinFaelles.Hent(Noegle("Gungner")) == modsat || OdinFaelles.Hent(Noegle("Sleipner")) == modsat);
				if (smtModsat)
				{
					if (aaben.Kort) ExitShort(0, Position.Quantity, "Modsat SMT", Signal);
					else ExitLong(0, Position.Quantity, "Modsat SMT", Signal);
					Print(string.Format("{0} {1}: lukket - SMT/Vergence gik ind den modsatte vej", slut, Name));
				}
				else if (t + 15 >= aaben.UdTid)
				{
					if (aaben.Kort) ExitShort(0, Position.Quantity, "Tid", Signal);
					else ExitLong(0, Position.Quantity, "Tid", Signal);
				}
				else if (aaben.BePt > 0 && !beFlyttet)
				{
					double e = Position.AveragePrice;
					double bedst = aaben.Kort ? e - vl : vh - e;
					if (bedst >= aaben.BePt)
					{
						beFlyttet = true;
						double nyStop = aaben.Kort ? e - aaben.BeLaas : e + aaben.BeLaas;
						SetStopLoss(Signal, CalculationMode.Price, nyStop, false);
						Print(string.Format("{0} {1} BE: stop flyttet til {2}", slut, Name, nyStop));
					}
				}
			}
			else if (aaben != null && Position.MarketPosition == MarketPosition.Flat)
				aaben = null;

			// 2) motoren
			foreach (MotorOrdre od in motor.PaaBar(t, ny, vo, vh, vl, vc, harE, eo, eh, el, ec))
			{
				if (od.Navn != OrdreNavn || Position.MarketPosition != MarketPosition.Flat)
					continue;
				string note;
				int antal = Juster(Beregn(od.StopPt), od.Kort, out note);
				if (antal < 1)
				{
					Print(string.Format("{0} {1}: sprunget over{2}", slut, Name, note));
					continue;
				}
				SetStopLoss(Signal, CalculationMode.Ticks, od.StopPt / TickSize, false);
				if (od.TpPt > 0)
					SetProfitTarget(Signal, CalculationMode.Ticks, od.TpPt / TickSize);
				aaben = od;
				aabenStopPt = od.StopPt;
				beFlyttet = false;
				Meld(od.Kort, antal);
				if (od.Kort) EnterShort(0, antal, Signal);
				else EnterLong(0, antal, Signal);
				Print(string.Format("{0} {1} {2} x{3} (rv5 {4}){5}", slut, Name, od.Kort ? "SHORT" : "LONG", antal,
					motor.Rv5.HasValue ? motor.Rv5.Value.ToString("0.00", CultureInfo.InvariantCulture) : "-", note));
			}
			if (OrdreNavn == "MO" && motor.MoRetning != null && ny.Hour == 9 && ny.Minute == 29 && ny.Second == 45)
				Print(string.Format("{0} {1}: {2}", slut, Name, motor.MoRetning));
		}
	}

	// Hugin - tanken: swingen paa formarkedets niveau
	public class OdinHugin : OdinRavnBase
	{
		protected override string Model { get { return "Hugin"; } }
		protected override string Beskrivelse { get { return "ODIN Hugin (swing): formarkedets high/low, stop 40, BE +75, ud 11:00 New York."; } }
		protected override string OrdreNavn { get { return "SWING"; } }
		protected override MotorIndstillinger Regler() { return MotorIndstillinger.PlanSwing(); }
		protected override int StandardAntal { get { return 2; } }
		protected override double StandardRisikoPct { get { return 2.5; } }
	}

	// Munin - hukommelsen: market open husker hvordan swingen gik
	public class OdinMunin : OdinRavnBase
	{
		protected override string Model { get { return "Munin"; } }
		protected override string Beskrivelse { get { return "ODIN Munin (market open): 1 minut, stop 30."; } }
		protected override string OrdreNavn { get { return "MO"; } }
		protected override MotorIndstillinger Regler() { return MotorIndstillinger.MarketOpen(); }
		protected override int StandardAntal { get { return 1; } }
		protected override double StandardRisikoPct { get { return 1.5; } }
	}

	// ------------------------------------------------------------------ Gungner og Sleipner (OdinSmtMotor.cs)
	public abstract class OdinSmtBase : OdinBase
	{
		private SmtMotor motor;
		private SmtHandel rigtig;                 // den handel der er aaben rigtigt (null = kun papir)
		private readonly List<double> kum = new List<double>();
		private string sidsteNoegle = "";         // seneste handel i kurvefilen (dato tid)

		protected abstract bool Vergence { get; }
		protected abstract int StandardKurve { get; }


		protected override void Standarder() { Kurvefilter = StandardKurve; }

		protected override void Klar()
		{
			motor = new SmtMotor(Vergence);
			LaesKurve();
		}

		private string KurveFil() { return Path.Combine(OdinMappe(), "kurve_" + Model + ".csv"); }

		// kurve_<model>.csv: dato;tid;R - en linje pr. afsluttet papirhandel (afloest = 0 R)
		private void LaesKurve()
		{
			kum.Clear();
			try
			{
				if (!File.Exists(KurveFil())) return;
				double sum = 0;
				foreach (string linje in File.ReadAllLines(KurveFil()))
				{
					string[] f = linje.Split(';');
					double r;
					if (f.Length < 3 || !double.TryParse(f[2], NumberStyles.Float, CultureInfo.InvariantCulture, out r)) continue;
					sum += r;
					kum.Add(sum);
					sidsteNoegle = f[0] + " " + f[1];
				}
				Print(string.Format("{0}: kurven har {1} handler, seneste {2}", Name, kum.Count, sidsteNoegle));
			}
			catch (Exception ex) { Print(Name + " kunne ikke laese kurven: " + ex.Message); }
		}

		private void TilKurve(SmtHandel x, double r)
		{
			string noegle = x.Dato + " " + x.Tid;
			if (string.CompareOrdinal(noegle, sidsteNoegle) <= 0) return;        // staar allerede i filen
			kum.Add((kum.Count > 0 ? kum[kum.Count - 1] : 0) + r);
			sidsteNoegle = noegle;
			try
			{
				File.AppendAllText(KurveFil(), string.Format(CultureInfo.InvariantCulture, "{0};{1};{2}\r\n", x.Dato, x.Tid, r));
			}
			catch (Exception ex) { Print(Name + " kunne ikke skrive kurven: " + ex.Message); }
		}

		private bool KurveOk()
		{
			int n = Kurvefilter;
			if (n <= 0 || kum.Count < n) return true;
			double snit = 0;
			for (int i = kum.Count - n; i < kum.Count; i++) snit += kum[i];
			return kum[kum.Count - 1] >= snit / n;
		}

		protected override void PaaEs(long t) { motor.PaaEs(t, eo, eh, el, ec); }

		protected override void PaaBar(DateTime slut, long t, DateTime ny, bool harE)
		{
			if (rigtig != null && Position.MarketPosition == MarketPosition.Flat)
				rigtig = null;
			foreach (SmtBegivenhed b in motor.PaaNq(t, ny, vo, vh, vl, vc))
			{
				SmtHandel x = b.Handel;
				switch (b.Type)
				{
					case SmtType.Lukket:
						TilKurve(x, x.R ?? 0);
						if (rigtig == x && Position.MarketPosition != MarketPosition.Flat)
							Luk("Papir lukket");                     // stop/TP burde allerede have lukket den
						rigtig = rigtig == x ? null : rigtig;
						break;
					case SmtType.Afloest:
						TilKurve(x, 0);
						break;
					case SmtType.Be:
						if (rigtig == x && Position.MarketPosition != MarketPosition.Flat && !beFlyttet)
						{
							beFlyttet = true;
							SetStopLoss(Signal, CalculationMode.Price, Position.AveragePrice, false);
							Print(string.Format("{0} {1} BE: stop flyttet til entry", slut, Name));
						}
						break;
					case SmtType.Ugyldig:
						Print(string.Format("{0} {1} {2} {3}: {4}", slut, Name, x.Kort ? "SHORT" : "LONG", x.Niveau, x.Status));
						break;
					case SmtType.Ny:
						NyHandel(slut, x);
						break;
				}
			}
		}

		private void NyHandel(DateTime slut, SmtHandel x)
		{
			bool ok = KurveOk();
			// den anden model har et rigtigt trade aabent den modsatte vej -> kun papir (kun live)
			string anden = Vergence ? "Gungner" : "Sleipner";
			MarketPosition andenMp = State == State.Realtime ? OdinFaelles.Hent(Noegle(anden)) : MarketPosition.Flat;
			bool modsat = andenMp != MarketPosition.Flat && andenMp != (x.Kort ? MarketPosition.Short : MarketPosition.Long);
			bool aabenSammeVej = rigtig != null && Position.MarketPosition == (x.Kort ? MarketPosition.Short : MarketPosition.Long);
			Print(string.Format(CultureInfo.InvariantCulture, "{0} {1} {2} {3} entry {4} SL {5} TP {6} BE {7} - {8}", slut, Name,
				x.Kort ? "SHORT" : "LONG", x.Niveau, x.Entry, x.Sl, x.Tp, x.Be.HasValue ? x.Be.Value.ToString(CultureInfo.InvariantCulture) : "-",
				!ok ? "papir (kurvefilter)" : modsat ? "papir (" + anden + " har et modsat trade aabent)" : "RIGTIG"));
			if (!ok || modsat)
			{
				if (rigtig != null && Position.MarketPosition != MarketPosition.Flat)
					Luk("Afloest");                                    // den gamle er afloest, den nye er kun papir
				rigtig = null;
				return;
			}
			double stopPt = Math.Abs(x.Entry - x.Sl.Value);
			aabenStopPt = stopPt;
			beFlyttet = false;
			SetStopLoss(Signal, CalculationMode.Price, x.Sl.Value, false);
			SetProfitTarget(Signal, CalculationMode.Price, x.Tp.Value);
			if (aabenSammeVej)
			{
				rigtig = x;                                            // samme vej: positionen fortsaetter med nyt SL/TP
				return;
			}
			string note;
			int antal = Juster(Beregn(stopPt), x.Kort, out note);
			if (antal < 1)
			{
				Print(string.Format("{0} {1}: kun papir{2}", slut, Name, note));
				if (rigtig != null && Position.MarketPosition != MarketPosition.Flat)
					Luk("Afloest");
				rigtig = null;
				return;
			}
			if (note.Length > 0)
				Print(string.Format("{0} {1}: x{2}{3}", slut, Name, antal, note));
			rigtig = x;
			Meld(x.Kort, antal);
			if (x.Kort) EnterShort(0, antal, Signal);                  // modsat vej: NinjaTrader vender positionen
			else EnterLong(0, antal, Signal);
		}

		private void Luk(string navn)
		{
			if (Position.MarketPosition == MarketPosition.Long) ExitLong(0, Position.Quantity, navn, Signal);
			else if (Position.MarketPosition == MarketPosition.Short) ExitShort(0, Position.Quantity, navn, Signal);
		}

		[NinjaScriptProperty]
		[Range(0, 200)]
		[Display(Name = "Kurvefilter (antal, 0 = fra)", Order = 1, GroupName = "4. Kurvefilter")]
		public int Kurvefilter { get; set; }
	}

	// Gungner - Odins spyd der altid rammer: SMT / Sweep Trade
	public class OdinGungner : OdinSmtBase
	{
		protected override string Model { get { return "Gungner"; } }
		protected override string Beskrivelse { get { return "ODIN Gungner (SMT): kun det ene indeks sweeper, close tilbage i samme minut. Kurvefilter 10."; } }
		protected override bool Vergence { get { return false; } }
		protected override int StandardKurve { get { return 10; } }
		protected override int StandardAntal { get { return 5; } }
		protected override double StandardRisikoPct { get { return 2.0; } }
	}

	// Sleipner - den ottebenede: Vergence (begge indeks tager samme niveau)
	public class OdinSleipner : OdinSmtBase
	{
		protected override string Model { get { return "Sleipner"; } }
		protected override string Beskrivelse { get { return "ODIN Sleipner (Vergence): begge indeks tager samme niveau. Uden kurvefilter."; } }
		protected override bool Vergence { get { return true; } }
		protected override int StandardKurve { get { return 0; } }
		protected override int StandardAntal { get { return 5; } }
		protected override double StandardRisikoPct { get { return 2.0; } }
	}
}
