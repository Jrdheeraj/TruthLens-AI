import { FileText, Image as ImageIcon, Video, UploadCloud, Upload, Scan } from "lucide-react";

const items = [
  { icon: FileText, label: "Text" },
  { icon: ImageIcon, label: "Image" },
  { icon: Video, label: "Video" },
  { icon: UploadCloud, label: "Combined" },
  { icon: Upload, label: "Ingest" },
  { icon: Scan, label: "Analyze" },
];

export default function SiteStackGrid() {
  return (
    <section className="relative overflow-hidden border-b border-white/10 bg-gradient-to-b from-violet-950/35 via-black to-black py-24 md:py-28">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_70%_20%,rgba(124,58,237,0.12),transparent)]" />
      <div className="relative mx-auto max-w-7xl px-6 lg:px-8">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {items.map((item) => (
            <div
              key={item.label}
              className="flex flex-col items-center rounded-sm border border-violet-500/20 bg-violet-950/30 px-3 py-8 text-center transition-[filter,transform] duration-200 hover:brightness-110"
            >
              <div className="flex h-11 w-11 items-center justify-center rounded-sm border border-white/10 bg-black/40">
                <item.icon className="h-5 w-5 text-white" strokeWidth={1.25} aria-hidden />
              </div>
              <span className="mt-3 text-xs font-medium text-zinc-300">{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
