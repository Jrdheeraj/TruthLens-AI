import { useState, useRef } from "react";
import { Upload, FileText, Image, Video, Loader2, CheckCircle2, XCircle, AlertCircle, ChevronDown, ChevronUp, Layers, Search, Globe, ExternalLink } from "lucide-react";
import { VerificationResponse, Verdict } from "../types/api";
import { verifyText, verifyImage, verifyVideo } from "../services/verifyApi";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";

type TabType = "text" | "image" | "video" | "combined";

const VerificationConsole = () => {
  const [activeTab, setActiveTab] = useState<TabType>("text");
  const [inputContent, setInputContent] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<VerificationResponse | null>(null);
  const [expandedSections, setExpandedSections] = useState<Record<number, boolean>>({});

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (activeTab === "image" && !file.type.startsWith("image/")) {
        toast.error("Please upload an image file");
        return;
      }
      if (activeTab === "video" && !file.type.startsWith("video/")) {
        toast.error("Please upload a video file");
        return;
      }
      setSelectedFile(file);
    }
  };

  const handleAnalyze = async () => {
    if (activeTab === "text" && !inputContent.trim()) return;
    if (activeTab !== "text" && !selectedFile) {
      toast.error(`Please upload ${activeTab === "image" ? "an image" : "a video"} first`);
      return;
    }

    setIsAnalyzing(true);
    setResult(null);
    setExpandedSections({});

    try {
      let response: VerificationResponse;
      if (activeTab === "text") {
        response = await verifyText(inputContent);
      } else if (activeTab === "image") {
        response = await verifyImage(selectedFile!);
      } else if (activeTab === "combined") {
        const { verifyMultimodal } = await import("../services/verifyApi");
        response = await verifyMultimodal(inputContent, selectedFile || undefined);
      } else {
        response = await verifyVideo(selectedFile!);
      }
      setResult(response);
    } catch (error: any) {
      toast.error(error.message || "An error occurred during analysis");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const toggleSection = (index: number) => {
    setExpandedSections(prev => ({ ...prev, [index]: !prev[index] }));
  };

  const VerdictBadge = ({ verdict }: { verdict: Verdict }) => {
    if (verdict === "LIKELY FAKE") {
      return (
        <span className="verdict-fake">
          <XCircle className="w-4 h-4" />
          LIKELY FAKE
        </span>
      );
    }
    if (verdict === "LIKELY TRUE") {
      return (
        <span className="verdict-true">
          <CheckCircle2 className="w-4 h-4" />
          LIKELY TRUE
        </span>
      );
    }
    if (verdict === "MISLEADING") {
      return (
        <span className="verdict-misleading">
          <AlertCircle className="w-4 h-4" />
          MISLEADING
        </span>
      );
    }
    return (
      <span className="verdict-uncertain">
        <AlertCircle className="w-4 h-4" />
        UNCERTAIN
      </span>
    );
  };

  const tabs: { id: TabType; label: string; icon: typeof FileText }[] = [
    { id: "text", label: "Text", icon: FileText },
    { id: "image", label: "Image", icon: Image },
    { id: "combined", label: "Combined", icon: Layers },
    { id: "video", label: "Video", icon: Video },
  ];

  const handleTabChange = (id: TabType) => {
    setActiveTab(id);
    setSelectedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <section id="verify" className="py-24">
      <div className="container mx-auto px-6">
        <div className="text-center mb-12">
          <h2 className="text-sm font-medium text-primary tracking-wide uppercase mb-4">
            Verification Console
          </h2>
          <h3 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
            Verify Any Content
          </h3>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Upload text, images, or videos for instant AI-powered authenticity analysis.
          </p>
        </div>

        <div className="max-w-5xl mx-auto">
          <div className="glass-panel p-8">
            <div className="grid lg:grid-cols-2 gap-8">
              <div className="space-y-6">
                <div className="flex gap-2">
                  {tabs.map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => handleTabChange(tab.id)}
                      className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${activeTab === tab.id
                        ? "bg-primary/10 text-primary border border-primary/20"
                        : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                        }`}
                    >
                      <tab.icon className="w-4 h-4" />
                      {tab.label}
                    </button>
                  ))}
                </div>

                {(activeTab === "text" || activeTab === "combined") && (
                  <textarea
                    value={inputContent}
                    onChange={(e) => setInputContent(e.target.value)}
                    placeholder="Paste the text you want to verify here..."
                    className="w-full h-32 p-4 bg-card border border-border rounded-xl text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all"
                  />
                )}

                {(activeTab === "image" || activeTab === "combined" || activeTab === "video") && (
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className="upload-zone h-32 flex flex-col items-center justify-center gap-2 cursor-pointer hover:bg-secondary/30 transition-all"
                  >
                    <input
                      type="file"
                      className="hidden"
                      ref={fileInputRef}
                      onChange={handleFileChange}
                      accept={activeTab === "video" ? "video/*" : "image/*"}
                    />
                    <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center">
                      <Upload className="w-5 h-5 text-primary" />
                    </div>
                    <div className="text-center">
                      <p className="text-xs font-medium text-foreground">
                        {selectedFile ? selectedFile.name : activeTab === "combined" ? "Add an image (optional)" : `Drop your ${activeTab} here`}
                      </p>
                    </div>
                  </div>
                )}

                <button
                  onClick={handleAnalyze}
                  disabled={isAnalyzing || (activeTab === "text" ? !inputContent.trim() : activeTab === "combined" ? !inputContent.trim() && !selectedFile : !selectedFile)}
                  className="w-full py-4 bg-primary text-primary-foreground font-medium rounded-lg transition-all hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {isAnalyzing ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      AI is verifying authenticity...
                    </>
                  ) : (
                    "Analyze Content"
                  )}
                </button>
              </div>

              <div className="space-y-6">
                {isAnalyzing ? (
                  <div className="space-y-6 animate-pulse">
                    <div className="glass-card p-6 space-y-4">
                      <div className="flex justify-between">
                        <Skeleton className="h-4 w-24 bg-muted/20" />
                        <Skeleton className="h-4 w-32 bg-muted/20" />
                      </div>
                      <div className="space-y-2">
                        <Skeleton className="h-4 w-full bg-muted/20" />
                        <Skeleton className="h-2 w-full bg-muted/10 rounded-full" />
                      </div>
                    </div>
                    <div className="glass-card divide-y divide-border">
                      <div className="p-4"><Skeleton className="h-4 w-32 bg-muted/20" /></div>
                      {[1, 2, 3].map(i => (
                        <div key={i} className="p-4"><Skeleton className="h-4 w-full bg-muted/10" /></div>
                      ))}
                    </div>
                  </div>
                ) : result ? (
                  <>
                    <div className="glass-card p-6">
                      <div className="flex items-center justify-between mb-4">
                        <span className="text-sm text-muted-foreground">Verification Result</span>
                        <VerdictBadge verdict={result.verdict} />
                      </div>

                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-muted-foreground">Confidence Level</span>
                          <span className="font-semibold">{Math.round(result.confidence * 100)}%</span>
                        </div>
                        <div className="h-2 bg-secondary rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-1000 ${result.verdict === "LIKELY FAKE" ? "bg-destructive" :
                              result.verdict === "LIKELY TRUE" ? "bg-verdict-true" :
                                result.verdict === "MISLEADING" ? "bg-[#f97316]" : "bg-verdict-uncertain"
                              }`}
                            style={{ width: `${result.confidence * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>

                    <div className={`glass-card p-6 border-l-4 mb-6 ${result.verdict === "LIKELY FAKE" ? "border-l-destructive" :
                      result.verdict === "LIKELY TRUE" ? "border-l-verdict-true" :
                        result.verdict === "MISLEADING" ? "border-l-[#f97316]" : "border-l-verdict-uncertain"
                      }`}>
                      <div className="flex items-center gap-2 mb-2">
                        <AlertCircle className="w-4 h-4 text-primary" />
                        <span className="text-sm font-bold uppercase tracking-tight">Expert Reasoning</span>
                      </div>
                      <p className="text-sm text-foreground leading-relaxed">
                        {String((result.reasoning.find(r => r.step === "Final Decision")?.details as any)?.summary || "Analysis complete.")}
                      </p>

                      <div className="mt-4 pt-4 border-t border-border/40 flex flex-wrap gap-x-6 gap-y-2">
                        {result.reasoning.some(r => r.step.includes("Text")) && (
                          <div className="flex items-center gap-2 text-[10px] text-muted-foreground uppercase font-semibold">
                            <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                            Text: Live Evidence & RAG
                          </div>
                        )}
                        {result.reasoning.some(r => r.step.includes("Visual")) && (
                          <div className="flex items-center gap-2 text-[10px] text-muted-foreground uppercase font-semibold">
                            <div className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                            Media: Visual Risk & OCR
                          </div>
                        )}
                        {result.reasoning.some(r => r.step.includes("Cross-Modal")) && (
                          <div className="flex items-center gap-2 text-[10px] text-muted-foreground uppercase font-semibold">
                            <div className="w-1.5 h-1.5 rounded-full bg-accent" />
                            Multimodal: Semantic Alignment
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="glass-card divide-y divide-border">
                      <div className="p-4 border-b border-border bg-secondary/20 flex items-center justify-between">
                        <div className="flex items-center gap-2 text-sm font-semibold">
                          <Globe className="w-4 h-4 text-primary" />
                          🔎 Evidence Sources
                        </div>
                        <span className="text-[10px] uppercase font-bold tracking-widest opacity-40">Verified via RAG</span>
                      </div>

                      {result.sources && result.sources.length > 0 ? (
                        <div className="p-4 space-y-4">
                          {result.sources.map((source, sIdx) => (
                            <div key={sIdx} className="p-3 rounded-lg bg-secondary/10 border border-border/50 hover:border-primary/30 transition-all group">
                              <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-2">
                                  <span className="text-sm font-bold text-foreground">{source.name}</span>
                                  <span className={`text-[10px] px-2 py-0.5 rounded border ${source.type.includes('Text') || source.type.includes('Audit') ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                                      source.type.includes('Image') ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' :
                                        'bg-accent/10 text-accent border-accent/20'
                                    }`}>
                                    {source.type}
                                  </span>
                                </div>
                                {source.url && (
                                  <a
                                    href={source.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-xs text-primary hover:underline flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity"
                                  >
                                    Visit Source <ExternalLink className="w-3 h-3" />
                                  </a>
                                )}
                              </div>
                              <p className="text-xs text-muted-foreground leading-relaxed">
                                {source.description}
                              </p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="p-8 text-center text-xs text-muted-foreground/60 italic">
                          No external sources were required for this verification.
                        </div>
                      )}
                    </div>

                    <div className="glass-card divide-y divide-border">
                      <div className="p-4">
                        <span className="text-sm font-medium">Analysis Breakdown</span>
                      </div>

                      {result.reasoning.map((step, index) => (
                        <div key={index} className="p-4">
                          <button
                            onClick={() => toggleSection(index)}
                            className="w-full flex items-center justify-between"
                          >
                            <div className="flex items-center gap-3">
                              <span className="text-sm font-medium">
                                {step.step}
                              </span>
                              {step.status && (
                                <span className={`text-xs px-2 py-0.5 rounded ${step.status === "HOAX" || step.status === "CONTRADICTED" || step.status === "MANIPULATED" || step.status === "INCONSISTENT"
                                  ? "bg-destructive/10 text-destructive"
                                  : step.status === "SUPPORTED" || step.status === "CONSISTENT" || step.status === "AUTHENTIC"
                                    ? "bg-verdict-true/10 text-verdict-true"
                                    : "bg-verdict-uncertain/10 text-verdict-uncertain"
                                  }`}>
                                  {step.status}
                                </span>
                              )}
                            </div>
                            {expandedSections[index] ? (
                              <ChevronUp className="w-4 h-4 text-muted-foreground" />
                            ) : (
                              <ChevronDown className="w-4 h-4 text-muted-foreground" />
                            )}
                          </button>
                          {expandedSections[index] && (
                            <div className="text-sm text-muted-foreground mt-3 pl-0 space-y-2">
                              {typeof step.details === 'string' ? (
                                <p>{step.details}</p>
                              ) : (
                                Object.entries(step.details).map(([key, value]) => (
                                  <div key={key} className="flex flex-col gap-1">
                                    <span className="text-xs font-semibold uppercase opacity-70">{key.replace(/_/g, ' ')}</span>
                                    <p>{String(value)}</p>
                                  </div>
                                ))
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="h-full flex items-center justify-center glass-card min-h-[300px]">
                    <div className="text-center text-muted-foreground">
                      <div className="w-16 h-16 rounded-2xl bg-secondary/50 flex items-center justify-center mx-auto mb-4">
                        <FileText className="w-8 h-8" />
                      </div>
                      <p className="text-sm">Enter content to analyze</p>
                      <p className="text-xs mt-1 text-muted-foreground/60">Results will appear here</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default VerificationConsole;
