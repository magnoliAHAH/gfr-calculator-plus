import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from './client';

/** Препараты организации (только активные) и показания выбранного препарата. */
export function useDrugs() {
  return useQuery({ queryKey: ['meta', 'drugs'], queryFn: () => unwrap(api.GET('/meta/drugs')) });
}

export function useIndications(drugCode: string) {
  return useQuery({
    queryKey: ['meta', 'indications', drugCode],
    enabled: drugCode !== '',
    queryFn: () => unwrap(api.GET('/meta/indications', { params: { query: { drug_code: drugCode } } })),
  });
}

export function useOverrideReasons() {
  return useQuery({
    queryKey: ['meta', 'override-reasons'],
    queryFn: () => unwrap(api.GET('/meta/override-reasons')),
    staleTime: Infinity, // справочник глобальный и почти не меняется
  });
}

export function useDemoDrugs() {
  return useQuery({ queryKey: ['demo', 'drugs'], queryFn: () => unwrap(api.GET('/demo/drugs')) });
}

export function useDemoScenarios() {
  return useQuery({ queryKey: ['demo', 'scenarios'], queryFn: () => unwrap(api.GET('/demo/scenarios')) });
}
