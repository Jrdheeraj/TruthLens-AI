import { ChevronRight } from "lucide-react";

export default function SiteFinalCta() {
  return (
    <section className="border-b border-white/10 bg-black py-24 md:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl rounded-sm border border-white/10 bg-tl-elevated px-8 py-16 text-center md:px-12 md:py-20">
          <h2 className="text-3xl font-semibold tracking-[-0.03em] text-white md:text-4xl">
            Verify Content With Clarity
          </h2>
          <p className="mx-auto mt-4 max-w-lg text-base leading-relaxed text-zinc-400 md:text-lg">
            Upload or paste content to verify, then review a concise result with confidence and an easy-to-read
            explanation.
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
