import { Newspaper, Search, Building2, Globe, GraduationCap } from "lucide-react";

const useCases = [
  {
    icon: Newspaper,
    title: "Journalists & Media",
    description: "Verify sources, detect manipulated content, and ensure accuracy before publication.",
  },
  {
    icon: Search,
    title: "Fact-Checkers",
    description: "Scale verification efforts with AI-powered analysis of viral claims and content.",
  },
  {
    icon: Building2,
    title: "Government & Policy",
    description: "Monitor information integrity and protect public discourse from coordinated campaigns.",
  },
  {
    icon: Globe,
    title: "Social Media Monitoring",
    description: "Track and analyze misinformation trends across platforms in real time.",
  },
  {
    icon: GraduationCap,
    title: "Education & Research",
    description: "Teach media literacy and conduct academic research on information ecosystems.",
  },
];

export default function SiteUseCases() {
  return (
    <section id="use-cases" className="border-b border-white/10 bg-tl-elevated py-24 md:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-mono text-[11px] font-medium tracking-[0.2em] text-violet-400/90 uppercase">
            Applications
          </h2>
          <h3 className="mt-4 text-3xl font-semibold tracking-[-0.03em] text-white md:text-4xl lg:text-5xl">
            Teams That Rely On TruthLens
          </h3>
          <p className="mt-4 text-base text-zinc-400 md:text-lg">
            Trusted by professionals who need reliable truth verification at scale.
          </p>
        </div>

        <div className="mx-auto mt-16 grid max-w-6xl gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {useCases.map((useCase) => (
            <div
              key={useCase.title}
              className="tl-surface tl-card-hover bg-black p-8 md:p-10"
            >
              <div className="mb-5 inline-flex rounded-sm border border-white/10 bg-tl-elevated p-2.5">
                <useCase.icon className="h-5 w-5 text-white" strokeWidth={1.25} aria-hidden />
              </div>
              <h4 className="text-base font-semibold text-white">{useCase.title}</h4>
              <p className="mt-3 text-sm leading-relaxed text-zinc-500">{useCase.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
