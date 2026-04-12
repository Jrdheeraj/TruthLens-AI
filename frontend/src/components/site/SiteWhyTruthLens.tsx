"use client";

import { motion } from "framer-motion";
import { Check, X } from "lucide-react";

const truthLensFeatures = [
  {
    title: "Evidence-based verification",
    detail: "Every verdict is grounded in traceable sources, not hidden model guesses.",
  },
  {
    title: "Multi-modal analysis (text, image, video)",
    detail: "Cross-checks claims across formats to detect context shifts and manipulations.",
  },
  {
    title: "Transparent reasoning with sources",
    detail: "Shows why a claim is flagged, what evidence was used, and confidence levels.",
  },
  {
    title: "Built for real-world misinformation",
    detail: "Designed for noisy feeds, viral posts, and fast-moving narratives.",
  },
  {
    title: "Cross-modal consistency checks",
    detail: "Finds mismatches between text, visuals, and metadata signals.",
  },
  {
    title: "Confidence scoring system",
    detail: "Produces nuanced confidence scores instead of binary yes/no outputs.",
  },
];

const typicalToolsFlaws = [
  {
    title: "Black-box answers with no explanation",
    detail: "You get a result, but not the path used to reach it.",
  },
  {
    title: "Text-only checks, missing visual context",
    detail: "Important image and video cues are ignored.",
  },
  {
    title: "No source clarity or attribution",
    detail: "Claims are scored without transparent supporting evidence.",
  },
  {
    title: "High uncertainty in results",
    detail: "Outputs feel unstable when content quality drops.",
  },
  {
    title: "Single-modal analysis only",
    detail: "Cannot validate consistency across multiple content types.",
  },
  {
    title: "Binary yes/no without nuance",
    detail: "Lacks confidence gradients needed for real decision making.",
  },
];

export default function SiteWhyTruthLens() {
  return (
    <section id="why-truthlens" className="relative border-b border-white/10 bg-black py-20 md:py-24 overflow-hidden">
      {/* Grid Background */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage: `
            linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px),
            linear-gradient(0deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px)
          `,
          backgroundSize: "80px 80px",
          backgroundPosition: "0 0",
        }}
      />
      <div className="mx-auto max-w-7xl px-6 lg:px-8 relative z-10">
        <div className="mx-auto max-w-2xl text-center">
          <h3 className="mt-4 text-3xl font-semibold tracking-[-0.03em] text-white md:text-4xl lg:text-5xl">
            Why TruthLens AI
          </h3>
          <p className="mt-4 text-base text-zinc-300 md:text-lg">
            Purpose-built for the misinformation age, not retrofitted from generic AI.
          </p>
        </div>

        <div className="mx-auto mt-14 grid max-w-6xl items-stretch gap-5 md:grid-cols-2">
          <div className="flex h-full flex-col rounded-sm border border-white/10 bg-tl-elevated p-6 md:p-8">
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-sm border border-white/10 bg-black/50">
                <Check className="h-4 w-4 text-violet-400" strokeWidth={2} aria-hidden />
              </div>
              <h4 className="text-lg font-semibold text-white">TruthLens AI</h4>
            </div>

            <div className="flex-1 space-y-2">
              {truthLensFeatures.map((feature, index) => (
                <motion.div
                  key={feature.title}
                  initial={{ opacity: 0, y: 14 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.3 }}
                  transition={{ duration: 0.35, delay: index * 0.05 }}
                  whileHover={{ y: -3, scale: 1.01 }}
                  className="group min-h-[112px] cursor-default rounded-sm border border-white/5 bg-black/40 px-3 py-2.5 transition-colors duration-200 hover:border-violet-400/40 hover:bg-violet-500/[0.06]"
                >
                  <div className="flex items-start gap-3">
                  <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-sm border border-violet-500/30 bg-violet-500/10">
                    <Check className="h-3 w-3 text-violet-300" strokeWidth={2} aria-hidden />
                  </div>
                  <div>
                    <p className="text-[15px] font-medium leading-relaxed text-zinc-100 transition-colors duration-200 group-hover:text-white">
                      {feature.title}
                    </p>
                    <p className="mt-1 text-sm leading-relaxed text-zinc-400 transition-colors duration-200 group-hover:text-zinc-300">
                      {feature.detail}
                    </p>
                  </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>

          <div className="flex h-full flex-col rounded-sm border border-white/10 bg-black/40 p-6 opacity-95 md:p-8">
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-sm border border-white/10 bg-tl-panel">
                <X className="h-4 w-4 text-zinc-500" strokeWidth={2} aria-hidden />
              </div>
              <h4 className="text-lg font-semibold text-zinc-300">Typical Tools</h4>
            </div>

            <div className="flex-1 space-y-2">
              {typicalToolsFlaws.map((flaw, index) => (
                <motion.div
                  key={flaw.title}
                  initial={{ opacity: 0, y: 14 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.3 }}
                  transition={{ duration: 0.35, delay: index * 0.05 }}
                  whileHover={{ y: -3, scale: 1.01 }}
                  className="group min-h-[112px] cursor-default rounded-sm border border-white/5 bg-black/20 px-3 py-2.5 transition-colors duration-200 hover:border-red-400/30 hover:bg-red-500/[0.05]"
                >
                  <div className="flex items-start gap-3">
                  <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-sm bg-red-500/10">
                    <X className="h-3 w-3 text-red-400/90" strokeWidth={2} aria-hidden />
                  </div>
                  <div>
                    <p className="text-[15px] font-medium leading-relaxed text-zinc-300 transition-colors duration-200 group-hover:text-zinc-200">
                      {flaw.title}
                    </p>
                    <p className="mt-1 text-sm leading-relaxed text-zinc-400 transition-colors duration-200 group-hover:text-zinc-300">
                      {flaw.detail}
                    </p>
                  </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
