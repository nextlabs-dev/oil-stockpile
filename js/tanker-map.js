/**
 * /tankers/ の船舶分布マップ。
 *
 * data.vessels (個別タンカーのリスト) を Leaflet circleMarker でプロット。
 * クリックで船名・destination・MMSI・位置をポップアップ表示。
 *
 * Leaflet は CDN から global L として読み込み済み (tankers/index.html)。
 */

const MAP_CENTER = [35.0, 137.0];   // 日本中央付近
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

function escapeHtml(s) {
  if (s == null) return '';
  return String(s)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function buildPopupHtml(v) {
  const name = v.name && v.name.trim() ? escapeHtml(v.name) : '<em>(船名未取得)</em>';
  const dest = v.destination && v.destination.trim() ? escapeHtml(v.destination) : '<em>(destination 未入力)</em>';
  const mmsi = typeof v.mmsi === 'number' ? v.mmsi : escapeHtml(v.mmsi);
  const coord = (typeof v.lat === 'number' && typeof v.lon === 'number')
    ? `${v.lat.toFixed(3)}°N, ${v.lon.toFixed(3)}°E`
    : '位置不明';
  const flag = v.isJapanBound ? '🇯🇵 日本港向け' : 'それ以外';
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

export function initTankerMap(vessels) {
  const container = document.getElementById('tanker-map');
  const empty = document.getElementById('map-empty');
  if (!container) return;

  if (typeof L === 'undefined') {
    console.warn('Leaflet (L) が読み込まれていません');
    container.hidden = true;
    if (empty) {
      empty.hidden = false;
      empty.textContent = '地図ライブラリの読み込みに失敗しました。';
    }
    return;
  }

  const list = Array.isArray(vessels) ? vessels : [];

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

  // 位置不明の vessel は表示できないため除外
  const withPosition = list.filter(
    (v) => typeof v.lat === 'number' && typeof v.lon === 'number',
  );

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
