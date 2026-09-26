import { useState, useEffect, useRef, useCallback } from "react";
import { Search, Plus, Loader2 } from "lucide-react";
import { searchSymbols } from "../services/api";

/**
 * Add-a-pair control for the watchlist.
 *
 * Searches the symbols the exchange actually lists rather than accepting free
 * text, so an invalid pair cannot be added in the first place. The parent
 * renders it either inline in the sidebar or inside the mobile drawer; `onClose`
 * is what lets the sidebar collapse it again.
 */
export default function WatchlistAdd({ onAdd, onClose }) {
  const [query,  setQuery]  = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");
  const [picked,  setPicked]  = useState(null);
  const boxRef = useRef(null);

  // Debounced search. Two characters is the shortest query that is not just
  // the entire market, and matches the backend's own minimum.
  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    const id = window.setTimeout(async () => {
      try {
        const d = await searchSymbols(q);
        setResults(d.results || []);
        setError("");
      } catch (e) {
        setError(e.message || "Search failed");
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 250);

    return () => window.clearTimeout(id);
  }, [query]);

  // Close on outside click, so the panel does not sit over the list forever.
  useEffect(() => {
    if (!onClose) return;
    function onDocClick(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) onClose();
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [onClose]);

  // Arrow keys + Enter, because a long result list is unusable by mouse alone.
  const onKeyDown = useCallback((e) => {
    if (!results.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setPicked(p => Math.min(p + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setPicked(p => Math.max(p - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const row = results[picked ?? 0];
      if (row) choose(row);
    } else if (e.key === "Escape") {
      onClose?.();
    }
  }, [results, picked, onClose]);

  async function choose(row) {
    try {
      await onAdd(row.symbol);
      setQuery("");
      setResults([]);
      setPicked(null);
      onClose?.();
    } catch (e) {
      setError(e.message || "Could not add that pair");
    }
  }

  const showPanel = query.trim().length >= 2;

  return (
    <div className="wl-search" ref={boxRef}>
      <div className="wl-search-bar">
        <Search size={13} className="wl-search-icon" />
        <input
          className="wl-search-input"
          value={query}
          onChange={e => { setQuery(e.target.value); setPicked(null); setError(""); }}
          onKeyDown={onKeyDown}
          placeholder="Search pairs, e.g. BTC or PEPE"
          maxLength={20}
          autoFocus
          aria-label="Search for a pair to add"
        />
        {loading
          ? <Loader2 size={13} className="wl-search-spin" />
          : <button className="wl-search-close" onClick={onClose} title="Close" type="button">
              <Plus size={13} style={{ transform: "rotate(45deg)" }} />
            </button>}
      </div>

      {error && <div className="wl-add-error">{error}</div>}

      {showPanel && (
        <div className="wl-results" role="listbox">
          {results.length === 0 && !loading && (
            <div className="wl-result-empty">No pair matches “{query.trim()}”</div>
          )}

          {results.map((r, i) => (
            <button
              key={r.symbol}
              type="button"
              role="option"
              aria-selected={i === picked}
              className={`wl-result ${i === picked ? "wl-result-sel" : ""}`}
              onMouseEnter={() => setPicked(i)}
              onClick={() => choose(r)}
            >
              <span className="wl-result-sym">
                {r.symbol.replace("USDT", "")}
                <span className="wl-usdt">/USDT</span>
              </span>
              {!r.tradeable && (
                <span className="wl-viewonly" title="Price monitoring only — not tradeable by this bot">
                  VIEW
                </span>
              )}
              <span className="wl-result-price">
                {r.price
                  ? (r.price >= 1
                      ? Number(r.price).toLocaleString(undefined, { maximumFractionDigits: 2 })
                      : Number(r.price).toFixed(6))
                  : "—"}
              </span>
              {r.change != null && (
                <span className={`wl-result-change ${r.change >= 0 ? "wl-pos" : "wl-neg"}`}>
                  {r.change >= 0 ? "+" : ""}{Number(r.change).toFixed(2)}%
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
