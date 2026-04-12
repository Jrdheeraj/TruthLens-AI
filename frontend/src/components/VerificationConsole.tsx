"use client";

import { useRef, useState } from "react";
import {
  FileText,
  Image as ImageIcon,
  Link2,
  Loader2,
  UploadCloud,
  Video,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { verifyImage, verifyMultimodal, verifyText, verifyVideo } from "@/services/verifyApi";
import { VerificationResponse, VerificationStatus } from "@/types/api";

type TabType = "text" | "image" | "video" | "combined";

const tabs: { id: TabType; label: string; icon: typeof FileText }[] = [
  { id: "text", label: "Text", icon: FileText },
  { id: "image", label: "Image", icon: ImageIcon },
  { id: "video", label: "Video", icon: Video },
  { id: "combined", label: "Combined", icon: UploadCloud },
];

const VerificationConsole = () => {
  const [activeTab, setActiveTab] = useState<TabType>("text");
  const [inputContent, setInputContent] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<VerificationResponse | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  const handleTabChange = (tab: TabType) => {
    setActiveTab(tab);
    setSelectedFile(null);
    setInputContent("");
    setResult(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if ((activeTab === "image" || activeTab === "combined") && !file.type.startsWith("image/")) {
      toast.error("Please upload an image file.");
      return;
    }

    if (activeTab === "video" && !file.type.startsWith("video/")) {
      toast.error("Please upload a video file.");
      return;
    }

    setSelectedFile(file);
  };

  const handleAnalyze = async () => {
    if (activeTab === "text" && !inputContent.trim()) {
      toast.error("Enter some text first.");
      return;
    }

    if (activeTab === "image" && !selectedFile) {
      toast.error("Upload an image first.");
      return;
    }

    if (activeTab === "video" && !selectedFile) {
      toast.error("Upload a video first.");
      return;
    }

    if (activeTab === "combined" && !inputContent.trim() && !selectedFile) {
      toast.error("Add text or an image first.");
      return;
    }

    setIsAnalyzing(true);
    setResult(null);

    try {
      let response: VerificationResponse;

      if (activeTab === "text") {
        response = await verifyText(inputContent);
      } else if (activeTab === "image") {
        response = await verifyImage(selectedFile!);
      } else if (activeTab === "video") {
        response = await verifyVideo(selectedFile!);
      } else {
        response = await verifyMultimodal(inputContent, selectedFile || undefined);
      }

      setResult(response);

      setTimeout(() => {
        resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 300);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Something went wrong while analyzing.";
      toast.error(message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const actualInfo =
    result?.actual_information ||
    (result?.corrected_facts && result.corrected_facts.length > 0
      ? result.corrected_facts[0].correction
      : null);

  const confidence = result ? Math.min(100, Math.max(0, Math.round(result.confidence))) : 0;

  const resolvedStatus: VerificationStatus | undefined = result
    ? result.status || result.verdict
    : undefined;

  const statusMeta: Record<VerificationStatus, { label: string; chipClass: string; subtitle: string }> = {
    TRUE: {
      label: "TRUE",
      chipClass: "bg-[#E9F8EF] text-[#1E824C] border-[#CDEFD9]",
      subtitle: "The content aligns with available evidence.",
    },
    FALSE: {
      label: "FALSE",
      chipClass: "bg-[#FDEEEE] text-[#B23A3A] border-[#F7D5D5]",
      subtitle: "The content is contradicted by evidence or lacks credible support.",
    },
  };

  const currentMeta = resolvedStatus ? statusMeta[resolvedStatus] : statusMeta.FALSE;
  const isReal = resolvedStatus === "TRUE";
  const isFalseLike = resolvedStatus === "FALSE";

  const explanationText = result
    ? result.explanation?.trim() ||
      (isReal
        ? "This content appears to be authentic based on the available evidence. The structure, wording, and contextual signals are consistent with known reliable patterns, and no major anomalies were detected during the verification pass."
        : "This content appears to be AI-generated or misleading because several structural and contextual patterns do not align with trusted evidence. Signals such as inconsistent phrasing, atypical media characteristics, or unsupported claims are commonly associated with synthetic or manipulated content.")
    : "Run verification to see a clear status, confidence score, and a plain-language explanation of the findings.";

  return (
    <section id="verify" className="border-t border-white/10 bg-black py-24 text-white md:py-28">
      <div className="mx-auto max-w-5xl px-4 sm:px-6">
        <div className="mb-12 text-center md:mb-14">
          <p className="mb-3 font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-violet-400/90">
            Verification
          </p>
          <h2 className="mb-3 text-3xl font-semibold tracking-[-0.03em] text-white md:text-4xl">
            Verify Content With Clarity
          </h2>
          <p className="mx-auto max-w-2xl text-base leading-relaxed text-zinc-400 md:text-lg">
            Upload or paste content to verify, then review a concise result with confidence and an easy-to-read
            explanation.
          </p>
        </div>

        <div className="mx-auto max-w-3xl rounded-sm border border-white/10 bg-tl-elevated p-7 transition-all duration-200 ease-in-out md:p-9">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-sm border border-white/10 bg-black">
            <UploadCloud className="h-5 w-5 text-zinc-500" strokeWidth={1.5} />
          </div>
          <h3 className="mb-7 text-center text-xl font-semibold text-white md:text-2xl">
            Upload or Paste Content to Verify
          </h3>

          <div className="mb-6 flex items-center justify-center">
            <div className="inline-flex flex-wrap items-center justify-center gap-0.5 rounded-sm border border-white/10 bg-black p-1">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => handleTabChange(tab.id)}
                    className={`flex items-center gap-2 rounded-sm border px-3 py-2 text-sm font-medium transition-colors duration-200 ${
                      isActive
                        ? "border-white/10 bg-tl-elevated text-white"
                        : "border-transparent text-zinc-500 hover:bg-white/[0.04]"
                    }`}
                  >
                    <Icon
                      className={`h-4 w-4 shrink-0 ${isActive ? "text-violet-400" : "text-zinc-500"}`}
                      strokeWidth={1.5}
                    />
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-5">
            {(activeTab === "text" || activeTab === "combined") && (
              <div className="flex flex-col">
                <label htmlFor="verify-text" className="mb-2 text-sm font-medium text-white">
                  Text to verify
                </label>
                <textarea
                  id="verify-text"
                  value={inputContent}
                  onChange={(e) => setInputContent(e.target.value)}
                  placeholder="Paste the claim, headline, or paragraph here..."
                  className="min-h-[168px] w-full resize-none rounded-sm border border-white/10 bg-black p-4 font-mono text-[15px] text-zinc-200 placeholder:text-zinc-600 transition-colors duration-200 ease-in-out focus:border-violet-500/50 focus:outline-none"
                />
              </div>
            )}

            {(activeTab === "image" || activeTab === "video" || activeTab === "combined") && (
              <div className="flex flex-col">
                <span className="mb-2 text-sm font-medium text-white">Media file</span>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex min-h-[170px] w-full cursor-pointer flex-col items-center justify-center gap-2.5 rounded-sm border border-dashed border-white/15 bg-black text-left transition-colors duration-200 ease-in-out hover:border-violet-500/40 hover:brightness-110"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-sm border border-white/10 bg-tl-elevated">
                    <UploadCloud className="h-5 w-5 text-zinc-500" strokeWidth={1.5} />
                  </div>
                  <p className="px-4 text-center text-sm font-medium text-white">
                    {selectedFile ? selectedFile.name : `Upload ${activeTab} file`}
                  </p>
                  <p className="px-8 text-center text-xs text-zinc-500">Click to browse files from your device</p>
                  <input
                    ref={fileInputRef}
                    type="file"
                    className="hidden"
                    accept={activeTab === "video" ? "video/*" : "image/*"}
                    onChange={handleFileSelect}
                  />
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="mb-12 mt-6 flex justify-center">
          <button
            type="button"
            onClick={handleAnalyze}
            disabled={isAnalyzing}
            className="flex min-w-[220px] w-full items-center justify-center gap-2 rounded-sm bg-white px-8 py-3 font-medium text-black transition-[filter,transform] duration-200 ease-in-out hover:brightness-95 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
          >
            {isAnalyzing ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin text-black" strokeWidth={2} />
                Running verification...
              </>
            ) : (
              "Run Verification"
            )}
          </button>
        </div>

        <div
          ref={resultRef}
          className="mx-auto max-w-3xl rounded-sm border border-white/10 bg-tl-elevated p-7 transition-all duration-200 ease-in-out md:p-9"
        >
          <h3 className="mb-6 text-lg font-semibold text-white md:text-xl">Verification Results</h3>

          {isAnalyzing && (
            <div className="flex flex-col items-center justify-center py-10 animate-in fade-in duration-200">
              <Loader2 className="mb-3 h-8 w-8 animate-spin text-violet-400" strokeWidth={1.5} />
              <p className="text-sm text-zinc-500">Analyzing your content. This usually takes a few seconds.</p>
            </div>
          )}

          {!isAnalyzing && result && (
            <div className="space-y-7 animate-in fade-in slide-in-from-bottom-2 duration-200">
              <div className="border-b border-white/10 pb-6">
                <p className="mb-2 text-sm font-medium text-zinc-500">Status</p>
                <div className="flex items-center gap-3">
                  <span
                    className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium ${currentMeta.chipClass}`}
                  >
                    {isReal ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
                    {currentMeta.label}
                  </span>
                  <span className="text-sm text-zinc-400">{currentMeta.subtitle}</span>
                </div>
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-sm font-medium text-zinc-500">Confidence Score</p>
                  <p className="text-sm font-semibold text-white">{confidence}%</p>
                </div>
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-white/10">
                  <div
                    className={`h-full rounded-full transition-all duration-200 ${
                      resolvedStatus === "TRUE" ? "bg-[#34C759]" : "bg-[#E35D5B]"
                    }`}
                    style={{ width: `${confidence}%` }}
                  />
                </div>
                {result.confidence_justification && (
                  <p className="mt-2 text-xs text-zinc-500">{result.confidence_justification}</p>
                )}
              </div>

              <div>
                <h4 className="mb-2 text-sm font-medium text-zinc-500">Explanation</h4>
                <p className="whitespace-pre-wrap text-[15px] leading-7 text-zinc-400 md:text-base">{explanationText}</p>
              </div>

              {(result.what_matches_evidence_better || actualInfo) && isFalseLike && (
                <div className="rounded-sm border border-white/10 bg-black p-4">
                  <h4 className="mb-2 text-sm font-medium text-zinc-500">What matches evidence better</h4>
                  <p className="whitespace-pre-wrap text-[15px] leading-7 text-zinc-400">
                    {result.what_matches_evidence_better || actualInfo}
                  </p>
                </div>
              )}

              {result.sources && result.sources.length > 0 && (
                <div>
                  <div className="mb-3 flex items-center gap-2">
                    <Link2 className="h-4 w-4 shrink-0 text-zinc-500" strokeWidth={1.5} />
                    <h4 className="text-sm font-medium text-zinc-500">Sources</h4>
                  </div>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    {result.sources.map((source, idx) => (
                      <div
                        key={idx}
                        className="group block rounded-sm border border-white/10 bg-black p-4 transition-colors duration-200 ease-in-out hover:border-violet-500/40"
                      >
                        <div className="mb-2 flex items-start justify-between gap-3">
                          <span className="line-clamp-2 text-[15px] font-semibold text-white">
                            {source.title || source.name || "Source"}
                          </span>
                          <span className="shrink-0 rounded-sm border border-white/10 bg-tl-elevated px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-500">
                            {source.type || source.source || "Web"}
                          </span>
                        </div>
                        <p className="line-clamp-3 text-sm leading-relaxed text-zinc-400">
                          {source.snippet || source.description || source.text || "No summary available."}
                        </p>
                        {(source.url || source.link) && (
                          <a
                            href={source.url || source.link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-2 inline-block break-all text-sm text-violet-400 underline underline-offset-2 transition-colors duration-200 ease-in-out hover:text-violet-300"
                          >
                            {source.url || source.link}
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {(!result.sources || result.sources.length === 0) && result.sources_note && (
                <p className="text-sm text-zinc-500">{result.sources_note}</p>
              )}
            </div>
          )}

          {!isAnalyzing && !result && (
            <p className="text-sm text-zinc-500">Results will appear here after you run verification.</p>
          )}
        </div>
      </div>
    </section>
  );
};

export default VerificationConsole;
