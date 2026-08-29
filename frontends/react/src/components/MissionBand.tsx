const FLOW = [
  { label: "1. Entrées", text: "Axe TXT, terrain CSV, catégorie REFT et cartouche." },
  { label: "2. Calcul", text: "Ligne rouge optimisée, profils et cubatures cohérents." },
  { label: "3. Livrables", text: "DXF, XLSX, PDF plan et PDF profils en travers." },
  { label: "4. Idée logicielle", text: "Un workflow répétitif peut devenir un outil métier BeamStack." },
];

export function MissionBand() {
  return (
    <section className="mx-auto mt-2 max-w-6xl px-6">
      <div className="rounded-lg border border-navy/10 bg-white p-5">
        <div className="mb-2 text-xs font-bold uppercase tracking-wide text-accent">
          Outil métier pour bureaux d'études
        </div>
        <p className="mb-4 max-w-4xl text-sm leading-relaxed text-[#2e394c] sm:text-base">
          Road Designer transforme un axe en plan et un MNT en livrables prêts à relire : plan,
          profil en long, profils en travers, cubatures, Bruckner, Excel et PDFs. BeamStack
          construit ce type d'outils pour rendre les workflows d'ingénierie de haut niveau
          accessibles aux petites équipes comme aux grandes structures.
        </p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {FLOW.map((item) => (
            <div key={item.label} className="border-t-2 border-accent/80 pt-2">
              <div className="text-xs font-bold text-ink">{item.label}</div>
              <div className="mt-1 text-xs text-muted">{item.text}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
