import type { ProviderView } from './accountConfigurationEvidence';

/** A dated successful test is historical evidence, never a continuous-health promise. */
export function onboardingProviderEvidence(providers: ProviderView[] | null, now = Date.now()) {
  if (providers === null) return { configured: null, attached: null, tested: null, testedAt: null as string | null, testedProvider: null as string | null };
  const configured = providers.filter(provider => provider.has_key === true);
  const tests = configured.filter(provider => {
    const time = typeof provider.last_test_at === 'string' ? Date.parse(provider.last_test_at) : NaN;
    return provider.last_test_ok === true && Number.isFinite(time) && time > 0 && time <= now;
  }).sort((a, b) => Date.parse(b.last_test_at!) - Date.parse(a.last_test_at!));
  return { configured: configured.length, attached: configured.some(provider => provider.live === true),
    tested: tests.length > 0, testedAt: tests[0]?.last_test_at ?? null, testedProvider: tests[0]?.id ?? null };
}
