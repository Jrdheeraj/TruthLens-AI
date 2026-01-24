export type Verdict = "LIKELY TRUE" | "LIKELY FAKE" | "MISLEADING" | "UNCERTAIN";

export interface ReasoningStep {
    step: string;
    status?: string;
    details: string | Record<string, any>;
}

export interface Source {
    name: string;
    type: string;
    description: string;
    url: string | null;
}

export interface VerificationResponse {
    verdict: Verdict;
    confidence: number;
    reasoning: ReasoningStep[];
    sources: Source[];
}
