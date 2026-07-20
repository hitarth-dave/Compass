import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Upload, Loader2, BookOpen, Search, Trash2, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Library() {
  const [seed, setSeed] = useState([]);
  const [custom, setCustom] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const fileRef = useRef(null);

  const load = async () => {
    const res = await axios.get(`${API}/books`);
    setSeed(res.data.seed || []);
    setCustom(res.data.custom || []);
  };
  useEffect(() => { load(); }, []);

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await axios.post(`${API}/books/upload`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`${res.data.book} · added ${res.data.chunks_added} passages`);
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const doDelete = async () => {
    if (!deleteTarget) return;
    try {
      await axios.delete(`${API}/books/${deleteTarget.book_id}`);
      toast.success(`Removed ${deleteTarget.book}`);
      setDeleteTarget(null);
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Delete failed");
    }
  };

  const search = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const res = await axios.get(`${API}/books/search`, { params: { q: query, k: 8 } });
      setResults(res.data.results);
    } finally {
      setSearching(false);
    }
  };

  const totalChunks =
    seed.reduce((s, b) => s + (b.chunk_count || 0), 0) +
    custom.reduce((s, b) => s + (b.chunk_count || 0), 0);

  return (
    <div className="max-w-6xl mx-auto px-8 py-12" data-testid="library-page">
      <div className="mb-12 flex items-end justify-between gap-6 flex-wrap fade-up">
        <div>
          <div className="overline mb-4">Sanatan Grantha Bhandar</div>
          <h1 className="font-serif-display text-5xl sm:text-6xl leading-[0.95] text-[color:var(--jai-parchment)]">
            Library of <em className="text-[color:var(--jai-gold)]">Shastras</em>
          </h1>
          <p className="mt-3 text-[color:var(--jai-text-muted)] max-w-xl">
            {seed.length} seed texts + {custom.length} of your uploads · {totalChunks} indexed passages.
          </p>
        </div>
        <div>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={upload}
            data-testid="upload-input"
          />
          <Button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="gold-btn h-12 px-6 font-serif-display text-lg glow-hover"
            data-testid="upload-btn"
          >
            {uploading ? <Loader2 size={16} className="mr-2 animate-spin" /> : <Upload size={16} className="mr-2" />}
            Add Your Scripture (PDF)
          </Button>
        </div>
      </div>

      <div className="card-surface p-6 mb-10 fade-up delay-1">
        <div className="overline mb-3">Search the Corpus</div>
        <div className="flex gap-3">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
            placeholder="e.g. Sade Sati, Gaja Kesari Yoga, Rahu in 10th house"
            className="bg-transparent border-[color:var(--jai-border)] text-[color:var(--jai-parchment)] font-serif-display text-lg focus-visible:ring-1 focus-visible:ring-[color:var(--jai-gold)]/50"
            data-testid="library-search-input"
          />
          <Button onClick={search} disabled={searching} className="gold-btn" data-testid="library-search-btn">
            {searching ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
          </Button>
        </div>
        {results.length > 0 && (
          <div className="mt-6 space-y-4" data-testid="search-results">
            {results.map((r, i) => (
              <div key={i} className="border-l-2 border-[color:var(--jai-gold)] pl-4 py-2">
                <div className="text-xs uppercase tracking-widest text-[color:var(--jai-gold)]">
                  {r.book} · {r.chapter}{" "}
                  {!r.is_seed && <span className="ml-2 text-[color:var(--jai-terracotta)]">(your upload)</span>}
                </div>
                <div className="mt-2 font-serif-display text-lg italic text-[color:var(--jai-parchment)] leading-relaxed">"{r.text}"</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Custom uploads section (if any) */}
      {custom.length > 0 && (
        <>
          <div className="overline mb-4 fade-up">Your uploads</div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12 fade-up">
            {custom.map((b, i) => (
              <BookCard key={b.book_id} book={b} onDelete={() => setDeleteTarget(b)} testid={`custom-book-${i}`} />
            ))}
          </div>
        </>
      )}

      {/* Seed corpus */}
      <div className="overline mb-4 fade-up delay-2 flex items-center gap-2">
        <Lock size={11} className="text-[color:var(--jai-gold)]" /> Seed corpus (built-in, locked)
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 fade-up delay-2">
        {seed.map((b, i) => (
          <BookCard key={b.book} book={b} testid={`seed-book-${i}`} />
        ))}
      </div>

      <AlertDialog open={!!deleteTarget} onOpenChange={(v) => !v && setDeleteTarget(null)}>
        <AlertDialogContent className="bg-[color:var(--jai-surface)] border-[color:var(--jai-border)]">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-serif-display text-[color:var(--jai-green-deep)]">Remove this book?</AlertDialogTitle>
            <AlertDialogDescription className="text-[color:var(--jai-text-muted)]">
              "{deleteTarget?.book}" and its {deleteTarget?.chunk_count} indexed passages will be removed from your library and future retrievals.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={doDelete} className="bg-red-700 text-white" data-testid="delete-book-confirm">Remove</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function BookCard({ book, onDelete, testid }) {
  return (
    <div
      className="card-surface p-6 hover:-translate-y-1 transition-transform duration-300 relative group"
      data-testid={testid}
    >
      <div className="flex items-start justify-between">
        <BookOpen size={20} className="text-[color:var(--jai-gold)] mb-4" />
        {book.is_seed ? (
          <span className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full bg-[color:var(--jai-gold)]/15 text-[color:var(--jai-gold)] font-semibold">
            Seed
          </span>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full bg-[color:var(--jai-terracotta)]/20 text-[color:var(--jai-terracotta)] font-semibold">
              Yours
            </span>
            {onDelete && (
              <button
                onClick={onDelete}
                className="opacity-70 hover:opacity-100 text-[color:var(--jai-terracotta)] p-1 rounded"
                title="Remove"
                data-testid={`delete-book-${book.book_id}`}
              >
                <Trash2 size={13} />
              </button>
            )}
          </div>
        )}
      </div>
      <h3 className="font-serif-display text-2xl text-[color:var(--jai-parchment)] leading-tight">{book.book}</h3>
      <div className="mt-3 text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">
        {book.chunk_count != null ? `${book.chunk_count} indexed passages` : "Live searchable"}
      </div>
      <p className="mt-4 text-sm text-[color:var(--jai-text-muted)] italic leading-relaxed line-clamp-3">
        "{book.sample}..."
      </p>
    </div>
  );
}
