"use client";

import { motion } from "framer-motion";

function MiniChart() {
  return (
    <svg viewBox="0 0 160 48" className="h-full w-full" fill="none" aria-hidden>
      <path
        d="M0 36 L24 28 L48 32 L72 12 L96 20 L120 8 L144 16 L160 10"
        stroke="#a78bfa"
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M0 40 L32 34 L56 38 L80 24 L104 30 L128 22 L160 18"
        stroke="#34d399"
        strokeWidth="1"
        strokeLinecap="round"
        opacity="0.7"
      />
    </svg>
  );
}

const queueRows = [
  { source: "Breaking headline", signal: "Cross-source validation", status: "Queued" },
  { source: "Image attachment", signal: "Reverse image trace", status: "Running" },
  { source: "Claim paragraph", signal: "Entity confidence", status: "Complete" },
  { source: "Video snippet", signal: "Frame integrity scan", status: "Running" },
  { source: "Social post", signal: "Narrative drift", status: "Queued" },
  { source: "External citation", signal: "Source trust score", status: "Complete" },
];

export default function SiteDashboardMocks() {
  return (
    <section className="relative border-b border-white/10 bg-black py-24 md:py-32">
      <div className="pointer-events-none absolute inset-0 tl-grid-section opacity-30" aria-hidden />
      <div className="relative mx-auto max-w-[1500px] px-6 lg:px-10">
        <div className="relative grid gap-10 lg:grid-cols-12 lg:items-start lg:gap-14">
          <motion.div
            className="rounded-sm border border-white/10 bg-tl-elevated lg:col-span-7"
            initial={{ opacity: 0, x: -24 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.35 }}
            transition={{ duration: 0.45, ease: "easeOut" }}
            whileHover={{ y: -2 }}
          >
            <div className="flex items-center gap-2 border-b border-white/10 px-6 py-4.5">
              <span className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
              <span className="h-2.5 w-2.5 rounded-full bg-amber-400/80" />
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500/70" />
              <div className="ml-3 flex h-10 flex-1 items-center rounded-sm border border-white/5 bg-black/50 px-4">
                <span className="text-[14px] text-zinc-500">truthlens://verification/queue/live</span>
              </div>
            </div>
            <div className="space-y-0 divide-y divide-white/5 p-6">
              {queueRows.map((row, i) => (
                <motion.div
                  key={row.source}
                  className="group flex items-center gap-4 py-3.5 first:pt-0 last:pb-0"
                  initial={{ opacity: 0, y: 8 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.2 }}
                  transition={{ duration: 0.25, delay: i * 0.05 }}
                  whileHover={{ x: 4 }}
                >
                  <span className="w-[140px] shrink-0 text-[14px] text-zinc-500">{row.source}</span>
                  <span className="flex-1 text-[14px] text-zinc-400 transition-colors duration-200 group-hover:text-zinc-200">
                    {row.signal}
                  </span>
                  <span className="inline-flex h-8 w-[94px] shrink-0 items-center justify-center rounded-sm border border-white/10 bg-white/5 text-[12px] uppercase tracking-wide text-zinc-500">
                    {row.status}
                  </span>
                </motion.div>
              ))}
            </div>
          </motion.div>

          <div className="relative lg:col-span-5 lg:pl-4">
            <motion.div
              className="rounded-sm border border-white/10 bg-black p-6 shadow-[0_0_0_1px_rgba(255,255,255,0.04)]"
              initial={{ opacity: 0, x: 24 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, amount: 0.35 }}
              transition={{ duration: 0.45, ease: "easeOut", delay: 0.08 }}
              whileHover={{ y: -2 }}
            >
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="text-[18px] font-medium text-zinc-200">Live Confidence Graph</p>
                  <p className="text-[14px] text-zinc-500">Model agreement and source reliability</p>
                </div>
                <span className="inline-flex h-8 w-14 items-center justify-center rounded-sm border border-white/10 bg-tl-panel text-[12px] text-zinc-500">
                  LIVE
                </span>
              </div>
              <div className="h-40 rounded-sm border border-white/5 bg-black/60 px-3 py-3">
                <MiniChart />
              </div>
              <div className="mt-4 grid grid-cols-2 gap-4">
                <motion.div
                  className="h-24 rounded-sm border border-white/10 bg-tl-elevated p-4"
                  whileHover={{ scale: 1.02 }}
                  transition={{ duration: 0.2 }}
                >
                  <p className="text-[14px] text-zinc-500">Model Drift</p>
                  <p className="mt-2 text-3xl font-medium text-zinc-200">Low</p>
                </motion.div>
                <motion.div
                  className="h-24 rounded-sm border border-white/10 bg-tl-elevated p-4"
                  whileHover={{ scale: 1.02 }}
                  transition={{ duration: 0.2 }}
                >
                  <p className="text-[14px] text-zinc-500">Source Health</p>
                  <p className="mt-2 text-3xl font-medium text-zinc-200">Stable</p>
                </motion.div>
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
}
