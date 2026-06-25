/**
 * /tankers/ の船舶分布マップ。
 *
 * data.vessels (個別タンカーのリスト) を Leaflet circleMarker でプロット。
 * クリックで船名・destination・MMSI・位置をポップアップ表示。
 *
 * Leaflet は CDN から global L として読み込み済み (tankers/index.html)。
 */

import { escapeHtml } from '../core/escape.js';

const MAP_CENTER = [35.0, 137.0]; // 日本中央付近
const MAP_ZOOM = 5;
const MAP_MIN_ZOOM = 4;
const MAP_MAX_ZOOM = 10;

const TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

// マーカー色: 日本港向け (赤) / それ以外・不明 (灰)
const COLOR_JAPAN_BOUND = '#c0392b';
const COLOR_OTHER = '#7f8c8d';

const MARKER_RADIUS_PX = 7;

// 船舶 1 隻分の表示用フィールドを整形する（escape・フォールバック込み）。
// ポップアップ（マウス）と隠し表（AT）の両方が同じ整形を共有する Single Source of Truth。
function formatVesselFields(v) {
  return {
    name: v.name?.trim() ? escapeHtml(v.name) : '<em>(船名未取得)</em>',
    dest: v.destination?.trim() ? escapeHtml(v.destination) : '<em>(destination 未入力)</em>',
    mmsi: typeof v.mmsi === 'number' ? v.mmsi : escapeHtml(v.mmsi),
    coord:
      typeof v.lat === 'number' && typeof v.lon === 'number'
        ? `${v.lat.toFixed(3)}°N, ${v.lon.toFixed(3)}°E`
        : '位置不明',
    flag: v.isJapanBound ? '🇯🇵 日本港向け' : 'それ以外',
  };
}

function buildPopupHtml(v) {
  const { name, dest, mmsi, coord, flag } = formatVesselFields(v);
  return `
    <div class="tanker-popup">
      <strong>${name}</strong><br>
      <span class="tanker-popup-row"><span class="tanker-popup-label">Destination:</span> ${dest}</span><br>
      <span class="tanker-popup-row"><span class="tanker-popup-label">MMSI:</span> ${mmsi}</span><br>
      <span class="tanker-popup-row"><span class="tanker-popup-label">位置:</span> ${coord}</span><br>
      <span class="tanker-popup-row">${flag}</span>
    </div>
  `.trim();
}

/**
 * 地図のポップアップ（マウス専用）と等価な個船詳細を、スクリーンリーダー/
 * キーボード利用者向けに視覚的に隠した表で提供する（WCAG 2.1.1）。
 * chart.js の buildHiddenTable と同じ .visually-hidden パターン。
 * 引数は地図にプロットされる船（位置情報あり）のリストを想定。
 */
export function buildVesselTableHtml(vessels) {
  const list = Array.isArray(vessels) ? vessels : [];
  if (list.length === 0) return '';
  const rows = list
    .map((v) => {
      const { name, dest, mmsi, coord, flag } = formatVesselFields(v);
      return (
        `<tr><th scope="row">${name}</th>` +
        `<td>${dest}</td><td>${mmsi}</td><td>${coord}</td><td>${flag}</td></tr>`
      );
    })
    .join('');
  return (
    `<table class="visually-hidden">` +
    `<caption>海域内のタンカー一覧（${list.length}隻・船名／destination／MMSI／座標）</caption>` +
    `<thead><tr>` +
    `<th scope="col">船名</th>` +
    `<th scope="col">Destination</th>` +
    `<th scope="col">MMSI</th>` +
    `<th scope="col">座標</th>` +
    `<th scope="col">区分</th>` +
    `</tr></thead>` +
    `<tbody>${rows}</tbody>` +
    `</table>`
  );
}

export function initTankerMap(vessels) {
  const container = document.getElementById('tanker-map');
  const empty = document.getElementById('map-empty');
  if (!container) return;

  const list = Array.isArray(vessels) ? vessels : [];
  // 位置不明の vessel は地図に表示できないため除外（隠し表も地図と同じ範囲にする）
  const withPosition = list.filter((v) => typeof v.lat === 'number' && typeof v.lon === 'number');

  // AT 向けテキスト等価物。Leaflet が #tanker-map を専有するため別コンテナに描く。
  // 地図の描画より前に埋めることで、Leaflet 読み込み失敗時でもデータを提供できる。
  const tableHost = document.getElementById('tanker-table');
  if (tableHost) tableHost.innerHTML = buildVesselTableHtml(withPosition);

  if (typeof L === 'undefined') {
    console.warn('Leaflet (L) が読み込まれていません');
    container.hidden = true;
    if (empty) {
      empty.hidden = false;
      empty.textContent = '地図ライブラリの読み込みに失敗しました。';
    }
    return;
  }

  const map = L.map(container, {
    center: MAP_CENTER,
    zoom: MAP_ZOOM,
    minZoom: MAP_MIN_ZOOM,
    maxZoom: MAP_MAX_ZOOM,
    zoomControl: true,
    scrollWheelZoom: false,
  });

  const tiles = L.tileLayer(TILE_URL, {
    attribution: TILE_ATTRIBUTION,
    maxZoom: MAP_MAX_ZOOM,
  });
  tiles.on('tileerror', (e) => {
    console.warn('[tanker-map] tile error:', e?.tile?.src || e);
  });
  tiles.addTo(map);

  setTimeout(() => map.invalidateSize(), 0);

  if (withPosition.length === 0) {
    if (empty) empty.hidden = false;
    return;
  }

  for (const v of withPosition) {
    const color = v.isJapanBound ? COLOR_JAPAN_BOUND : COLOR_OTHER;
    L.circleMarker([v.lat, v.lon], {
      radius: MARKER_RADIUS_PX,
      color,
      weight: 1.5,
      fillColor: color,
      fillOpacity: 0.7,
    })
      .bindPopup(buildPopupHtml(v))
      .addTo(map);
  }
}
