// Entirely synthetic issuers, market participants, sources and dates.
const root = "https://alva.example",
  period = "FY2029-Q4";
export const identity = { name: "Alva Optics plc", isin: "GB0000000034", symbol: "ALVO" };
const document = (path, title, text, tags) => ({ url: root + "/" + path, title, text, tags });
function calendar(stamp, dateText) {
  return document(
    "calendar",
    "Alva Optics plc investor reporting calendar",
    stamp +
      " 08:00 UTC. Alva Optics plc (ALVO, GB0000000034) Investor Relations. Fiscal Q4 FY2029 results release: " +
      dateText +
      ". This is a release, not an investor call. London local time.",
    "calendar issuer investor earnings schedule release finanzkalender termine",
  );
}
const decoy = document(
  "namesake",
  "Alva Optical Holdings (ALVH) calendar",
  "Unrelated issuer Alva Optical Holdings, ALVH, will report on January 9.",
  "calendar issuer",
);
const consensus = document(
  "survey",
  "Signal Desk pre-release analyst survey",
  "2030-01-23 09:00 UTC, Signal Desk, Mira Fan: Alva Optics Q4 FY2029. Median GAAP revenue GBP 102 million from 5 sell-side analysts (range 96 to 110). Alder Research's Lima Roy expects contract renewals to support margins; Birch Securities' Theo Yen expects warranty claims to weigh on margins. Survey not representative of all investors.",
  "analyst expectations estimates sentiment consensus forecast preview opinions margins gegenposition",
);
const later = document(
  "later",
  "Later update on reported results",
  "2030-01-26 15:00 UTC, Signal Desk. Analysts now expect 777 million for next quarter after figures were published.",
  "analyst sentiment consensus preview",
);
const actual = document(
  "results",
  "Alva Optics Q4 FY2029 results release",
  "2030-01-25 08:00 UTC. Alva Optics plc (ALVO) Q4 FY2029 complete release: revenue GBP 105 million GAAP, diluted EPS GBP 0.42 GAAP. Management guides FY2030 operating margin to 12–13% on renewals. No analyst statements.",
  "issuer release actual results guidance operating",
);
const correction = document(
  "correction",
  "Alva Optics corrected Q4 FY2029 report",
  "Correction issued 2030-01-28 07:00 UTC: Alva Optics plc Q4 FY2029 corrects GAAP revenue to GBP 103 million from GBP 105 million due to a duplicate invoice. FY2030 margin guidance unchanged.",
  "issuer release actual amendment correction guidance",
);
const reaction = document(
  "responses",
  "Post-release views on Alva",
  "2030-01-25 12:00 UTC, Market Ledger by Bo Lee: Alder Research's Lima Roy sees repeat orders underpinning margin guidance. Birch Securities' Theo Yen highlights warranty provisioning left unresolved by management. Both referred to the Alva Optics Q4 FY2029 release; neither attributed the stock move to a single cause.",
  "post release analyst reaction views sentiment commentary reasons interpretation",
);
const price = document(
  "price",
  "ALVO exchange observation",
  "London Exchange 2030-01-25 16:30 UTC close: ALVO gained 2% from the prior close on January 24 to close January 25. No motive or analyst comment provided.",
  "observed market price performance exchange reaction return",
);
const stale = document(
  "old",
  "Prior quarter expectations",
  "2029-10-21 10:00 UTC. Two brokers discussing Q3 FY2029. No Q4 estimates.",
  "analyst estimates consensus",
);
const schedule = {
  period,
  report_type: "quarter",
  day: "2030-01-25",
  zone: "Europe/London",
  certainty: "confirmed",
  precision: "exact",
  local_time: "08:00",
  source: { url: root + "/calendar" },
};
const cases = {};
for (const [id, stamp, label, precision] of [
  ["nov", "2029-11-10", "January 2030", "month"],
  ["dec", "2029-12-25", "late January 2030", "late_month"],
  ["jan", "2030-01-14", "25 January 2030 at 08:00 London time", "exact"],
]) {
  cases[id] = { phase: "calendar", stamp, docs: [decoy, calendar(stamp, label)], precision };
}
cases.preview = { phase: "preview", stamp: "2030-01-24", docs: [consensus, later, stale, decoy] };
cases.actual = { phase: "actual", stamp: "2030-01-25", docs: [actual, price, reaction], candidate: actual };
cases.review = {
  phase: "review",
  stamp: "2030-01-25",
  docs: [actual, reaction, price],
  history: [
    {
      kind: "actual",
      body: {
        release: "full",
        source: { url: actual.url },
        facts: [{ metric: "revenue", value: "105", period }],
        guidance: "FY2030 operating margin 12–13%",
      },
    },
    {
      kind: "preview",
      body: {
        facts: [
          {
            value_kind: "consensus",
            metric: "revenue",
            value: "102",
            unit: "million",
            currency: "GBP",
            basis: "GAAP",
            period,
          },
        ],
      },
    },
  ],
};
cases.price_only = { ...cases.review, docs: [actual, price, stale] };
cases.sparse = { phase: "preview", stamp: "2030-01-24", docs: [stale, later, decoy] };
cases.correction = {
  phase: "actual",
  stamp: "2030-01-28",
  docs: [correction, actual, stale],
  candidate: correction,
};
export { cases, schedule };
export function searchFixture(docs, query) {
  const words = query.toLowerCase().match(/[\p{L}\p{N}]+/gu) || [];
  const intent = query.toLowerCase();
  const interested = {
    survey: /analy|consens|konsens|forecast|estimat|erwart|margin|stimmung|sentiment/,
    later: /analy|consens|konsens|forecast|estimat|erwart|stimmung|sentiment/,
    responses:
      /analy|comment|reaction|view|kommentar|re[aä]ktion|stimm|investor|broker|market|meinung|sell.side/,
    price: /pric|return|kurs|exchange|börse|close|perf[oó]rm|performance|market|markt|share|stock|trading/,
  };
  return docs
    .filter((doc) => (interested[doc.url.split("/").pop()] || /.*/).test(intent))
    .map((doc) => ({
      doc,
      score: words.reduce((n, w) => n + Number((doc.tags + " " + doc.title).toLowerCase().includes(w)), 0),
    }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 4)
    .map(({ doc }) => ({ url: doc.url, title: doc.title }));
}
