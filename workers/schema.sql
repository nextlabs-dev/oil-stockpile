-- 有事終息予想タブ (/forecast/) の投票ストア。
-- 仕様: docs/project/01-requirements/06-crisis-forecast-tab.md §5
--
-- 生 IP は保存しない。voter_hash はソルト付き SHA-256 のみを保持する。
-- 再投票は「上書き」方式のため、(question_id, voter_hash) を UNIQUE にして
-- INSERT ... ON CONFLICT DO UPDATE で choice を差し替える。

CREATE TABLE IF NOT EXISTS votes (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  question_id TEXT NOT NULL,
  choice      TEXT NOT NULL,
  voter_hash  TEXT NOT NULL,
  created_at  TEXT NOT NULL, -- ISO8601 (UTC) 初回投票時刻
  updated_at  TEXT NOT NULL  -- ISO8601 (UTC) 最終更新時刻。連投レート制限にも使う
);

CREATE INDEX IF NOT EXISTS idx_votes_q ON votes (question_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_votes_dedup ON votes (question_id, voter_hash);
