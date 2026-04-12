import { ChevronRight } from "lucide-react";

export default function SiteFinalCta() {
  return (
    <section className="relative border-b border-white/10 bg-black py-24 md:py-32">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 55% 55% at 50% 50%, rgba(124,58,237,0.2) 0%, rgba(124,58,237,0.04) 35%, rgba(0,0,0,0) 70%)",
        }}
      />
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="relative mx-auto max-w-2xl rounded-sm border border-white/10 bg-tl-elevated px-8 py-16 text-center md:px-12 md:py-20">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-zinc-500">Ready To Deploy Truth</p>
          <h2 className="text-3xl font-semibold tracking-[-0.03em] text-white md:text-4xl">
            Build Your Verification Workflow
          </h2>
          <p className="mx-auto mt-4 max-w-lg text-base leading-relaxed text-zinc-400 md:text-lg">
            Launch a modern trust layer for your newsroom, policy team, or platform moderation pipeline.
          </p>
          <a
            href="#verify"
            className="mt-10 inline-flex items-center justify-center gap-1 rounded-sm bg-white px-6 py-2.5 text-sm font-medium text-black transition-[filter,transform] duration-200 hover:brightness-95 active:scale-[0.98]"
          >
            Analyze Content
            <ChevronRight className="h-4 w-4" strokeWidth={2} aria-hidden />
          </a>
        </div>
      </div>
    </section>
  );
}
