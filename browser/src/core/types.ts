export type ValidationStatus = "ok" | "validation_failed" | "manual_review_required";

export interface ParityRow {
  number: number;
  source: string;
  converted: string;
  auditFlags: string[];
  validationStatus?: string;
}

export interface ParityResult {
  validationStatus: ValidationStatus;
  rows: ParityRow[];
  finalLineNumber: number | null;
  finalQuery: string;
  oneLineQuery: string;
  validationErrors: string[];
}

export interface ParityFixture {
  id: string;
  description: string;
  source: string;
  endDate?: string;
  expected: {
    validationStatus: ValidationStatus;
    strategyLines?: string[];
    oneLineQuery?: string;
    rowConvertedContains?: string[];
    rowAuditFlagsContain?: string[];
    rowValidationStatuses?: Record<string, string>;
  };
}
