import { Button } from '@/components/ui/button';
import type { DocumentDetail, DocumentStatus, PipelineStep } from '@/types/admin';
import { PIPELINE_STEPS } from '@/types/admin';
import { CheckCircle2, Circle, Loader2, XCircle, RotateCcw } from 'lucide-react';

interface PipelineProgressProps {
  document: DocumentDetail;
  onRetry: (step: PipelineStep['key']) => void;
  retrying?: PipelineStep['key'] | null;
}

/** Steps to render for this document: 'llm_clean' only shows once opted into or run. */
function visibleSteps(doc: DocumentDetail): PipelineStep[] {
  const llmCleanEngaged = doc.llm_clean_requested
    || Boolean(doc.llm_cleaned_at)
    || doc.status === 'llm_cleaning'
    || doc.status === 'llm_cleaned';
  return PIPELINE_STEPS.filter((step) => !step.optional || llmCleanEngaged);
}

/** Determine per-step state based on the overall document status. */
function stepState(
  step: PipelineStep,
  docStatus: DocumentStatus,
  allSteps: PipelineStep[],
): 'idle' | 'running' | 'success' | 'failed' {
  if (docStatus === 'failed') {
    // The step that was running when failure occurred
    if (docStatus === step.runningStatus) return 'failed';
    // For earlier steps that already completed, mark success
    const stepIdx = allSteps.findIndex((s) => s.key === step.key);
    // Check if failed at this step by seeing if the running-status matches
    // Actually docStatus is 'failed', we need to figure out which step failed.
    // We can infer: if this step's doneStatus was reached (previous steps), success.
    // Otherwise if we're at this step's running status or beyond but haven't completed, failed.
  }

  // Status ordering
  const STATUS_ORDER: DocumentStatus[] = [
    'uploaded',
    'converting', 'converted',
    'cleaning', 'cleaned',
    'llm_cleaning', 'llm_cleaned',
    'chunking', 'chunked',
    'embedding', 'indexed',
  ];
  const currentIdx = STATUS_ORDER.indexOf(docStatus);
  const runningIdx = STATUS_ORDER.indexOf(step.runningStatus);
  const doneIdx = STATUS_ORDER.indexOf(step.doneStatus);

  if (docStatus === 'failed') {
    // If current failed and the running status of this step is <= where we got stuck
    // We need to determine which step the doc was in when it failed.
    // The doc might have been at any stage. Check timestamps to infer.
    // Simplification: mark all steps up to (but not including) the first not-completed step as success,
    // mark the next one as failed, rest idle.
    if (doneIdx <= currentIdx) return 'success'; // completed before failure
    if (runningIdx <= currentIdx) return 'failed';
    return 'idle';
  }

  if (currentIdx >= doneIdx) return 'success';
  if (currentIdx >= runningIdx) return 'running';
  return 'idle';
}

/** Refine stepState for the 'failed' case using timestamps */
function getStepStates(doc: DocumentDetail): Record<PipelineStep['key'], 'idle' | 'running' | 'success' | 'failed'> {
  const result: Record<string, 'idle' | 'running' | 'success' | 'failed'> = {};
  const steps = visibleSteps(doc);
  const timestamps: Record<PipelineStep['key'], string | null> = {
    convert: doc.converted_at,
    clean: doc.cleaned_at,
    llm_clean: doc.llm_cleaned_at,
    chunk: doc.chunked_at,
    index: doc.indexed_at,
  };

  if (doc.status === 'failed') {
    let foundFailed = false;
    for (const step of steps) {
      if (timestamps[step.key]) {
        result[step.key] = 'success';
      } else if (!foundFailed) {
        result[step.key] = 'failed';
        foundFailed = true;
      } else {
        result[step.key] = 'idle';
      }
    }
    return result as Record<PipelineStep['key'], 'idle' | 'running' | 'success' | 'failed'>;
  }

  for (const step of steps) {
    result[step.key] = stepState(step, doc.status, steps);
  }
  return result as Record<PipelineStep['key'], 'idle' | 'running' | 'success' | 'failed'>;
}

const ICONS = {
  idle: <Circle className="h-5 w-5 text-muted-foreground" />,
  running: <Loader2 className="h-5 w-5 animate-spin text-blue-500" />,
  success: <CheckCircle2 className="h-5 w-5 text-green-500" />,
  failed: <XCircle className="h-5 w-5 text-destructive" />,
};

const LABELS = {
  idle: 'Chưa bắt đầu',
  running: 'Đang xử lý…',
  success: 'Hoàn thành',
  failed: 'Lỗi',
};

export default function PipelineProgress({ document: doc, onRetry, retrying }: PipelineProgressProps) {
  const states = getStepStates(doc);
  const steps = visibleSteps(doc);

  return (
    <div className="space-y-3">
      {steps.map((step, idx) => {
        const state = states[step.key];
        return (
          <div key={step.key} className="flex items-center gap-3">
            {/* Connector */}
            <div className="flex flex-col items-center">
              {ICONS[state]}
              {idx < steps.length - 1 && (
                <div className={`mt-1 h-6 w-0.5 ${state === 'success' ? 'bg-green-300' : 'bg-muted'}`} />
              )}
            </div>

            {/* Label + status */}
            <div className="flex-1">
              <p className="text-sm font-medium">
                {step.label}
                {step.key === 'convert' && doc.converter && state === 'success' && (
                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                    ({doc.converter})
                  </span>
                )}
                {step.key === 'chunk' && doc.chunking_strategy && state === 'success' && (
                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                    ({doc.chunking_strategy})
                  </span>
                )}
                {step.key === 'llm_clean' && state === 'success' && doc.llm_clean_warnings?.length ? (
                  <span className="ml-2 text-xs font-normal text-amber-600">
                    ({doc.llm_clean_warnings.length} cảnh báo)
                  </span>
                ) : null}
              </p>
              <p className={`text-xs ${state === 'failed' ? 'text-destructive' : 'text-muted-foreground'}`}>
                {state === 'failed' && doc.error_message ? doc.error_message : LABELS[state]}
              </p>
            </div>

            {/* Retry button for failed step */}
            {state === 'failed' && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => onRetry(step.key)}
                disabled={retrying === step.key}
              >
                {retrying === step.key ? (
                  <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                ) : (
                  <RotateCcw className="mr-1 h-3 w-3" />
                )}
                Thử lại
              </Button>
            )}
          </div>
        );
      })}
    </div>
  );
}
