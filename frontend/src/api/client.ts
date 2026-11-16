import axios from "axios";
import type {
  DatasetSnapshot,
  Deployment,
  EvaluationRun,
  GenerationJob,
  GenerationPayload,
  GenerationPreview,
  GenerationPromptDefaults,
  ModelArtifact,
  PlaygroundQuestionInput,
  PlaygroundResult,
  Project,
  Question,
  RuntimeConfig,
  Sample,
  SampleDetail,
  SampleImportResult,
  SeedImportResult,
  SeedSample,
  TrainingCharts,
  TrainingJob,
} from "@/types/api";

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(message: string, code = "REQUEST_ERROR", status = 0) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

const client = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error)) {
      const payload = error.response?.data as
        | { error?: { code?: string; message?: string } }
        | undefined;
      return Promise.reject(
        new ApiError(
          payload?.error?.message || error.message,
          payload?.error?.code || "REQUEST_ERROR",
          error.response?.status || 0,
        ),
      );
    }
    return Promise.reject(error);
  },
);

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

export async function getConfig(): Promise<RuntimeConfig> {
  const response = await client.get<{ data: RuntimeConfig }>("/config");
  return response.data.data;
}

export async function setDevice(device: string): Promise<RuntimeConfig> {
  const response = await client.post<{ data: RuntimeConfig }>("/config/device", { device });
  return response.data.data;
}

export async function listProjects(): Promise<Project[]> {
  const response = await client.get<Project[]>("/projects");
  return response.data;
}

export async function getProject(projectId: string): Promise<Project> {
  const response = await client.get<Project>(`/projects/${projectId}`);
  return response.data;
}

export async function createProject(payload: {
  name: string;
  domain: string;
  languages: string[];
}): Promise<Project> {
  const response = await client.post<Project>("/projects", payload);
  return response.data;
}

export async function updateProject(
  projectId: string,
  payload: Partial<Pick<Project, "name" | "domain" | "languages">>,
): Promise<Project> {
  const response = await client.put<Project>(`/projects/${projectId}`, payload);
  return response.data;
}

export async function deleteProject(projectId: string): Promise<void> {
  await client.post(`/projects/${projectId}/delete`);
}

export async function listQuestions(projectId: string): Promise<Question[]> {
  const response = await client.get<Question[]>(`/projects/${projectId}/questions`);
  return response.data;
}

export async function createQuestion(
  projectId: string,
  payload: {
    key: string;
    type: string;
    instructions: string;
    criteria: Record<string, string> | string[] | null;
  },
): Promise<Question> {
  const response = await client.post<Question>(`/projects/${projectId}/questions`, payload);
  return response.data;
}

export async function updateQuestion(
  projectId: string,
  questionId: string,
  payload: Partial<Question>,
): Promise<Question> {
  const response = await client.put<Question>(
    `/projects/${projectId}/questions/${questionId}`,
    payload,
  );
  return response.data;
}

export async function deleteQuestion(
  projectId: string,
  questionId: string,
): Promise<void> {
  await client.delete(`/projects/${projectId}/questions/${questionId}`);
}

export async function uploadSeeds(
  projectId: string,
  file: File,
): Promise<SeedImportResult> {
  const form = new FormData();
  form.append("file", file);
  const response = await client.post<SeedImportResult>(
    `/projects/${projectId}/seeds/import`,
    form,
  );
  return response.data;
}

export function seedTemplateUrl(
  projectId: string,
  format: "jsonl" | "csv",
): string {
  return `/api/v1/projects/${projectId}/seeds/template?format=${format}`;
}

export async function listSeeds(projectId: string): Promise<SeedSample[]> {
  const response = await client.get<SeedSample[]>(`/projects/${projectId}/seeds`);
  return response.data;
}

export async function importSeeds(
  projectId: string,
  samples: Array<{
    state: Record<string, unknown>;
    labels: Record<string, unknown>;
    language: string;
  }>,
): Promise<SeedSample[]> {
  const response = await client.post<SeedSample[]>(`/projects/${projectId}/seeds`, {
    samples,
  });
  return response.data;
}

export async function deleteSeed(seedId: string): Promise<void> {
  await client.delete(`/seeds/${seedId}`);
}

export async function promoteSeed(seedId: string): Promise<SampleDetail> {
  const response = await client.post<SampleDetail>(`/seeds/${seedId}/promote`);
  return response.data;
}

export async function promoteSeeds(projectId: string): Promise<Sample[]> {
  const response = await client.post<Sample[]>(`/projects/${projectId}/seeds/promote`, {
    seedIds: [],
  });
  return response.data;
}

