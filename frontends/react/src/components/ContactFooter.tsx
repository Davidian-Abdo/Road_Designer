const SOFTWARE_LINKS = [
  {
    name: "Gantt-Chart-Builder V1.0",
    url: "https://gantt-chart-builder.streamlit.app/",
    description:
      "Génération de gantt-chart téléchargeable interactive offline à partir d'un fichier Excel.",
  },
];

export function ContactFooter() {
  return (
    <footer className="mx-auto mt-10 max-w-6xl border-t border-navy/15 px-6 py-8">
      <div className="mb-1 text-lg font-extrabold text-navy sm:text-xl">
        Un logiciel métier à construire ?
      </div>
      <p className="max-w-4xl text-sm text-muted">
        Si vous avez une idée de logiciel, un problème technique à résoudre ou un workflow
        répétitif qui prend trop de temps, contactez BeamStack. Nous transformons vos méthodes,
        calculs et livrables en outils professionnels, clairs et accessibles.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <a
          href="mailto:Askdaoudi@gmail.com"
          className="inline-flex min-h-9 items-center rounded-md border border-navy/15 bg-white px-3 py-2 text-sm font-bold text-navy hover:border-accent/60 hover:text-accent"
        >
          Contact : Askdaoudi@gmail.com
        </a>
      </div>
      <div className="mt-4 text-sm font-bold text-accent">Voir nos logiciels</div>
      <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {SOFTWARE_LINKS.map((link) => (
          <div key={link.url} className="border-l-[3px] border-accent/80 bg-panel/80 px-3 py-3">
            <a
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-bold text-navy hover:text-accent"
            >
              {link.name}
            </a>
            <div className="mt-1 text-xs text-muted">{link.description}</div>
          </div>
        ))}
      </div>
    </footer>
  );
}
