"use client";

import { motion } from "framer-motion";
import {
  FileSearch2,
  FileText,
  Image,
  ScanSearch,
  ShieldCheck,
  Video,
  UploadCloud,
  Scale,
  BadgeCheck,
} from "lucide-react";

const rowOne = [
  { icon: FileText, label: "Text" },
  { icon: Image, label: "Image" },
  { icon: Video, label: "Video" },
  { icon: UploadCloud, label: "Combined" },
  { icon: FileSearch2, label: "Claims" },
  { icon: ScanSearch, label: "Detection" },
  { icon: ShieldCheck, label: "Evidence" },
];

const rowTwo = [
  { icon: FileSearch2, label: "Cross-check" },
  { icon: Scale, label: "Confidence" },
  { icon: BadgeCheck, label: "Verdict" },
  { icon: ShieldCheck, label: "Sources" },
  { icon: ScanSearch, label: "Analyze" },
  { icon: FileText, label: "Report" },
  { icon: Image, label: "Media" },
];

const TILE_WIDTH = 96;
const TILE_GAP = 16;

function TechTile({ icon: Icon, label }: { icon: typeof FileText; label: string }) {
  return (
    <div className="group flex h-24 w-24 shrink-0 flex-col items-center justify-center rounded-sm border border-violet-300/15 bg-violet-700/80 transition-transform duration-200 hover:scale-[1.04]">
      <Icon className="h-7 w-7 text-white" strokeWidth={1.6} />
      <span className="mt-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-violet-100/90">{label}</span>
    </div>
  );
}

function MarqueeRow({
  items,
  duration,
  reverse = false,
}: {
  items: { icon: typeof FileText; label: string }[];
  duration: number;
  reverse?: boolean;
}) {
  const shift = (TILE_WIDTH + TILE_GAP) * items.length;
  const repeated = [...items, ...items];

  return (
    <div className="overflow-hidden">
      <motion.div
        className="flex w-max gap-4 will-change-transform"
        animate={reverse ? { x: [-shift, 0] } : { x: [0, -shift] }}
        transition={{ duration, repeat: Infinity, ease: "linear" }}
      >
        {repeated.map((item, idx) => (
          <TechTile key={`${item.label}-${idx}`} icon={item.icon} label={item.label} />
        ))}
      </motion.div>
    </div>
  );
}

export default function SiteStackGrid() {
  return (
    <section className="relative overflow-hidden bg-black py-24 md:py-28">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_85%_55%_at_72%_42%,rgba(109,40,217,0.22),transparent)]" />
      <div className="relative w-full px-0">
        <div className="overflow-hidden bg-gradient-to-r from-black via-violet-950/65 to-violet-900/85 lg:grid lg:grid-cols-12">
          <div className="border-b border-white/10 p-8 md:p-10 lg:col-span-4 lg:border-b-0 lg:border-r lg:p-12">
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-zinc-500">TruthLens Verification Engine</p>
            <h3 className="mt-4 text-4xl font-semibold leading-[1.08] tracking-[-0.035em] text-white md:text-5xl">
              Verify Text,
              <br />
              Images, and Video
            </h3>
          </div>

          <div className="lg:col-span-8 p-6 md:p-8 lg:p-10 xl:pr-2">
            <div className="mb-4">
              <MarqueeRow items={rowOne} duration={16} />
            </div>
            <MarqueeRow items={rowTwo} duration={18} reverse />
          </div>
        </div>
      </div>
    </section>
  );
}