export async function listSamples(params: {
  status?: string;
  projectId?: string;
  limit?: number;
}): Promise<Sample[]> {
  const response = await client.get<Sample[]>("/samples", { params });
  return response.data;
}

export async function getSample(sampleId: string): Promise<SampleDetail> {
  const response = await client.get<SampleDetail>(`/samples/${sampleId}`);
  return response.data;
}

export async function createSample(
  projectId: string,
  payload: {
    state: Record<string, unknown>;
    labels: Record<string, unknown>;
    meta?: Record<string, unknown>;
    language: string;
    difficulty: string;
  },
): Promise<SampleDetail> {
  const response = await client.post<SampleDetail>(
    `/projects/${projectId}/samples`,
    payload,
  );
  return response.data;
}

export async function importSamples(
  projectId: string,
  file: File,
): Promise<SampleImportResult> {
  const form = new FormData();
  form.append("file", file);
  const response = await client.post<SampleImportResult>(
    `/projects/${projectId}/samples/import`,
    form,
  );
  return response.data;
}

export function sampleTemplateUrl(
  projectId: string,
  format: "jsonl" | "csv",
): string {
  return `/api/v1/projects/${projectId}/samples/template?format=${format}`;
}

export async function acceptSample(sampleId: string): Promise<SampleDetail> {
  const response = await client.post<SampleDetail>(`/samples/${sampleId}/accept`, {});
  return response.data;
}

export async function rejectSample(
  sampleId: string,
  reviewNote?: string,
): Promise<SampleDetail> {
  const response = await client.post<SampleDetail>(`/samples/${sampleId}/reject`, {
    reviewNote,
  });
  return response.data;
}

export async function updateAnnotation(
  sampleId: string,
  questionId: string,
  answer: unknown,
  reviewNote?: string,
): Promise<void> {
  await client.put(`/samples/${sampleId}/annotations/${questionId}`, {
    answer,
    reviewer: "human",
    reviewNote,
  });
}

export async function deleteSample(sampleId: string): Promise<void> {
  await client.delete(`/samples/${sampleId}`);
}

export async function reannotateSample(sampleId: string): Promise<SampleDetail> {
  const response = await client.post<SampleDetail>(`/samples/${sampleId}/reannotate`);
  return response.data;
}

export async function listSnapshots(projectId?: string): Promise<DatasetSnapshot[]> {
  const response = await client.get<DatasetSnapshot[]>("/datasets", {
    params: projectId ? { projectId } : undefined,
  });
  return response.data;
}

export async function createSnapshot(projectId: string): Promise<DatasetSnapshot> {
  const response = await client.post<DatasetSnapshot>(`/projects/${projectId}/datasets`);
  return response.data;
}

export async function getSnapshot(snapshotId: string): Promise<DatasetSnapshot> {
  const response = await client.get<DatasetSnapshot>(`/datasets/${snapshotId}`);
  return response.data;
}

export async function deleteSnapshot(snapshotId: string): Promise<void> {
  await client.delete(`/datasets/${snapshotId}`);
}


export async function startGeneration(
  projectId: string,
  payload: GenerationPayload,
): Promise<GenerationJob> {
  const response = await client.post<GenerationJob>(
    `/projects/${projectId}/generate`,
    payload,
  );
  return response.data;
}

export async function getGenerationPromptDefaults(
  projectId: string,
): Promise<GenerationPromptDefaults> {
  const response = await client.get<GenerationPromptDefaults>(
    `/projects/${projectId}/generation-prompt-defaults`,
  );
  return response.data;
}

export async function previewGeneration(
  projectId: string,
  payload: GenerationPayload,
): Promise<GenerationPreview> {
  const response = await client.post<GenerationPreview>(
    `/projects/${projectId}/generation-preview`,
    payload,
  );
  return response.data;
}

export async function listGenerationJobs(projectId: string): Promise<GenerationJob[]> {
  const response = await client.get<GenerationJob[]>("/generation-jobs", {
    params: { projectId },
  });
  return response.data;
}

export async function cancelGenerationJob(jobId: string): Promise<GenerationJob> {
  const response = await client.post<GenerationJob>(`/generation-jobs/${jobId}/cancel`);
  return response.data;
}

export async function pauseGenerationJob(jobId: string): Promise<GenerationJob> {
  const response = await client.post<GenerationJob>(`/generation-jobs/${jobId}/pause`);
  return response.data;
}

export async function resumeGenerationJob(jobId: string): Promise<GenerationJob> {
  const response = await client.post<GenerationJob>(`/generation-jobs/${jobId}/resume`);
  return response.data;
}

