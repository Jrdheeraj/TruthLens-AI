"use client";

import { motion } from "framer-motion";
import { ChevronRight, Play } from "lucide-react";

import SiteHeroVisual from "@/components/site/SiteHeroVisual";

export default function SiteHero() {
  return (
    <section className="relative overflow-hidden border-b border-white/10 bg-[#0A0A0A] pt-32 pb-40 md:pb-48">
      {/* Top-left lighting effect */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 -left-40 h-96 w-96 opacity-50"
        style={{
          background: "radial-gradient(circle, rgba(168, 85, 247, 0.4) 0%, rgba(168, 85, 247, 0.2) 40%, rgba(0, 0, 0, 0) 70%)",
          filter: "blur(60px)",
        }}
      />

      <div className="relative mx-auto max-w-7xl px-6 lg:px-8">
        <div className="grid items-center gap-24 lg:grid-cols-2 lg:gap-16 lg:gap-x-20">
          <div className="relative z-40">
            <motion.div
              className="mb-8 flex items-center gap-3 border-l-2 border-violet-500 pl-4"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, ease: "easeOut" }}
            >
              <span className="font-mono text-[12px] leading-snug tracking-wide text-zinc-500">
                AI-Powered Verification Platform
              </span>
            </motion.div>

            <h1 className="text-[3rem] font-semibold leading-[1.05] tracking-[-0.035em] text-white sm:text-5xl lg:text-[3.5rem] xl:text-[4rem]">
              <motion.span
                className="inline-block"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.72, delay: 0.1, ease: "easeOut" }}
              >
                Absolute Truth in a
              </motion.span>
              <motion.span
                className="block bg-[linear-gradient(90deg,#8B5CF6_0%,#3B82F6_52%,#22D3EE_100%)] bg-clip-text text-transparent"
                style={{ backgroundSize: "200% 200%", willChange: "background-position" }}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0, backgroundPosition: ["0% 50%", "100% 50%", "0% 50%"] }}
                transition={{
                  opacity: { duration: 0.72, delay: 0.5, ease: "easeOut" },
                  y: { duration: 0.72, delay: 0.5, ease: "easeOut" },
                  backgroundPosition: { duration: 8, repeat: Infinity, ease: "linear" },
                }}
              >
              Synthetic World
              </motion.span>
            </h1>

            <motion.p
              className="mt-6 max-w-lg text-base leading-relaxed text-zinc-400 md:text-lg"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.58, ease: "easeOut" }}
            >
              Advanced AI-driven verification for text, images, and deepfake videos separating facts from fiction in
              real time.
            </motion.p>

            <motion.div
              className="mt-10 flex flex-col gap-3 sm:flex-row sm:items-center"
              initial={{ opacity: 0, y: 16, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.6, delay: 0.7, ease: "easeOut" }}
            >
              <a
                href="#verify"
                className="inline-flex items-center justify-center gap-1 rounded-sm bg-white px-5 py-2.5 text-sm font-medium text-black transition-[filter,transform] duration-200 hover:brightness-95 active:scale-[0.98]"
              >
                Analyze Content
                <ChevronRight className="h-4 w-4" strokeWidth={2} aria-hidden />
              </a>
              <a
                href="#how-it-works"
                className="inline-flex items-center justify-center gap-2 rounded-sm border border-white/15 bg-transparent px-5 py-2.5 text-sm font-medium text-white transition-[filter,transform] duration-200 hover:border-white/25 hover:bg-white/[0.03] active:scale-[0.98]"
              >
                <Play className="h-4 w-4" strokeWidth={1.5} aria-hidden />
                How TruthLens Works
              </a>
            </motion.div>
          </div>

          <div className="relative z-30">
            <SiteHeroVisual />
          </div>
        </div>
      </div>
    </section>
  );
}
