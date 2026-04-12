const truthLensFeatures = [
  "Evidence-based verification",
  "Multi-modal analysis (text, image, video)",
  "Transparent reasoning with sources",
  "Built for real-world misinformation",
  "Cross-modal consistency checks",
  "Confidence scoring system",
];

function PixelTile() {
  const pattern = [
    [1, 1, 0, 1, 0, 1],
    [1, 0, 1, 1, 1, 0],
    [0, 1, 1, 0, 1, 1],
    [1, 1, 0, 1, 0, 0],
    [0, 1, 0, 1, 1, 1],
    [1, 0, 1, 0, 1, 0],
  ];
  return (
    <div className="grid grid-cols-6 gap-px rounded-sm border border-white/10 bg-white/10 p-1">
      {pattern.flatMap((row, ri) =>
        row.map((on, ci) => (
          <span
            key={`${ri}-${ci}`}
            className={`h-1.5 w-1.5 rounded-[1px] ${on ? "bg-violet-400" : "bg-emerald-400/70"}`}
          />
        )),
      )}
    </div>
  );
}

export default function SiteFeatureSixGrid() {
  return (
    <section className="border-b border-white/10 bg-black py-24 md:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-mono text-[11px] font-medium tracking-[0.2em] text-violet-400/90 uppercase">
            The Difference
          </h2>
          <h3 className="mt-4 text-3xl font-semibold tracking-[-0.03em] text-white md:text-4xl">TruthLens AI</h3>
        </div>

        <div className="mx-auto mt-16 grid max-w-6xl gap-px bg-white/10 sm:grid-cols-2 lg:grid-cols-3">
          {truthLensFeatures.map((feature, index) => (
            <div
              key={index}
              className="bg-black p-8 transition-[filter] duration-200 hover:brightness-110 md:p-10"
            >
              <div className="flex items-start gap-4">
                <PixelTile />
                <div className="min-w-0 flex-1 pt-0.5">
                  <h4 className="text-sm font-semibold leading-snug text-white md:text-base">{feature}</h4>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
