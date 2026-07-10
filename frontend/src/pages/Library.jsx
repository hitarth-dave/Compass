import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Upload, Loader2, BookOpen, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Library() {
  const [books, setBooks] = useState([]);
  const [totalChunks, setTotalChunks] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const fileRef = useRef(null);

  const load = async () => {
    const res = await axios.get(`${API}/books`);
    setBooks(res.data.books);
    setTotalChunks(res.data.total_chunks);
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
      toast.success(`${res.data.filename} · added ${res.data.chunks_added} passages`);
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
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

  return (
    <div className="max-w-6xl mx-auto px-8 py-12" data-testid="library-page">
      <div className="mb-12 flex items-end justify-between gap-6 flex-wrap fade-up">
        <div>
          <div className="overline mb-4">Sanatan Grantha Bhandar</div>
          <h1 className="font-serif-display text-5xl sm:text-6xl leading-[0.95] text-[color:var(--jai-parchment)]">
            Library of <em className="text-[color:var(--jai-gold-soft)]">Shastras</em>
          </h1>
          <p className="mt-3 text-[color:var(--jai-text-muted)] max-w-xl">
            {books.length} texts · {totalChunks} indexed passages. Every AI response cites these sources.
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
            Add Scripture (PDF)
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
                <div className="text-xs uppercase tracking-widest text-[color:var(--jai-gold)]">{r.book} · {r.chapter}</div>
                <div className="mt-2 font-serif-display text-lg italic text-[color:var(--jai-parchment)] leading-relaxed">"{r.text}"</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 fade-up delay-2">
        {books.map((b, i) => (
          <div
            key={b.book}
            className="card-surface p-6 hover:-translate-y-1 transition-transform duration-300 cursor-default"
            data-testid={`book-card-${i}`}
            style={{ animationDelay: `${i * 40}ms` }}
          >
            <BookOpen size={20} className="text-[color:var(--jai-gold)] mb-4" />
            <h3 className="font-serif-display text-2xl text-[color:var(--jai-parchment)] leading-tight">{b.book}</h3>
            <div className="mt-3 text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">
              {b.chunk_count} indexed passages
            </div>
            <p className="mt-4 text-sm text-[color:var(--jai-text-muted)] italic leading-relaxed line-clamp-3">
              "{b.sample}..."
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
