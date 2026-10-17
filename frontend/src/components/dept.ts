export type DeptMode = 'bb' | '135' | '90'

/** DEPT sign of a carbon: CH and CH3 up, CH2 down in DEPT-135; only CH in DEPT-90; quaternary carbons vanish. */
export function deptSign(hs: number | undefined, mode: DeptMode): number {
  if (mode === 'bb') return 1
  if (hs === undefined || hs === 0) return 0
  if (mode === '90') return hs === 1 ? 1 : 0
  return hs === 2 ? -1 : 1
}
