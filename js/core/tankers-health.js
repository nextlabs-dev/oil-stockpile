export const AIS_STALE_HOURS = 6;
export const AIS_MIN_SAMPLE_DURATION_SEC = 60;

function parseFetchedAt(value) {
  if (typeof value !== 'string' || !value) return Number.NaN;
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : Number.NaN;
}

export function evaluateAisHealth(data, now = Date.now()) {
  if (!data || !Number.isFinite(data.totalTankersInRegion)) {
    return { state: 'error', message: 'AISデータの観測数を確認できません。' };
  }
  if (
    !Number.isFinite(data.japanBoundTankers) ||
    data.japanBoundTankers < 0 ||
    data.japanBoundTankers > data.totalTankersInRegion
  ) {
    return { state: 'error', message: 'AISデータの内訳を確認できません。' };
  }

  const fetchedAt = parseFetchedAt(data.fetchedAt);
  if (!Number.isFinite(fetchedAt)) {
    return { state: 'error', message: 'AISデータの取得時刻を確認できません。' };
  }

  const ageHours = (now - fetchedAt) / 3_600_000;
  if (ageHours > AIS_STALE_HOURS) {
    return {
      state: 'stale',
      ageHours,
      message: `最終取得から${Math.floor(ageHours)}時間以上経過しています。表示値は最後に取得できたスナップショットです。`,
    };
  }

  const duration = Number(data.samplingDurationSec);
  if (
    data.totalTankersInRegion === 0 ||
    !Number.isFinite(duration) ||
    duration < AIS_MIN_SAMPLE_DURATION_SEC
  ) {
    return {
      state: 'degraded',
      message: '今回のAISサンプルは短時間または観測数が少ないため、参考値としてご覧ください。',
    };
  }

  return { state: 'fresh', ageHours };
}
