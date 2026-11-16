export type QuestionType = "choice" | "noul" | "score";
export type SampleStatus = "pending" | "accepted" | "rejected";

export interface RuntimeConfig {
  device: string;
  devicePreference: string;
  availableDevices: string[];
  llmConfigured: boolean;
  llmProvider: string;
  llmBaseUrl: string;
  llmModel: string;
  jevConfigured: boolean;
  jevProvider: string;
  jevModel: string;
  targets: string[];
  reservedTargets: string[];
  layaEnabled: boolean;
  glinerEnabled: boolean;
  layaRuntimeReady: boolean;
  layaTrainReady: boolean;
  layaServeReady: boolean;
  layaVenv: string;
  layaModels: Record<string, string>;
  glinerRuntimeReady: boolean;
  glinerVenv: string;
  glinerModels: Record<string, string>;
  dataDir: string;
}

export interface Project {
  id: string;
  name: string;
  domain: string;
  languages: string[];
  questionCount: number;
  seedCount: number;
  sampleCount: number;
  pendingCount: number;
  snapshotCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface Question {
  id: string;
  projectId: string;
  key: string;
  type: QuestionType;
  instructions: string;
  criteria: Record<string, string> | string[] | null;
  order: number;
  createdAt: string;
  updatedAt: string;
}

export interface SeedSample {
  id: string;
  projectId: string;
  state: Record<string, unknown>;
  labels: Record<string, unknown>;
  source: string;
  language: string;
  createdAt: string;
}

export interface SeedImportResult {
  imported: number;
  seeds: SeedSample[];
}

export interface Annotation {
  id: string;
  questionId: string;
  questionKey: string;
  questionType: QuestionType;
  answer: Record<string, unknown>;
  teacher: string;
  teacherModel: string | null;
  confidence: number | null;
  probabilities: Record<string, number> | null;
  status: string;
  reviewer: string | null;
  reviewNote: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Sample {
  id: string;
  projectId: string;
  state: Record<string, unknown>;
  meta: Record<string, unknown>;
  source: string;
  generationJobId: string | null;
  language: string;
  difficulty: string;
  status: SampleStatus;
  annotationCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface SampleDetail extends Sample {
  annotations: Annotation[];
  questions: Question[];
  missingQuestionIds: string[];
}

export interface SampleImportResult {
  imported: number;
  heldout: number;
  samples: Sample[];
}

export interface DatasetSnapshot {
  id: string;
  projectId: string;
  version: number;
  canonicalPath: string;
  layaPath: string;
  glinerPath: string | null;
  splitCounts: Record<string, number>;
  labelDistribution: Record<string, Record<string, number>>;
  promptVersions: Record<string, string>;
  teacherModels: Record<string, number>;
  createdAt: string;
  downloads: Record<string, string>;
}


export interface GenerationPayload {
  count: number;
  languages: string[];
  difficulty: Record<string, number>;
  negativeRatio: number;
  labelBalanced: boolean;
  teacher: string;
  customPrompt?: string;
  systemPromptTemplate?: string;
  userPromptTemplate?: string;
  llm?: {
    temperature?: number;
    thinkBudget?: number;
    thinkLevel?: string;
  };
}

export interface GenerationPromptDefaults {
  system: string;
  user: string;
  placeholders: string[];
}

export interface GenerationPreview {
  model: string;
  endpoint: string;
  language: string;
  batchSize: number;
  body: Record<string, unknown>;
}

export interface GenerationJob {
  id: string;
  projectId: string;
  status: string;
  stage: string;
  progress: number;
  config: Record<string, unknown>;
  targetCount: number;
  generatedCount: number;
  acceptedCount: number;
  rejectedCount: number;
  error: string | null;
  cancelRequested: boolean;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface TrainingJob {
  id: string;
  projectId: string;
  snapshotId: string;
  target: string;
  mode: string;
  device: string;
  config: Record<string, unknown>;
  status: string;
  stage: string;
  progress: number;
  pid: number | null;
  metrics: Record<string, unknown>;
  artifactPath: string | null;
  logPath: string | null;
  error: string | null;
  cancelRequested: boolean;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface EvaluationRun {
  id: string;
  projectId: string;
  snapshotId: string;
  models: string[];
  device: string;
  status: string;
  stage: string;
  progress: number;
  results: Record<string, unknown>;
  reportPath: string | null;
  error: string | null;
  cancelRequested: boolean;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface ModelArtifact {
  id: string;
  projectId: string;
  trainingJobId: string | null;
  target: string;
  name: string;
  kind: string;
  path: string;
  metrics: Record<string, unknown>;
  config: Record<string, unknown>;
  createdAt: string;
}

export interface Deployment {
  id: string;
  artifactId: string | null;
  target: string;
  host: string;
  port: number;
  status: string;
  pid: number | null;
  logPath: string | null;
  error: string | null;
  startedAt: string | null;
  stoppedAt: string | null;
  createdAt: string;
}


export interface PlaygroundQuestionInput {
  key: string;
  type: QuestionType;
  instructions: string;
  criteria: Record<string, string> | string[] | null;
}

export interface PlaygroundResult {
  model: string;
  modelInfo: Record<string, unknown>;
  answers: Record<string, Record<string, unknown>>;
  latencyMs: number | null;
  routing: Record<string, unknown> | null;
  usage: Record<string, unknown> | null;
}
