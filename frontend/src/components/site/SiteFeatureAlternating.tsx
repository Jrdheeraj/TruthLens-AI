import { ChevronRight } from "lucide-react";

import SiteHeroVisual from "@/components/site/SiteHeroVisual";

function PurpleLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      className="mt-6 inline-flex items-center gap-1 text-sm font-medium text-violet-400 transition-colors duration-200 hover:text-violet-300"
    >
      {children}
      <ChevronRight className="h-4 w-4" strokeWidth={2} aria-hidden />
    </a>
  );
}

export default function SiteFeatureAlternating() {
  return (
    <section className="border-b border-white/10 bg-black py-24 md:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="overflow-hidden rounded-sm border border-white/10 lg:grid lg:grid-cols-2">
          <div className="border-b border-white/10 p-10 lg:border-b-0 lg:border-r lg:p-14">
            <h2 className="font-mono text-[11px] font-medium tracking-[0.2em] text-violet-400/90 uppercase">
              The Difference
            </h2>
            <h3 className="mt-4 text-2xl font-semibold tracking-[-0.03em] text-white md:text-3xl lg:text-4xl">
              Why TruthLens AI
            </h3>
            <p className="mt-4 max-w-md text-base leading-relaxed text-zinc-400 md:text-lg">
              Purpose-built for the misinformation age, not retrofitted from generic AI.
            </p>
            <PurpleLink href="#verify">Verify Content</PurpleLink>
          </div>
          <div className="flex items-center justify-center bg-tl-elevated p-8 lg:p-10">
            <div className="w-full max-w-[420px] scale-[0.92]">
              <SiteHeroVisual />
            </div>
          </div>
        </div>

        <div className="mt-10 overflow-hidden rounded-sm border border-white/10 lg:mt-12 lg:grid lg:grid-cols-2">
          <div className="order-2 flex items-center justify-center border-t border-white/10 bg-tl-elevated p-8 lg:order-1 lg:border-r lg:border-t-0 lg:p-10">
            <div className="w-full max-w-[420px] scale-[0.92]">
              <SiteHeroVisual />
            </div>
          </div>
          <div className="order-1 p-10 lg:order-2 lg:p-14">
            <h2 className="font-mono text-[11px] font-medium tracking-[0.2em] text-violet-400/90 uppercase">
              Verification
            </h2>
            <h3 className="mt-4 text-2xl font-semibold tracking-[-0.03em] text-white md:text-3xl lg:text-4xl">
              Verify Content With Clarity
            </h3>
            <p className="mt-4 max-w-md text-base leading-relaxed text-zinc-400 md:text-lg">
              Upload or paste content to verify, then review a concise result with confidence and an easy-to-read
              explanation.
            </p>
            <PurpleLink href="#verify">Analyze Content</PurpleLink>
          </div>
        </div>
      </div>
    </section>
  );
}
