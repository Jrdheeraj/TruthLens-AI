import { Check, Upload, Scan, ShieldCheck, FileCheck } from "lucide-react";

const steps = [
  {
    icon: Upload,
    title: "Ingest",
    subtitle: "Upload Text, Image, or Video",
    description:
      "Drag & drop interface supporting social media posts, screenshots, headlines, and multimedia content.",
    preview: "ingest" as const,
  },
  {
    icon: Scan,
    title: "Analyze",
    subtitle: "AI Extracts & Examines",
    description:
      "Advanced AI extracts claims, detects manipulation patterns, and performs cross-modal reasoning on text and visuals.",
    preview: "analyze" as const,
  },
  {
    icon: ShieldCheck,
    title: "Verify",
    subtitle: "Cross-Reference Evidence",
    description: "Checks against real-world evidence, trusted sources, and known hoax pattern databases.",
    preview: "verify" as const,
  },
  {
    icon: FileCheck,
    title: "Verdict",
    subtitle: "Clear Authenticity Report",
    description: "Delivers a clear verdict with confidence score and transparent reasoning for full accountability.",
    preview: "verdict" as const,
  },
];

function StepPreview({ type }: { type: (typeof steps)[number]["preview"] }) {
  if (type === "ingest") {
    return (
      <div className="mt-4 rounded-sm border border-white/10 bg-black/50 p-3 flex flex-col">
        <div className="space-y-2">
          <div className="text-xs font-medium text-zinc-400">Social Media Posts</div>
          <div className="space-y-1">
            {[1, 2, 3].map((n) => (
              <div
                key={n}
                className={`flex items-center justify-between gap-2 rounded-sm px-2 py-2 ${
                  n === 2 ? "border border-emerald-500/25 bg-emerald-500/10" : "border border-transparent"
                }`}
              >
                <span className="h-2 flex-1 rounded-full bg-white/10" />
                {n === 2 ? (
                  <Check className="h-3.5 w-3.5 shrink-0 text-emerald-400" strokeWidth={2} />
                ) : (
                  <Check className="h-3.5 w-3.5 shrink-0 text-emerald-400/50" strokeWidth={2} />
                )}
              </div>
            ))}
          </div>
          <div className="text-xs text-zinc-600">Screenshots, Videos, Headlines</div>
        </div>
      </div>
    );
  }
  if (type === "analyze") {
    return (
      <div className="mt-4 h-40 rounded-sm border border-white/10 bg-black/50 p-3 font-mono flex flex-col overflow-hidden">
        <div className="space-y-1 flex-1 text-xs">
          <div className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Processing</div>
          <div className="h-1.5 w-20 rounded-sm bg-white/15" />
          <div className="h-6 rounded-sm border border-white/10 bg-black/60 flex items-center px-1.5">
            <span className="text-xs text-zinc-600">Claims Extracted</span>
          </div>
          <div className="h-6 rounded-sm border border-white/10 bg-black/60 flex items-center px-1.5">
            <span className="text-xs text-zinc-600">Pattern Detection</span>
          </div>
          <div className="h-1.5 w-32 rounded-sm bg-emerald-500/30" />
          <div className="text-xs text-zinc-600">Cross-modal Reasoning</div>
        </div>
      </div>
    );
  }
  if (type === "verify") {
    return (
      <div className="mt-4 h-40 rounded-sm border border-white/10 bg-black/50 p-3 flex flex-col overflow-hidden">
        <div className="flex-1 text-xs">
          <div className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2">Evidence Checks</div>
          <div className="mb-1 h-1.5 w-24 rounded-full bg-fuchsia-400/30" />
          <div className="space-y-1">
            {[
              "Real-world Sources",
              "Known Hoax Database",
              "Pattern Matching"
            ].map((label, n) => (
              <div key={n} className="flex items-center gap-2 border-b border-white/5 py-1 last:border-0">
                <Check className="h-3 w-3 shrink-0 text-emerald-400" strokeWidth={2} />
                <span className="text-xs text-zinc-500">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="mt-4 h-40 rounded-sm border border-white/10 bg-black/50 p-3 flex flex-col overflow-hidden">
      <div className="flex-1 flex flex-col justify-between text-xs">
        <div>
          <div className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-2">Confidence Score</div>
          <div className="mb-1 flex items-center justify-between">
            <span className="h-1.5 w-12 rounded-full bg-white/10" />
            <span className="text-xs font-semibold text-violet-400">82%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/5">
            <div className="h-full w-[82%] rounded-full bg-gradient-to-r from-violet-500 to-emerald-400" />
          </div>
        </div>
        <div className="mt-2 grid grid-cols-2 gap-1">
          <div className="h-6 rounded-sm border border-white/10 bg-tl-panel flex items-center justify-center px-1">
            <span className="text-xs text-zinc-600 text-center">Full Report</span>
          </div>
          <div className="h-6 rounded-sm border border-white/10 bg-tl-panel flex items-center justify-center px-1">
            <span className="text-xs text-zinc-600 text-center">Reasoning</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function SiteSteps() {
  return (
    <section id="how-it-works" className="relative border-b border-white/10 bg-black py-24 md:py-32">
      <div className="pointer-events-none absolute inset-0 tl-grid-section opacity-40" aria-hidden />
      <div className="relative mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-mono text-[12px] font-medium tracking-[0.2em] text-violet-400/90 uppercase">
            The Process
          </h2>
          <h3 className="mt-4 text-4xl font-semibold tracking-[-0.03em] text-white md:text-5xl lg:text-6xl">
            Upload, Verify, Decide.
          </h3>
          <p className="mt-4 text-lg text-zinc-400 md:text-xl">
            TruthLens compresses noisy media into clear, evidence-backed outcomes in four production-ready steps.
          </p>
        </div>

        <div className="mt-20 grid gap-4 md:grid-cols-2 lg:grid-cols-4 auto-rows-max">
          {steps.map((step, index) => (
            <div key={step.title} className="tl-surface tl-card-hover px-5 py-8 md:px-6 flex flex-col h-full">
              <div className="flex items-start gap-4 flex-1">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-sm bg-violet-600 text-sm font-semibold text-white">
                  {index + 1}
                </span>
                <div className="min-w-0 pt-0.5">
                  <step.icon className="mb-3 h-5 w-5 text-zinc-500" strokeWidth={1.5} aria-hidden />
                  <h4 className="text-xl font-semibold tracking-tight text-white">{step.title}</h4>
                  <p className="mt-1 text-base font-medium text-zinc-400">{step.subtitle}</p>
                  <p className="mt-3 text-base leading-relaxed text-zinc-500">{step.description}</p>
                </div>
              </div>
              <StepPreview type={step.preview} />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
