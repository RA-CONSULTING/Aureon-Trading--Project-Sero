import { useReadOnlyPoller } from './useReadOnlyPoller';
import { assessmentStores, type AssessmentName } from '../services/assessmentReads';
import { currentAssessment } from '../lib/assessmentEvidence';

export function useAssessmentRead<T>(name: AssessmentName) {
  const receipt = useReadOnlyPoller(assessmentStores[name], 5_000, 8_000);
  return { ...receipt, raw: receipt.data,
    data: receipt.loading ? undefined : currentAssessment(receipt.data, Date.now(), name) as T | null };
}