export interface TrainingPayload {
  projectId: string;
  snapshotId: string;
  target: "laya" | "gliner";
  mode: "fit" | "finetune";
  device: string;
  baseModel?: string;
  config: {
    epochs: number;
    microBatch: number;
    gradAccum: number;
    encoderLr: number;
    headLr: number;
    loss: string;
    labelSmoothing: number;
    shuffleOptions: boolean;
    freezeEncoder: boolean;
    targetError: number;
    minAbstainN: number;
  };
}

export async function createTrainingJob(payload: TrainingPayload): Promise<TrainingJob> {
  const response = await client.post<TrainingJob>("/training-jobs", payload);
  return response.data;
}

export async function listTrainingJobs(projectId: string): Promise<TrainingJob[]> {
  const response = await client.get<TrainingJob[]>("/training-jobs", {
    params: { projectId },
  });
  return response.data;
}

export async function getTrainingCharts(jobId: string): Promise<TrainingCharts> {
  const response = await client.get<TrainingCharts>(`/training-jobs/${jobId}/charts`);
  return response.data;
}

export async function cancelTrainingJob(jobId: string): Promise<TrainingJob> {
  const response = await client.post<TrainingJob>(`/training-jobs/${jobId}/cancel`);
  return response.data;
}

export async function createEvaluation(payload: {
  projectId: string;
  snapshotId: string;
  models: string[];
  device: string;
  artifactIds?: Record<string, string>;
}): Promise<EvaluationRun> {
  const response = await client.post<EvaluationRun>("/evaluations", payload);
  return response.data;
}

export async function listEvaluations(projectId: string): Promise<EvaluationRun[]> {
  const response = await client.get<EvaluationRun[]>("/evaluations", {
    params: { projectId },
  });
  return response.data;
}

export async function cancelEvaluation(runId: string): Promise<EvaluationRun> {
  const response = await client.post<EvaluationRun>(`/evaluations/${runId}/cancel`);
  return response.data;
}

export async function runPlayground(payload: {
  projectId?: string;
  model: string;
  state: unknown;
  questions: PlaygroundQuestionInput[];
  artifactId?: string;
  device?: string;
}): Promise<PlaygroundResult> {
  const response = await client.post<PlaygroundResult>("/playground/run", payload, {
    timeout: 300000,
  });
  return response.data;
}

export function evaluationReportUrl(runId: string, format: "json" | "md"): string {
  return `/api/v1/evaluations/${runId}/report?format=${format}`;
}

export async function listArtifacts(projectId?: string): Promise<ModelArtifact[]> {
  const response = await client.get<ModelArtifact[]>("/artifacts", {
    params: projectId ? { projectId } : undefined,
  });
  return response.data;
}

export function artifactDownloadUrl(artifactId: string): string {
  return `/api/v1/artifacts/${artifactId}/download`;
}

export async function downloadArtifact(
  artifactId: string,
  onProgress?: (percent: number | null) => void,
): Promise<void> {
  const response = await client.get<Blob>(`/artifacts/${artifactId}/download`, {
    responseType: "blob",
    timeout: 0,
    onDownloadProgress: (event) => {
      onProgress?.(
        event.total ? Math.round((event.loaded / event.total) * 100) : null,
      );
    },
  });
  const disposition = String(response.headers["content-disposition"] ?? "");
  const match = disposition.match(/filename="?([^";]+)"?/);
  const filename = match?.[1] ?? `artifact-${artifactId.slice(0, 8)}.zip`;
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function createDeployment(payload: {
  artifactId: string;
  target: "laya" | "gliner";
  host?: string;
  port?: number;
}): Promise<Deployment> {
  const response = await client.post<Deployment>("/deployments", payload);
  return response.data;
}

export async function listDeployments(projectId?: string): Promise<Deployment[]> {
  const response = await client.get<Deployment[]>("/deployments", {
    params: projectId ? { projectId } : undefined,
  });
  return response.data;
}

export async function stopDeployment(deploymentId: string): Promise<Deployment> {
  const response = await client.post<Deployment>(`/deployments/${deploymentId}/stop`);
  return response.data;
}

export async function restartDeployment(deploymentId: string): Promise<Deployment> {
  const response = await client.post<Deployment>(`/deployments/${deploymentId}/restart`);
  return response.data;
}


export async function deleteArtifact(artifactId: string): Promise<void> {
  await client.delete(`/artifacts/${artifactId}`);
}

export async function deleteDeployment(deploymentId: string): Promise<void> {
  await client.delete(`/deployments/${deploymentId}`);
}
