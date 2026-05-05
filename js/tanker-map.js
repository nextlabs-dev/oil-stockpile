/**
 * /tankers/ の密度マップ描画。
 *
 * data.densityGrid.cells を Leaflet 円でプロットする。
 * cells は 0.5° メッシュ集計済 (個別船舶は識別不可) で、
 * 1 セル = lat/lon 中心 + 隻数。
 *
 * Leaflet は CDN から global L として読み込み済み (tankers/index.html)。
 */

const MAP_CENTER = [35.0, 137.0];   // 日本中央付近
const MAP_ZOOM = 5;
const MAP_MIN_ZOOM = 4;
const MAP_MAX_ZOOM = 8;

const TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

const CIRCLE_COLOR = '#c0392b';

/** 隻数 → 半径(meters)。1 隻でも見える + 多いほど大きく。 */
function radiusForCount(count) {
  return 12000 + 5000 * Math.sqrt(Math.max(count, 1));
}

/** 隻数 → 塗り透明度。多いほど濃く、最大 0.85。 */
function opacityForCount(count) {
  return Math.min(0.35 + 0.1 * count, 0.85);
}

export function initTankerMap(densityGrid) {
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

  const cells = (densityGrid && Array.isArray(densityGrid.cells))
    ? densityGrid.cells
    : [];

  const map = L.map(container, {
    center: MAP_CENTER,
    zoom: MAP_ZOOM,
    minZoom: MAP_MIN_ZOOM,
    maxZoom: MAP_MAX_ZOOM,
    zoomControl: true,
    scrollWheelZoom: false,         // ページスクロールを邪魔しない
  });

  const tiles = L.tileLayer(TILE_URL, {
    attribution: TILE_ATTRIBUTION,
    maxZoom: MAP_MAX_ZOOM,
  });
  tiles.on('tileerror', (e) => {
    // タイル取得失敗時のデバッグ補助
    console.warn('[tanker-map] tile error:', e?.tile?.src || e);
  });
  tiles.addTo(map);

  // CSS が反映された後で実サイズを再認識させる (タイミングによっては
  // Leaflet が 0px と認識して描画を止めることがあるため)
  setTimeout(() => map.invalidateSize(), 0);

  if (cells.length === 0) {
    if (empty) empty.hidden = false;
    return;
  }

  for (const { lat, lon, count } of cells) {
    if (typeof lat !== 'number' || typeof lon !== 'number') continue;
    L.circle([lat, lon], {
      radius: radiusForCount(count),
      color: CIRCLE_COLOR,
      weight: 1,
      fillColor: CIRCLE_COLOR,
      fillOpacity: opacityForCount(count),
    })
      .bindTooltip(`${count} 隻`, { direction: 'top' })
      .addTo(map);
  }
}
