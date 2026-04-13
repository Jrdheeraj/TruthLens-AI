export type Verdict = "TRUE" | "FALSE";
export type VerificationStatus = "TRUE" | "FALSE";

export interface ReasoningStep {
    step: string;
    status?: string;
    details: string | Record<string, unknown>;
}

export interface Source {
    url?: string;
    link?: string;
    title?: string;
    source?: string;
    type?: string;
    name?: string;
    description?: string;
    snippet?: string;
    text?: string;
}

// PART 8: Standardized response format
export interface AnalysisDetails {
    model_score?: number;
    visual_risk?: number;
    motion_score?: number;
    audio_score?: number;
    audio_type?: string;
    audio_has_speech?: boolean;
    detected_issues?: string[];
}

// PART 5: Corrected facts for false claims
export interface CorrectedFact {
    claim: string;
    correction: string;
}

export interface VerificationResponse {
    verdict: Verdict;
    status?: VerificationStatus;
    confidence: number;
    confidence_justification?: string;
    summary?: string;
    explanation?:
        | string
        | {
              summary?: string;
              key_points?: string[];
              points?: string[];
              technical?: string;
          };
    explanation_text?: string;
    actual_information?: string;
    what_matches_evidence_better?: string;
    sources_note?: string;
    corrected_facts?: CorrectedFact[];  // Factual corrections for FALSE claims
    details?: AnalysisDetails;  // Detailed analysis results
    reasoning?: string | ReasoningStep[];
    sources?: Source[];
    rag_powered?: boolean;
    audio_transcript?: string;  // Transcribed audio from video
}
