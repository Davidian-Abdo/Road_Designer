export function Header() {
  return (
    <header className="border-b border-navy/15">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-5 px-6 py-4">
        <div className="text-3xl font-extrabold text-ink sm:text-4xl">BeamStack</div>
        <div className="hidden h-10 w-[3px] flex-none rounded bg-accent sm:block" aria-hidden />
        <div className="flex min-w-0 max-w-xl flex-col gap-0.5">
          <div className="text-sm font-bold uppercase text-[#263246]">
            Software solutions for engineers
          </div>
          <div className="text-sm text-muted">
            High-level engineering tools accessible to every engineer.
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-6 pb-3">
        <div className="border-l-[3px] border-accent bg-panel/80 px-4 py-3">
          <div dir="rtl" className="font-serif text-lg text-[#1f2937]">
            وَقُل رَّبِّ زِدْنِي عِلْمًا
          </div>
          <div className="mt-1 flex flex-wrap gap-4 text-xs text-muted">
            <span>said The Great Designer : Sourate Taha, 20:114</span>
            <span>« Seigneur, accrois-moi en science. »</span>
          </div>
        </div>
        <h1 className="mt-4 text-4xl font-extrabold text-navy sm:text-5xl">Road Designer V 1.0</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Génération de livrables BET (DXF + XLSX + PDF) à partir d'un fichier axe et d'un MNT.
          Standards REFT (Maroc). Toutes les annotations sont en français.
        </p>
      </div>
    </header>
  );
}
